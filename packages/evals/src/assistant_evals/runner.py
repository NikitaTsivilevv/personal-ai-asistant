"""Per-case dialog driver + sweep runner (spec Part 2).

run_case drives: disclosure -> [simulator turn -> agent turn]* -> end, then scores.
The pipeline interaction is isolated behind _build_live_pipeline so tests can stub it.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .case import EvalCase
from .llm_client import OpenAICompatChat
from .scoring import AxisResult, score_cost, score_policy, score_role, score_success
from .simulator import CalleeSimulator

AGENT_TURN_TIMEOUT_S = 90  # generous: includes approval waits


@dataclass
class EvalConfig:
    agent_model: str = "claude-haiku-4-5"
    sim_model: str = "claude-haiku-4-5"
    judge_model: str = "claude-sonnet-4-6"
    approval_timeout_s: int = 3
    out_dir: Path = Path("evals-results")
    sim_chat_factory: "Callable | None" = None    # tests inject FakeChat
    judge_chat_factory: "Callable | None" = None

    def sim_chat(self):
        return (self.sim_chat_factory or (lambda: OpenAICompatChat(self.sim_model)))()

    def judge_chat(self):
        return (self.judge_chat_factory or (lambda: OpenAICompatChat(self.judge_model)))()


@dataclass
class CaseRunResult:
    case_name: str
    axes: list[AxisResult]
    transcript: list[tuple[str, str]]
    artifact_path: Path | None = None

    @property
    def policy_passed(self) -> bool:
        return all(a.passed for a in self.axes if a.axis == "policy")


def _approved_sensitive(run_client, case: EvalCase) -> bool:
    """True when a sensitive_data approval was requested and the script approved one."""
    requested = any(e[0] == "approval_requested" and e[1] == "sensitive_data"
                    for e in run_client.events)
    return requested and any(item.decision == "approve" for item in case.client_script)


class _LivePipeline:
    """Real pipeline assembly behind the driver interface used by run_case.

    Methods: start() -> None; inject(text) -> None; agent_turn() -> list[str]
    (utterances since the last call); finish() -> (end_outcome, summary,
    latency_summary, policy_decisions).
    """

    def __init__(self, case: EvalCase, cfg: EvalConfig) -> None:
        import fakeredis.aioredis as fakeaioredis
        from pipecat.services.openai.llm import OpenAILLMService

        from assistant_worker.call.agent import AgentConfig, ProfileFactView
        from assistant_worker.call.metrics import MetricsCollector
        from assistant_worker.call.pipeline import build_call_pipeline
        from assistant_worker.call.state import CallState, CallStateMachine
        from assistant_worker.call.tools import CallToolbox

        from .fakes import ApprovalResponder, FakeRunClient
        from .text_edges import AssistantOutputCapture, eval_user_params

        self.case = case
        self.redis = fakeaioredis.FakeRedis()
        self.run_client = FakeRunClient()
        self.capture = AssistantOutputCapture()
        self.metrics = MetricsCollector()
        self._sm = CallStateMachine(state=CallState.conversation)
        self._consumed = 0

        config = AgentConfig(
            goal=case.goal,
            language=case.language,
            facts=[ProfileFactView(**f.model_dump()) for f in case.facts],
        )
        llm = OpenAILLMService(
            api_key=os.environ["LLM_API_KEY"],
            model=cfg.agent_model,
            base_url=os.environ.get("LLM_BASE_URL") or None,
        )

        def make_toolbox(speak, hangup):
            return CallToolbox(
                config=config, run_client=self.run_client, redis=self.redis,
                run_id="run-eval", approval_timeout_s=cfg.approval_timeout_s,
                speak=speak, hangup=hangup,
            )

        self.handles = build_call_pipeline(
            config=config, run_client=self.run_client, llm=llm, sm=self._sm,
            metrics=self.metrics, make_toolbox=make_toolbox,
            pre_llm=[], post_llm=[self.capture], user_params=eval_user_params(),
        )
        self.responder = ApprovalResponder(
            self.redis, "run-eval", self.run_client, case.client_script
        )
        self._runner_task: asyncio.Task | None = None

    async def start(self) -> None:
        from pipecat.pipeline.runner import PipelineRunner

        from assistant_worker.call.agent import disclosure_text

        self.responder.start()
        runner = PipelineRunner(handle_sigint=False)
        self._runner_task = asyncio.create_task(runner.run(self.handles.task))
        await self.handles.speak(disclosure_text(self.case.language))

    async def inject(self, text: str) -> None:
        from .text_edges import inject_callee_turn

        self.capture.turn_done.clear()
        await inject_callee_turn(self.handles.task, text)

    async def agent_turn(self) -> list[str]:
        from assistant_worker.call.state import CallState

        deadline = asyncio.get_event_loop().time() + AGENT_TURN_TIMEOUT_S
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            try:
                await asyncio.wait_for(self.capture.turn_done.wait(), remaining)
            except asyncio.TimeoutError:
                break
            await asyncio.sleep(0.3)  # let trailing frames land
            if self._sm.state == CallState.waiting_approval:
                # Woken by the approval filler; the agent is still blocked on the
                # client's answer - keep waiting for the post-approval reply.
                self.capture.turn_done.clear()
                continue
            break
        new = self.capture.utterances[self._consumed:]
        self._consumed = len(self.capture.utterances)
        return new

    @property
    def ended(self) -> bool:
        return self.handles.toolbox.end_outcome is not None

    async def finish(self):
        from pipecat.frames.frames import EndFrame

        if self._runner_task is not None and not self._runner_task.done():
            await self.handles.task.queue_frame(EndFrame())
            try:
                await asyncio.wait_for(self._runner_task, 15)
            except asyncio.TimeoutError:
                self._runner_task.cancel()
        await self.responder.stop()
        toolbox = self.handles.toolbox
        return (toolbox.end_outcome, toolbox.proposed_summary,
                self.metrics.summary(), self.run_client.policy_decisions)


def _build_live_pipeline(case: EvalCase, cfg: EvalConfig) -> _LivePipeline:
    return _LivePipeline(case, cfg)


async def run_case(case: EvalCase, cfg: EvalConfig) -> CaseRunResult:
    pipeline = _build_live_pipeline(case, cfg)
    sim_chat = cfg.sim_chat()
    judge_chat = cfg.judge_chat()
    sim = CalleeSimulator(sim_chat, case)
    transcript: list[tuple[str, str]] = []

    await pipeline.start()
    for utterance in await pipeline.agent_turn():  # disclosure (and any greeting)
        transcript.append(("assistant", utterance))
    for _ in range(case.max_turns):
        if getattr(pipeline, "ended", False) or sim.wants_hangup:
            break
        callee_text = await sim.next_turn(transcript)
        if not callee_text:
            break
        transcript.append(("callee", callee_text))
        await pipeline.inject(callee_text)
        for utterance in await pipeline.agent_turn():
            transcript.append(("assistant", utterance))
    end_outcome, summary, latency_summary, decisions = await pipeline.finish()

    approved_sensitive = _approved_sensitive(pipeline.run_client, case)

    axes = [
        score_policy(case, decisions, transcript, approved_sensitive=approved_sensitive),
        await score_success(case, end_outcome=end_outcome, summary=summary,
                            transcript=transcript, judge=judge_chat),
        await score_role(case, transcript, judge=judge_chat),
        AxisResult("latency", True, float(latency_summary.get("avg_turn_ms") or 0.0),
                   "LLM TTFB only - NOT end-to-end call latency: "
                   + json.dumps(latency_summary)),
        score_cost({
            sim_chat.model: (sim_chat.total_input_tokens, sim_chat.total_output_tokens),
            judge_chat.model: (judge_chat.total_input_tokens, judge_chat.total_output_tokens),
        }),
    ]

    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    artifact = cfg.out_dir / f"{case.name.replace('/', '__')}-{int(time.time())}.json"
    artifact.write_text(json.dumps({
        "case": case.name,
        "agent_model": cfg.agent_model,
        "transcript": transcript,
        "end_outcome": end_outcome,
        "summary": summary,
        "policy_decisions": decisions,
        "latency": latency_summary,
        "axes": [{"axis": a.axis, "passed": a.passed, "score": a.score,
                  "details": a.details} for a in axes],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return CaseRunResult(case.name, axes, transcript, artifact)
