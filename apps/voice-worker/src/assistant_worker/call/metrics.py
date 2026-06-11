"""Per-turn latency metrics (groundwork for EPIC-006, spec §3).

Collected in memory during the call and attached to the run_completed /
run_failed event payload, which lands in audit_log for later analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TurnMetrics:
    turn: int
    stt_ms: float | None = None
    llm_ttfb_ms: float | None = None
    tts_ttfb_ms: float | None = None

    @property
    def total_ms(self) -> float:
        return sum(v for v in (self.stt_ms, self.llm_ttfb_ms, self.tts_ttfb_ms) if v is not None)


@dataclass
class MetricsCollector:
    turns: list[TurnMetrics] = field(default_factory=list)

    def record(self, stage: str, value_ms: float) -> None:
        """Record a stage timing ('stt' | 'llm' | 'tts') for the current turn."""
        attr = {"stt": "stt_ms", "llm": "llm_ttfb_ms", "tts": "tts_ttfb_ms"}[stage]
        current = self.turns[-1] if self.turns else None
        if current is None or getattr(current, attr) is not None:
            current = TurnMetrics(turn=len(self.turns) + 1)
            self.turns.append(current)
        setattr(current, attr, value_ms)

    def summary(self) -> dict:
        if not self.turns:
            return {"turns": 0}
        totals = [t.total_ms for t in self.turns if t.total_ms]
        return {
            "turns": len(self.turns),
            "avg_turn_ms": round(sum(totals) / len(totals), 1) if totals else None,
            "max_turn_ms": round(max(totals), 1) if totals else None,
            "per_turn": [
                {
                    "turn": t.turn,
                    "stt_ms": t.stt_ms,
                    "llm_ttfb_ms": t.llm_ttfb_ms,
                    "tts_ttfb_ms": t.tts_ttfb_ms,
                }
                for t in self.turns
            ],
        }
