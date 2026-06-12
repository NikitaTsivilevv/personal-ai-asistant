"""Deterministic call-termination backstop (pure logic; no pipecat/async deps).

Guarantees a call ends even if the LLM never calls end_call: the pipeline force-ends
on a wall-clock duration cap or a conversation-turn cap. Kept pure so it is unit-tested
in isolation; the pipeline owns the timer/observer wiring.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class TerminationGuard:
    max_duration_s: float
    max_turns: int
    now: Callable[[], float] = time.monotonic
    turns: int = 0
    _start: float = field(init=False)
    _fired: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self._start = self.now()

    def register_turn(self) -> bool:
        """Count one conversation turn; return True when the turn cap is reached."""
        self.turns += 1
        return self.turns >= self.max_turns

    def duration_exceeded(self) -> bool:
        return (self.now() - self._start) >= self.max_duration_s

    def try_fire(self) -> bool:
        """Single-shot gate: returns True exactly once, the first time the pipeline
        should terminate the call. Both triggers (turns/duration) route through it."""
        if self._fired:
            return False
        self._fired = True
        return True
