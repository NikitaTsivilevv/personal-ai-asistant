"""Retry policy, summary fallback, metrics collector, TwiML (EPIC-002 plan C2-C4)."""

from __future__ import annotations

from assistant_shared.schemas import StructuredGoal
from assistant_worker.call.agent import AgentConfig
from assistant_worker.call.metrics import MetricsCollector
from assistant_worker.call.retry import RetryPolicy
from assistant_worker.call.state import CallState
from assistant_worker.call.summary import generate_summary, template_summary
from assistant_worker.call.tools import CallToolbox
from assistant_worker.call.twilio_client import stream_twiml
from assistant_worker.settings import WorkerSettings


def test_retry_policy_bounds():
    policy = RetryPolicy(max_attempts=3, base_delay_s=120, multiplier=2)
    assert policy.should_retry(CallState.no_answer, 1)
    assert policy.should_retry(CallState.busy, 2)
    assert not policy.should_retry(CallState.no_answer, 3)
    assert not policy.should_retry(CallState.failed, 1)  # not retryable
    assert not policy.should_retry(CallState.voicemail, 1)
    assert policy.delay_s(1) == 120
    assert policy.delay_s(2) == 240
    assert policy.delay_s(10) == 1800  # capped


def _toolbox() -> CallToolbox:
    goal = StructuredGoal(objective="Записаться к стоматологу")
    return CallToolbox(
        config=AgentConfig(goal=goal),
        run_client=None,  # type: ignore[arg-type]
        redis=None,  # type: ignore[arg-type]
        run_id="r1",
    )


def test_template_summary_full():
    toolbox = _toolbox()
    toolbox.end_outcome = "achieved"
    toolbox.proposed_summary = "Записал на четверг 18:00."
    toolbox.logged_facts = ["Приём стоит 50 евро"]
    toolbox.proposed_next_steps = "Прийти за 10 минут."
    text = template_summary(toolbox)
    assert "Цель достигнута" in text
    assert "Записал на четверг" in text
    assert "50 евро" in text
    assert "Следующие шаги" in text


def test_template_summary_empty():
    text = template_summary(_toolbox(), transcript_tail=["callee: adios"])
    assert "не оставил итогов" in text
    assert "adios" in text


async def test_generate_summary_falls_back_without_key():
    toolbox = _toolbox()
    toolbox.proposed_summary = "Готово."
    text = await generate_summary(toolbox, ["assistant: hola"], anthropic_api_key="")
    assert "Готово." in text


def test_metrics_collector_turns():
    m = MetricsCollector()
    m.record("stt", 120)
    m.record("llm", 450)
    m.record("tts", 200)
    m.record("stt", 100)  # starts turn 2
    summary = m.summary()
    assert summary["turns"] == 2
    assert summary["per_turn"][0]["llm_ttfb_ms"] == 450
    assert summary["avg_turn_ms"] > 0


def test_metrics_empty():
    assert MetricsCollector().summary() == {"turns": 0}


def test_stream_twiml_escapes_and_includes_params():
    settings = WorkerSettings(public_ws_url="wss://example.com/ws?a=1&b=2")
    xml = stream_twiml(settings, run_id="run-1", task_id="task-1")
    assert 'url="wss://example.com/ws?a=1&amp;b=2"' in xml
    assert '<Parameter name="run_id" value="run-1" />' in xml
    assert '<Parameter name="task_id" value="task-1" />' in xml
