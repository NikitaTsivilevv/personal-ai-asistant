"""Pipecat call pipeline: Twilio media stream <-> Deepgram <-> LLM <-> Cartesia.

Requires the ``call`` extra (``uv sync --extra call`` in apps/voice-worker) and
real provider keys; everything framework-agnostic lives in the sibling modules
so this file stays a thin assembly layer.

NOTE: written against pipecat-ai 1.x docs; verify against the installed
version during the provisioning session before the first real call.
"""

from __future__ import annotations

import json
import logging

import redis.asyncio as aioredis
from fastapi import WebSocket

from assistant_shared.schemas import Speaker

from ..events_client import RunClient
from ..settings import WorkerSettings
from .agent import AgentConfig, build_system_prompt, disclosure_text
from .control import ControlRouter
from .metrics import MetricsCollector
from .state import CallState, CallStateMachine
from .tools import TOOL_DEFINITIONS, CallToolbox

logger = logging.getLogger(__name__)

try:  # heavy optional deps
    from pipecat.adapters.schemas.function_schema import FunctionSchema
    from pipecat.adapters.schemas.tools_schema import ToolsSchema
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.frames.frames import (
        EndFrame,
        InputAudioRawFrame,
        InterimTranscriptionFrame,
        LLMMessagesAppendFrame,
        MetricsFrame,
        TranscriptionFrame,
        TTSSpeakFrame,
        TTSTextFrame,
        UserStartedSpeakingFrame,
        UserStoppedSpeakingFrame,
    )
    from pipecat.metrics.metrics import TTFBMetricsData
    from pipecat.observers.base_observer import BaseObserver, FramePushed
    from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineParams, PipelineTask
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
    from pipecat.serializers.twilio import TwilioFrameSerializer
    from pipecat.services.cartesia.tts import CartesiaTTSService
    from pipecat.services.deepgram.stt import DeepgramSTTService
    from pipecat.services.llm_service import FunctionCallParams
    from pipecat.services.openai.llm import OpenAILLMService
    from pipecat.transports.websocket.fastapi import (
        FastAPIWebsocketParams,
        FastAPIWebsocketTransport,
    )

    PIPECAT_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without the extra
    PIPECAT_AVAILABLE = False


if PIPECAT_AVAILABLE:

    class PauseGate(FrameProcessor):
        """Freezes the agent while "Pause automation" is active (EPIC-003 C1).

        Sits between STT and the user context aggregator: while paused it
        swallows the frames that would trigger an LLM turn, so the assistant
        stays silent but the call (and the transcript observer, which watches
        the STT output upstream of this gate) keeps running.
        """

        PAUSABLE_FRAMES = ()  # set after class body; see below

        def __init__(self) -> None:
            super().__init__()
            self.paused = False

        async def process_frame(self, frame, direction) -> None:
            await super().process_frame(frame, direction)
            if (
                self.paused
                and direction == FrameDirection.DOWNSTREAM
                and isinstance(frame, self.PAUSABLE_FRAMES)
            ):
                return
            await self.push_frame(frame, direction)

    PauseGate.PAUSABLE_FRAMES = (
        TranscriptionFrame,
        InterimTranscriptionFrame,
        UserStartedSpeakingFrame,
        UserStoppedSpeakingFrame,
    )

    class InboundAudioProbe(FrameProcessor):
        """Logs inbound audio frame count and peak amplitude.

        Diagnoses "bot hears nothing" by separating the failure modes: zero
        frames = media not reaching the worker (Twilio/tunnel); frames with
        peak ~0 = audio arrives but is silence (codec/serializer).
        """

        def __init__(self, log_every: int = 250) -> None:
            super().__init__()
            self._log_every = log_every
            self._frames = 0
            self._peak = 0

        async def process_frame(self, frame, direction) -> None:
            await super().process_frame(frame, direction)
            if isinstance(frame, InputAudioRawFrame):
                import array

                self._frames += 1
                if frame.audio:
                    chunk_peak = max(abs(s) for s in array.array("h", frame.audio))
                    self._peak = max(self._peak, chunk_peak)
                if self._frames % self._log_every == 1:
                    logger.info(
                        "audio-in probe: %d frames, peak amplitude since last log=%d",
                        self._frames,
                        self._peak,
                    )
                    self._peak = 0
            await self.push_frame(frame, direction)


async def read_stream_start(websocket: WebSocket) -> dict:
    """Read Twilio's connected/start messages; returns stream_sid, call_sid, custom params."""
    while True:
        raw = await websocket.receive_text()
        message = json.loads(raw)
        if message.get("event") == "start":
            start = message["start"]
            return {
                "stream_sid": start["streamSid"],
                "call_sid": start["callSid"],
                "params": start.get("customParameters", {}),
            }


def _tool_schemas() -> "ToolsSchema":
    return ToolsSchema(
        standard_tools=[
            FunctionSchema(
                name=tool["name"],
                description=tool["description"],
                properties=tool["parameters"],
                required=tool["required"],
            )
            for tool in TOOL_DEFINITIONS
        ]
    )


async def run_call_pipeline(
    *,
    websocket: WebSocket,
    stream_info: dict,
    config: AgentConfig,
    run_client: RunClient,
    redis: aioredis.Redis,
    settings: WorkerSettings,
    run_id: str,
) -> tuple[CallState, CallToolbox, MetricsCollector]:
    """Run one call to completion. Returns (final_state, toolbox, metrics)."""
    if not PIPECAT_AVAILABLE:
        raise RuntimeError("pipecat is not installed; install the 'call' extra")

    sm = CallStateMachine(state=CallState.dialing)
    metrics = MetricsCollector()
    transcript_log: list[str] = []
    seq = 0

    serializer = TwilioFrameSerializer(
        stream_sid=stream_info["stream_sid"],
        call_sid=stream_info["call_sid"],
        account_sid=settings.twilio_account_sid,
        auth_token=settings.twilio_auth_token,
    )
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            vad_analyzer=SileroVADAnalyzer(),
            serializer=serializer,
        ),
    )
    stt = DeepgramSTTService(
        api_key=settings.deepgram_api_key,
        settings=DeepgramSTTService.Settings(language=config.language),
    )
    tts = CartesiaTTSService(
        api_key=settings.cartesia_api_key,
        voice_id=settings.cartesia_voice_id,
        params=CartesiaTTSService.InputParams(language=config.language),
    )
    llm_kwargs: dict = {"api_key": settings.llm_api_key, "model": settings.llm_model}
    if settings.llm_base_url:
        llm_kwargs["base_url"] = settings.llm_base_url
    llm = OpenAILLMService(**llm_kwargs)

    context = LLMContext(
        [{"role": "system", "content": build_system_prompt(config)}],
        tools=_tool_schemas(),
    )
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(context)

    pause_gate = PauseGate()
    pipeline = Pipeline(
        [
            transport.input(),
            InboundAudioProbe(),
            stt,
            pause_gate,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )
    task = PipelineTask(pipeline, params=PipelineParams(enable_metrics=True))

    async def speak(text: str) -> None:
        await task.queue_frame(TTSSpeakFrame(text))

    async def hangup_call() -> None:
        _safe_transition(sm, CallState.wrapping_up)
        await task.queue_frame(EndFrame())

    toolbox = CallToolbox(
        config=config,
        run_client=run_client,
        redis=redis,
        run_id=run_id,
        approval_timeout_s=settings.approval_timeout_s,
        speak=speak,
        hangup=hangup_call,
    )

    async def on_whisper(text: str) -> None:
        config.whispers.append(text)
        await task.queue_frame(
            LLMMessagesAppendFrame(
                [{"role": "system", "content": f"Live instruction from your client: {text}"}],
            )
        )

    async def on_hangup(kind: str) -> None:
        logger.info("run %s: %s requested from control plane", run_id, kind)
        await hangup_call()

    async def on_pause(paused: bool) -> None:
        pause_gate.paused = paused
        logger.info("run %s: automation %s", run_id, "paused" if paused else "resumed")
        await run_client.status(
            sm.run_status, call_state="paused" if paused else sm.state.value
        )

    router = ControlRouter(
        redis, run_id, on_whisper=on_whisper, on_hangup=on_hangup, on_pause=on_pause
    )
    toolbox.control_router = router

    # Tool registration: every handler is wrapped so state transitions happen
    # around approval pauses.
    def _register(name: str):
        handler = toolbox.handlers[name]

        async def wrapper(params: "FunctionCallParams") -> None:
            nonlocal seq
            if name == "request_approval":
                _safe_transition(sm, CallState.waiting_approval)
                await run_client.status(sm.run_status, call_state=sm.state.value)
            result = await handler(**params.arguments)
            if name == "request_approval":
                _safe_transition(sm, CallState.conversation)
                await run_client.status(sm.run_status, call_state=sm.state.value)
            await params.result_callback(result)

        llm.register_function(name, wrapper, cancel_on_interruption=False)

    for tool in TOOL_DEFINITIONS:
        _register(tool["name"])

    async def emit_segment(speaker: Speaker, text: str) -> None:
        nonlocal seq
        text = text.strip()
        if not text:
            return
        seq += 1
        role = "assistant" if speaker == Speaker.assistant else "callee"
        transcript_log.append(f"{role}: {text}")
        await run_client.say(seq, speaker, text)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client) -> None:
        _safe_transition(sm, CallState.connected)
        await run_client.status(sm.run_status, call_state=sm.state.value)
        _safe_transition(sm, CallState.disclosure)
        # Mandatory disclosure: spoken via TTS directly, not LLM-generated.
        await speak(disclosure_text(config.language))
        _safe_transition(sm, CallState.conversation)
        await run_client.status(sm.run_status, call_state=sm.state.value)

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client) -> None:
        await task.queue_frame(EndFrame())

    class _CallObserver(BaseObserver):
        """Streams transcript segments and collects per-turn latency metrics.

        pipecat 1.3 removed TranscriptProcessor, so segments are taken from
        frames directly: TranscriptionFrame = callee, TTSTextFrame = assistant.
        Frames are observed at every processor hop, hence the id dedupe.
        """

        def __init__(self) -> None:
            super().__init__()
            self._seen: set[int] = set()

        async def on_push_frame(self, data: "FramePushed") -> None:
            frame = data.frame
            if frame.id in self._seen:
                return
            if isinstance(frame, TranscriptionFrame):
                self._seen.add(frame.id)
                await emit_segment(Speaker.callee, frame.text)
            elif isinstance(frame, TTSTextFrame):
                self._seen.add(frame.id)
                await emit_segment(Speaker.assistant, frame.text)
            elif isinstance(frame, MetricsFrame):
                self._seen.add(frame.id)
                for item in frame.data:
                    if isinstance(item, TTFBMetricsData) and item.value is not None:
                        stage = _stage_for_processor(item.processor or "")
                        if stage:
                            metrics.record(stage, item.value * 1000)

    task.add_observer(_CallObserver())

    router.start()
    try:
        runner = PipelineRunner(handle_sigint=False)
        await runner.run(task)
    finally:
        await router.stop()

    if sm.state == CallState.wrapping_up:
        _safe_transition(sm, CallState.ended)
    elif not sm.is_terminal:
        # Pipeline ended without an explicit wrap-up (callee hung up, drop, etc.)
        _safe_transition(sm, CallState.wrapping_up)
        _safe_transition(sm, CallState.ended)

    toolbox.transcript_log = transcript_log  # type: ignore[attr-defined]
    return sm.state, toolbox, metrics


def _stage_for_processor(processor_name: str) -> str | None:
    lowered = processor_name.lower()
    if "stt" in lowered or "deepgram" in lowered:
        return "stt"
    if "llm" in lowered or "openai" in lowered:
        return "llm"
    if "tts" in lowered or "cartesia" in lowered:
        return "tts"
    return None


def _safe_transition(sm: CallStateMachine, target: CallState) -> None:
    from .state import InvalidTransition

    try:
        sm.transition(target)
    except InvalidTransition:
        logger.debug("skipped transition %s -> %s", sm.state, target)
