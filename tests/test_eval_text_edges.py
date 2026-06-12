"""Text edges: AssistantOutputCapture aggregation + passthrough, callee injection."""

import pytest

pipecat = pytest.importorskip("pipecat")

from pipecat.frames.frames import (  # noqa: E402
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    TextFrame,
    TranscriptionFrame,
    TTSSpeakFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection  # noqa: E402

from assistant_evals.text_edges import (  # noqa: E402
    AssistantOutputCapture,
    eval_user_params,
    inject_callee_turn,
)


async def _feed(capture, frames):
    pushed = []

    async def fake_push(frame, direction=FrameDirection.DOWNSTREAM):
        pushed.append(frame)

    capture.push_frame = fake_push
    for frame in frames:
        await capture.process_frame(frame, FrameDirection.DOWNSTREAM)
    return pushed


async def test_capture_aggregates_llm_response_and_signals_turn():
    capture = AssistantOutputCapture()
    await _feed(
        capture,
        [
            LLMFullResponseStartFrame(),
            TextFrame("Hola, "),
            TextFrame("buenos días."),
            LLMFullResponseEndFrame(),
        ],
    )
    assert capture.utterances == ["Hola, buenos días."]
    assert capture.turn_done.is_set()


async def test_capture_records_direct_tts_phrases():
    capture = AssistantOutputCapture()
    pushed = await _feed(capture, [TTSSpeakFrame("Un momento, por favor.")])
    assert capture.utterances == ["Un momento, por favor."]
    assert any(isinstance(f, TTSSpeakFrame) for f in pushed)  # passthrough preserved


async def test_capture_passes_frames_through():
    capture = AssistantOutputCapture()
    pushed = await _feed(
        capture,
        [
            LLMFullResponseStartFrame(),
            TextFrame("Hola"),
            LLMFullResponseEndFrame(),
        ],
    )
    # Every frame is forwarded unchanged regardless of recording.
    assert len(pushed) == 3


async def test_capture_ignores_text_outside_response_window():
    capture = AssistantOutputCapture()
    # A stray TextFrame with no surrounding FullResponse markers is not recorded.
    await _feed(capture, [TextFrame("ruido")])
    assert capture.utterances == []


async def test_capture_does_not_buffer_transcription_frames():
    # TranscriptionFrame subclasses TextFrame; ensure a callee transcript that
    # somehow reaches the capturer mid-response is not folded into the agent text.
    capture = AssistantOutputCapture()
    await _feed(
        capture,
        [
            LLMFullResponseStartFrame(),
            TextFrame("Hola"),
            TranscriptionFrame(text="callee noise", user_id="callee", timestamp="t"),
            LLMFullResponseEndFrame(),
        ],
    )
    assert capture.utterances == ["Hola"]


async def test_inject_callee_turn_queues_native_frame_triplet():
    queued = []

    class _Task:
        async def queue_frame(self, frame):
            queued.append(frame)

    await inject_callee_turn(_Task(), "Buenos días")
    assert [type(f) for f in queued] == [
        UserStartedSpeakingFrame,
        TranscriptionFrame,
        UserStoppedSpeakingFrame,
    ]
    transcription = queued[1]
    assert transcription.text == "Buenos días"
    assert transcription.user_id == "callee"
    assert transcription.timestamp  # ISO8601 string populated


def test_eval_user_params_uses_fast_speech_timeout_and_no_vad():
    params = eval_user_params()
    assert params.vad_analyzer is None
    strategies = params.user_turn_strategies.stop
    assert len(strategies) == 1
    from pipecat.turns.user_stop import SpeechTimeoutUserTurnStopStrategy

    assert isinstance(strategies[0], SpeechTimeoutUserTurnStopStrategy)
