"""Text edges replacing the audio layer in eval pipelines (spec Part 2).

Input: the dialog driver queues UserStartedSpeaking/Transcription/UserStoppedSpeaking
frames directly onto the pipeline task (no transport, no STT, no VAD).
Output: AssistantOutputCapture sits in the TTS position, recording agent utterances
(streamed LLM text between FullResponse markers, plus direct TTSSpeakFrame phrases:
disclosure, approval filler, deny phrase, expiry wrap-up) and signalling end-of-turn.

Pipecat 1.3.0 class-hierarchy notes (verified in .venv):
- ``LLMTextFrame`` and ``TranscriptionFrame`` both subclass ``TextFrame``
  (frames.py:333, 415); ``isinstance(frame, TextFrame)`` therefore matches the
  streamed LLM output we want AND the callee ``TranscriptionFrame`` we don't.
  We exclude ``TranscriptionFrame`` explicitly so a callee transcript reaching the
  capturer is never folded into the agent's text.
- ``TTSSpeakFrame`` subclasses ``DataFrame`` (frames.py:740), NOT ``TextFrame`` —
  so recording it in its own branch cannot double-record via the TextFrame branch.
"""

from __future__ import annotations

import asyncio

from pipecat.frames.frames import (
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    TextFrame,
    TranscriptionFrame,
    TTSSpeakFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.aggregators.llm_response_universal import LLMUserAggregatorParams
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.turns.user_stop import SpeechTimeoutUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.utils.time import time_now_iso8601


class AssistantOutputCapture(FrameProcessor):
    """Collects agent text output; turn_done fires when a reply is complete."""

    def __init__(self) -> None:
        super().__init__()
        self.utterances: list[str] = []
        self.turn_done = asyncio.Event()
        self._buffer: list[str] = []
        self._in_response = False

    async def process_frame(self, frame, direction) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMFullResponseStartFrame):
            self._in_response = True
            self._buffer = []
        elif isinstance(frame, LLMFullResponseEndFrame):
            text = "".join(self._buffer).strip()
            if text:
                self.utterances.append(text)
            self._in_response = False
            self.turn_done.set()
        elif isinstance(frame, TTSSpeakFrame):
            self.utterances.append(frame.text)
            self.turn_done.set()
        elif (
            isinstance(frame, TextFrame)
            and not isinstance(frame, TranscriptionFrame)
            and self._in_response
        ):
            # TranscriptionFrame subclasses TextFrame; it is callee input, not agent
            # output, so it must never be buffered into the agent's utterance.
            self._buffer.append(frame.text)
        await self.push_frame(frame, direction)


async def inject_callee_turn(task, text: str) -> None:
    """Feed one callee utterance as the user aggregator's native frame triplet."""
    await task.queue_frame(UserStartedSpeakingFrame())
    await task.queue_frame(
        TranscriptionFrame(text=text, user_id="callee", timestamp=time_now_iso8601())
    )
    await task.queue_frame(UserStoppedSpeakingFrame())


def eval_user_params() -> LLMUserAggregatorParams:
    """Aggregator params for text mode: no VAD, fast speech-timeout turn close.

    ``SpeechTimeoutUserTurnStopStrategy`` takes keyword-only ``user_speech_timeout``
    (verified at pipecat/turns/user_stop/speech_timeout_user_turn_stop_strategy.py:48),
    not ``timeout`` as the plan draft assumed.
    """
    return LLMUserAggregatorParams(
        user_turn_strategies=UserTurnStrategies(
            stop=[SpeechTimeoutUserTurnStopStrategy(user_speech_timeout=0.2)]
        ),
    )
