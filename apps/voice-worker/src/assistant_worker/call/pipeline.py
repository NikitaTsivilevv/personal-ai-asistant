"""Pipecat call pipeline: Twilio media stream <-> Deepgram <-> LLM <-> Cartesia.

Requires the ``call`` extra (``uv sync --extra call`` in apps/voice-worker) and
real provider keys; everything framework-agnostic lives in the sibling modules
so this file stays a thin assembly layer.

NOTE: written against pipecat-ai 1.x docs; verify against the installed
version during the provisioning session before the first real call.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

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


@dataclass
class CallPipelineHandles:
    """Everything a caller needs to run and steer one assembled call pipeline."""

    task: "PipelineTask"
    toolbox: CallToolbox
    pause_gate: "PauseGate"
    speak: Callable[[str], Awaitable[None]]
    hangup: Callable[[], Awaitable[None]]
    transcript_log: list[str]


try:  # heavy optional deps
    from pipecat.adapters.schemas.function_schema import FunctionSchema
    from pipecat.adapters.schemas.tools_schema import ToolsSchema
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.audio.vad.vad_analyzer import VADParams
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
    from pipecat.processors.aggregators.llm_response_universal import (
        LLMContextAggregatorPair,
        LLMUserAggregatorParams,
    )
    from pipecat.serializers.twilio import TwilioFrameSerializer
    from pipecat.services.cartesia.tts import CartesiaTTSService
    from pipecat.services.deepgram.stt import DeepgramSTTService
    from pipecat.services.llm_service import FunctionCallParams
    from pipecat.services.openai.llm import OpenAILLMService
    from pipecat.transports.websocket.fastapi import (
        FastAPIWebsocketParams,
        FastAPIWebsocketTransport,
    )
    from pipecat.turns.user_stop import (
        SpeechTimeoutUserTurnStopStrategy,
        TurnAnalyzerUserTurnStopStrategy,
    )
    from pipecat.turns.user_turn_strategies import UserTurnStrategies

    PIPECAT_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without the extra
    PIPECAT_AVAILABLE = False


if PIPECAT_AVAILABLE:
    # --- pipecat 1.3 turns-API wiring (verified against the installed venv) ---
    # The pre-1.3 `FastAPIWebsocketParams(vad_analyzer=...)` kwarg was a SILENT
    # NO-OP: TransportParams (base_transport.py) has no vad_analyzer field and
    # pydantic ignores the unknown kwarg, so VAD config never took effect and
    # turns used default behaviour. The 1.3 attach points are:
    #
    # 1. VAD attaches on the USER CONTEXT AGGREGATOR, not the transport:
    #    LLMUserAggregatorParams.vad_analyzer (llm_response_universal.py:160,
    #    consumed at :649 to build the VADController). NOT on TransportParams.
    # 2. The smart-turn STOP STRATEGY attaches via the same aggregator's
    #    user_turn_strategies. The default UserTurnStrategies.stop already is
    #    [TurnAnalyzerUserTurnStopStrategy(LocalSmartTurnAnalyzerV3())]
    #    (user_turn_strategies.py:43-51, 74-78), so supplying vad_analyzer is
    #    enough to get VAD + smart-turn; we pass an explicit list so the
    #    VAD-only fallback (None analyzer) is also honoured.
    # 3. Barge-in / interruptions: enable_interruptions defaults to True on
    #    BaseUserTurnStartStrategy (base_user_turn_start_strategy.py:55),
    #    inherited by the default VADUserTurnStartStrategy; the user-turn
    #    processor calls broadcast_interruption() when it is set
    #    (user_turn_processor.py:194). No separate flag on PipelineParams.

    def build_vad_analyzer() -> "SileroVADAnalyzer":
        """Silero VAD wired onto the user aggregator (the actual turn-detection fix).

        The previous `vad_analyzer=` kwarg on FastAPIWebsocketParams was silently
        ignored, so no VADController existed and user turns never closed. The real
        default VAD_STOP_SECS is 0.2s; 0.3s is a slightly more conservative silence
        window to avoid clipping mid-utterance pauses in call-centre audio, while
        smart-turn V3 remains the primary semantic end-of-turn signal.
        """
        return SileroVADAnalyzer(
            params=VADParams(confidence=0.6, start_secs=0.2, stop_secs=0.3, min_volume=0.5)
        )

    def build_turn_analyzer():
        """Semantic end-of-turn classifier (smart-turn V3).

        Falls back to None (VAD-only) if the ONNX model can't load offline, so a
        provisioning host without the model still runs calls.
        """
        try:
            from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import (
                LocalSmartTurnAnalyzerV3,
            )

            return LocalSmartTurnAnalyzerV3()
        except Exception as exc:  # model download / load failure
            logger.warning("smart-turn V3 unavailable, VAD-only turn-taking: %s", exc)
            return None

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


def build_call_pipeline(
    *,
    config: AgentConfig,
    run_client: RunClient,
    llm: "OpenAILLMService",
    sm: CallStateMachine,
    metrics: MetricsCollector,
    make_toolbox: Callable[
        [Callable[[str], Awaitable[None]], Callable[[], Awaitable[None]]], CallToolbox
    ],
    pre_llm: "Sequence[FrameProcessor]" = (),
    post_llm: "Sequence[FrameProcessor]" = (),
    user_params: "LLMUserAggregatorParams | None" = None,
    on_callee_turn: "Callable[[], Awaitable[None]] | None" = None,
) -> CallPipelineHandles:
    """Pure assembly of one call pipeline from injected parts.

    Knows nothing about Twilio/Deepgram/Cartesia/websockets/settings: the audio
    (or text) edges arrive via ``pre_llm``/``post_llm`` and the providers via
    ``llm``/``make_toolbox``. Production audio and the offline text-edge eval
    harness share this exact aggregator/LLM/tool/policy core.
    """
    if not PIPECAT_AVAILABLE:
        raise RuntimeError("pipecat is not installed; install the 'call' extra")

    seq = 0
    transcript_log: list[str] = []

    context = LLMContext(
        [{"role": "system", "content": build_system_prompt(config)}],
        tools=_tool_schemas(),
    )
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=user_params if user_params is not None else LLMUserAggregatorParams(),
    )

    pause_gate = PauseGate()
    pipeline = Pipeline(
        [
            *pre_llm,
            pause_gate,
            user_aggregator,
            llm,
            *post_llm,
            assistant_aggregator,
        ]
    )
    task = PipelineTask(pipeline, params=PipelineParams(enable_metrics=True))

    async def speak(text: str) -> None:
        await task.queue_frame(TTSSpeakFrame(text))

    async def hangup_call() -> None:
        _safe_transition(sm, CallState.wrapping_up)
        await task.queue_frame(EndFrame())

    toolbox = make_toolbox(speak, hangup_call)

    # Tool registration: every handler is wrapped so state transitions happen
    # around approval pauses.
    def _register(name: str):
        handler = toolbox.handlers[name]

        async def wrapper(params: "FunctionCallParams") -> None:
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
            elif isinstance(frame, UserStoppedSpeakingFrame):
                self._seen.add(frame.id)
                if on_callee_turn is not None:
                    await on_callee_turn()
            elif isinstance(frame, MetricsFrame):
                self._seen.add(frame.id)
                for item in frame.data:
                    if isinstance(item, TTFBMetricsData) and item.value is not None:
                        stage = _stage_for_processor(item.processor or "")
                        if stage:
                            metrics.record(stage, item.value * 1000)

    task.add_observer(_CallObserver())

    return CallPipelineHandles(
        task=task,
        toolbox=toolbox,
        pause_gate=pause_gate,
        speak=speak,
        hangup=hangup_call,
        transcript_log=transcript_log,
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

    serializer = TwilioFrameSerializer(
        stream_sid=stream_info["stream_sid"],
        call_sid=stream_info["call_sid"],
        account_sid=settings.twilio_account_sid,
        auth_token=settings.twilio_auth_token,
    )
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        # VAD is NOT configured here in pipecat 1.3: TransportParams has no
        # vad_analyzer field, so the old kwarg was a silent no-op. VAD/turn/
        # barge-in are wired on the user aggregator below.
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
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

    # pipecat 1.3 turn-taking wiring (see findings comment near build_vad_analyzer):
    #   - vad_analyzer attaches here, NOT on the transport
    #     (llm_response_universal.py:160,649 -> VADController).
    #   - The default user_turn_strategies.stop is
    #     TurnAnalyzerUserTurnStopStrategy(LocalSmartTurnAnalyzerV3())
    #     (user_turn_strategies.py:43-51), so we build the strategy list
    #     explicitly to honour the VAD-only fallback when no model loads.
    #   - Barge-in: enable_interruptions defaults True on the (default)
    #     VADUserTurnStartStrategy (base_user_turn_start_strategy.py:55).
    turn_analyzer = build_turn_analyzer()
    if turn_analyzer is not None:
        stop_strategies = [TurnAnalyzerUserTurnStopStrategy(turn_analyzer=turn_analyzer)]
    else:
        # VAD-only fallback: a pure VAD/STT-timeout stop strategy with no ML
        # model, so we don't re-trigger the smart-turn load that just failed.
        # NOTE: passing user_turn_strategies=None would let pipecat rebuild the
        # default LocalSmartTurnAnalyzerV3 (user_turn_strategies.py:43-51),
        # re-hitting the same load failure — hence the explicit strategy here.
        stop_strategies = [SpeechTimeoutUserTurnStopStrategy()]
    user_params = LLMUserAggregatorParams(
        # VAD attach point in 1.3 (llm_response_universal.py:160,649).
        vad_analyzer=build_vad_analyzer(),
        # Smart-turn (or VAD-only) stop strategy; start strategies keep
        # their default VADUserTurnStartStrategy, whose enable_interruptions
        # default True drives barge-in (base_user_turn_start_strategy.py:55).
        user_turn_strategies=UserTurnStrategies(stop=stop_strategies),
    )

    def make_toolbox(speak, hangup) -> CallToolbox:
        return CallToolbox(
            config=config,
            run_client=run_client,
            redis=redis,
            run_id=run_id,
            approval_timeout_s=settings.approval_timeout_s,
            speak=speak,
            hangup=hangup,
        )

    from .termination import TerminationGuard
    from .agent import termination_wrapup

    guard = TerminationGuard(
        max_duration_s=settings.max_call_duration_s,
        max_turns=settings.max_call_turns,
    )

    async def _force_terminate() -> None:
        if not guard.try_fire():
            return
        logger.info("run %s: termination backstop fired (turns=%d)", run_id, guard.turns)
        await handles.speak(termination_wrapup(config.language))
        await handles.hangup()

    async def _on_callee_turn() -> None:
        if guard.register_turn():
            await _force_terminate()

    handles = build_call_pipeline(
        config=config,
        run_client=run_client,
        llm=llm,
        sm=sm,
        metrics=metrics,
        make_toolbox=make_toolbox,
        pre_llm=[transport.input(), InboundAudioProbe(), stt],
        post_llm=[tts, transport.output()],
        user_params=user_params,
        on_callee_turn=_on_callee_turn,
    )
    task = handles.task
    pause_gate = handles.pause_gate

    async def _duration_watchdog() -> None:
        while True:
            await asyncio.sleep(5)
            if guard.duration_exceeded():
                await _force_terminate()
                return

    watchdog = asyncio.create_task(_duration_watchdog())

    async def on_whisper(text: str) -> None:
        config.whispers.append(text)
        await task.queue_frame(
            LLMMessagesAppendFrame(
                [{"role": "system", "content": f"Live instruction from your client: {text}"}],
            )
        )

    async def on_hangup(kind: str) -> None:
        logger.info("run %s: %s requested from control plane", run_id, kind)
        await handles.hangup()

    async def on_pause(paused: bool) -> None:
        pause_gate.paused = paused
        logger.info("run %s: automation %s", run_id, "paused" if paused else "resumed")
        await run_client.status(
            sm.run_status, call_state="paused" if paused else sm.state.value
        )

    router = ControlRouter(
        redis, run_id, on_whisper=on_whisper, on_hangup=on_hangup, on_pause=on_pause
    )
    handles.toolbox.control_router = router

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client) -> None:
        _safe_transition(sm, CallState.connected)
        await run_client.status(sm.run_status, call_state=sm.state.value)
        _safe_transition(sm, CallState.disclosure)
        # Mandatory disclosure: spoken via TTS directly, not LLM-generated.
        await handles.speak(disclosure_text(config.language))
        _safe_transition(sm, CallState.conversation)
        await run_client.status(sm.run_status, call_state=sm.state.value)

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client) -> None:
        await task.queue_frame(EndFrame())

    router.start()
    try:
        runner = PipelineRunner(handle_sigint=False)
        await runner.run(task)
    finally:
        watchdog.cancel()
        await router.stop()

    if sm.state == CallState.wrapping_up:
        _safe_transition(sm, CallState.ended)
    elif not sm.is_terminal:
        # Pipeline ended without an explicit wrap-up (callee hung up, drop, etc.)
        _safe_transition(sm, CallState.wrapping_up)
        _safe_transition(sm, CallState.ended)

    handles.toolbox.transcript_log = handles.transcript_log  # type: ignore[attr-defined]
    return sm.state, handles.toolbox, metrics


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
