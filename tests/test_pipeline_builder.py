"""build_call_pipeline assembles a runnable task from injected parts (spec Part 2)."""

import pytest

pipecat = pytest.importorskip("pipecat")  # skip if the 'call' extra isn't installed

from assistant_shared.schemas import StructuredGoal  # noqa: E402
from assistant_worker.call.agent import AgentConfig  # noqa: E402
from assistant_worker.call.metrics import MetricsCollector  # noqa: E402
from assistant_worker.call.pipeline import build_call_pipeline  # noqa: E402
from assistant_worker.call.state import CallState, CallStateMachine  # noqa: E402
from assistant_worker.call.tools import CallToolbox  # noqa: E402


class _RecordingRunClient:
    def __init__(self):
        self.events = []

    async def status(self, status, *, call_state=None):
        self.events.append(("status", str(status), call_state))

    async def say(self, seq, speaker, text, ts_ms=None):
        self.events.append(("say", text))

    async def policy_decision(self, data):
        self.events.append(("policy_decision", data))

    async def request_approval(self, kind, question, context):
        self.events.append(("approval_requested", kind))
        return "appr-1"

    async def approval_expired(self, approval_id):
        self.events.append(("approval_expired", approval_id))


async def test_builder_assembles_with_no_audio_edges(fake_redis):
    from pipecat.services.openai.llm import OpenAILLMService

    config = AgentConfig(goal=StructuredGoal(objective="test", scenario="doctor"))
    run_client = _RecordingRunClient()
    llm = OpenAILLMService(api_key="test-key", model="test-model")
    sm = CallStateMachine(state=CallState.dialing)
    metrics = MetricsCollector()

    def make_toolbox(speak, hangup):
        return CallToolbox(
            config=config, run_client=run_client, redis=fake_redis, run_id="run-1",
            approval_timeout_s=1, speak=speak, hangup=hangup,
        )

    handles = build_call_pipeline(
        config=config, run_client=run_client, llm=llm, sm=sm, metrics=metrics,
        make_toolbox=make_toolbox, pre_llm=[], post_llm=[],
    )
    assert handles.task is not None
    assert handles.toolbox.config is config
    assert callable(handles.speak) and callable(handles.hangup)
    assert handles.pause_gate.paused is False
