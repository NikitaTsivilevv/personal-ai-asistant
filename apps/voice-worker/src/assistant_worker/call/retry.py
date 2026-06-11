"""Bounded retries with backoff for busy/no-answer outcomes (spec §2)."""

from __future__ import annotations

from dataclasses import dataclass

from .state import RETRYABLE_STATES, CallState


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_s: float = 120.0
    multiplier: float = 2.0
    max_delay_s: float = 1800.0

    def should_retry(self, outcome: CallState, attempt_no: int) -> bool:
        return outcome in RETRYABLE_STATES and attempt_no < self.max_attempts

    def delay_s(self, attempt_no: int) -> float:
        """Delay before the next attempt; attempt_no is the attempt that just failed (1-based)."""
        return min(self.base_delay_s * self.multiplier ** (attempt_no - 1), self.max_delay_s)
