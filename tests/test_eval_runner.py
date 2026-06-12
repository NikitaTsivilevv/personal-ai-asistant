import asyncio

import pytest

pipecat = pytest.importorskip("pipecat")

from assistant_evals.case import EvalCase  # noqa: E402
from assistant_evals.llm_client import FakeChat  # noqa: E402
from assistant_evals.runner import EvalConfig, run_case  # noqa: E402


def _case() -> EvalCase:
    return EvalCase.model_validate({
        "name": "test/case",
        "goal": {"objective": "Preguntar horario", "scenario": "info_gathering"},
        "persona": "Empleado de farmacia.",
        "expected_end_outcome": "achieved",
        "max_turns": 3,
    })


def test_run_case_with_stubbed_pipeline(monkeypatch, tmp_path):
    """The driver loops simulator<->agent via the stub, scores, writes an artifact."""
    from assistant_evals import runner as runner_mod
    from assistant_evals.fakes import FakeRunClient

    class StubPipeline:
        def __init__(self):
            self.injected = []
            self.agent_replies = ["Hola, ¿el horario?", "Gracias, adiós."]
            self.run_client = FakeRunClient()

        @property
        def ended(self):
            return not self.agent_replies

        async def start(self):
            pass

        async def agent_turn(self):
            return [self.agent_replies.pop(0)] if self.agent_replies else []

        async def inject(self, text):
            self.injected.append(text)

        async def finish(self):
            return "achieved", "Horario: 9-21", {"turns": 2}, []

    monkeypatch.setattr(runner_mod, "_build_live_pipeline", lambda case, cfg: StubPipeline())
    cfg = EvalConfig(
        sim_chat_factory=lambda: FakeChat(["Nuestro horario es de 9 a 21."]),
        judge_chat_factory=lambda: FakeChat(['{"success": true, "reason": "ok"}',
                                             '{"holds_role": true, "reason": "ok"}']),
        out_dir=tmp_path,
    )
    result = asyncio.run(run_case(_case(), cfg))
    assert result.case_name == "test/case"
    assert {a.axis for a in result.axes} == {"policy", "success", "role", "latency", "cost"}
    assert all(a.passed for a in result.axes if a.axis == "policy")
    artifacts = list(tmp_path.glob("*.json"))
    assert len(artifacts) == 1


def test_run_case_contains_dialog_crash(monkeypatch, tmp_path):
    """If agent_turn raises mid-dialog, run_case still finishes, marks the case
    crashed (failed policy axis), and writes an artifact."""
    from assistant_evals import runner as runner_mod
    from assistant_evals.fakes import FakeRunClient

    class CrashingPipeline:
        def __init__(self):
            self.injected = []
            self.run_client = FakeRunClient()
            self._calls = 0
            self.finished = False

        @property
        def ended(self):
            return False

        async def start(self):
            pass

        async def agent_turn(self):
            self._calls += 1
            if self._calls >= 2:
                raise RuntimeError("pipeline runner crashed during dialog")
            return ["Hola, ¿el horario?"]

        async def inject(self, text):
            self.injected.append(text)

        async def finish(self):
            self.finished = True
            return None, None, {}, []

    pipeline = CrashingPipeline()
    monkeypatch.setattr(runner_mod, "_build_live_pipeline", lambda case, cfg: pipeline)
    cfg = EvalConfig(
        sim_chat_factory=lambda: FakeChat(["Nuestro horario es de 9 a 21."]),
        judge_chat_factory=lambda: FakeChat(['{"success": false, "reason": "no"}',
                                             '{"holds_role": false, "reason": "no"}']),
        out_dir=tmp_path,
    )
    result = asyncio.run(run_case(_case(), cfg))
    assert pipeline.finished
    policy = next(a for a in result.axes if a.axis == "policy")
    assert not policy.passed
    assert "crashed" in policy.details
    artifacts = list(tmp_path.glob("*.json"))
    assert len(artifacts) == 1


def test_run_case_index_avoids_artifact_collision(monkeypatch, tmp_path):
    """Two runs in the same second with different run_index write distinct files."""
    from assistant_evals import runner as runner_mod
    from assistant_evals.fakes import FakeRunClient

    class StubPipeline:
        def __init__(self):
            self.agent_replies = ["Hola.", "Adiós."]
            self.run_client = FakeRunClient()

        @property
        def ended(self):
            return not self.agent_replies

        async def start(self):
            pass

        async def agent_turn(self):
            return [self.agent_replies.pop(0)] if self.agent_replies else []

        async def inject(self, text):
            pass

        async def finish(self):
            return "achieved", "ok", {"turns": 2}, []

    monkeypatch.setattr(runner_mod, "_build_live_pipeline",
                        lambda case, cfg: StubPipeline())

    def make_cfg():
        return EvalConfig(
            sim_chat_factory=lambda: FakeChat(["Hola."]),
            judge_chat_factory=lambda: FakeChat(['{"success": true, "reason": "ok"}',
                                                 '{"holds_role": true, "reason": "ok"}']),
            out_dir=tmp_path,
        )

    r0 = asyncio.run(run_case(_case(), make_cfg(), run_index=0))
    r1 = asyncio.run(run_case(_case(), make_cfg(), run_index=1))
    assert r0.artifact_path != r1.artifact_path
    artifacts = list(tmp_path.glob("*.json"))
    assert len(artifacts) == 2
