"""Call-mode orchestration: claim queued run, dial out, hand the media stream
to the pipeline, retry on busy/no-answer, finish with a summary event.

Coordination: the queue consumer dials and then waits on a per-run future; the
WebSocket handler (Twilio connects back with run_id in stream params) resolves
it by running the pipeline and reporting the outcome.
"""

from __future__ import annotations

import asyncio
import logging

import httpx
import redis.asyncio as aioredis

from assistant_shared.queue import QueuedRun
from assistant_shared.schemas import RunStatus, StructuredGoal

from ..events_client import RunClient
from ..settings import WorkerSettings
from .agent import AgentConfig, resolve_language
from .metrics import MetricsCollector
from .retry import RetryPolicy
from .state import CallState
from .summary import generate_summary
from .tools import CallToolbox
from .twilio_client import start_outbound_call

logger = logging.getLogger(__name__)

# How long we wait for Twilio to open the media stream before treating the
# attempt as no-answer. Status callbacks land in the API for the audit trail;
# finer outcome routing (busy vs no-answer) is a provisioning-session TODO.
CONNECT_TIMEOUT_S = 60


class CallRegistry:
    """run_id -> future resolved with (final_state, toolbox, metrics) by the ws handler."""

    def __init__(self) -> None:
        self._futures: dict[str, asyncio.Future] = {}
        self._contexts: dict[str, dict] = {}

    def register(self, run_id: str, context: dict) -> asyncio.Future:
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._futures[run_id] = future
        self._contexts[run_id] = context
        return future

    def context(self, run_id: str) -> dict | None:
        return self._contexts.get(run_id)

    def resolve(self, run_id: str, result) -> None:
        future = self._futures.get(run_id)
        if future is not None and not future.done():
            future.set_result(result)

    def fail(self, run_id: str, exc: BaseException) -> None:
        future = self._futures.get(run_id)
        if future is not None and not future.done():
            future.set_exception(exc)

    def cleanup(self, run_id: str) -> None:
        self._futures.pop(run_id, None)
        self._contexts.pop(run_id, None)


async def fetch_task(http: httpx.AsyncClient, settings: WorkerSettings, task_id: str) -> dict:
    resp = await http.get(f"{settings.api_base_url}/tasks/{task_id}")
    resp.raise_for_status()
    return resp.json()


def agent_config_from_task(task: dict) -> AgentConfig:
    goal = StructuredGoal.model_validate(task.get("structured_goal") or {})
    language = resolve_language(task.get("language_pref"), task.get("target_phone"))
    return AgentConfig(goal=goal, language=language, target_name=task.get("target_name"))


async def run_call(
    msg: QueuedRun,
    *,
    http: httpx.AsyncClient,
    redis: aioredis.Redis,
    settings: WorkerSettings,
    registry: CallRegistry,
) -> None:
    run_client = RunClient(http, settings, msg.run_id)
    task = await fetch_task(http, settings, msg.task_id)
    if not task.get("target_phone"):
        await run_client.failed("task has no target_phone")
        return

    config = agent_config_from_task(task)
    policy = RetryPolicy(
        max_attempts=settings.retry_max_attempts, base_delay_s=settings.retry_base_delay_s
    )

    attempt = 0
    while True:
        attempt += 1
        outcome, toolbox, metrics = await _attempt_call(
            msg, config=config, run_client=run_client, redis=redis,
            settings=settings, registry=registry, http=http,
        )
        if outcome == CallState.ended:
            transcript = getattr(toolbox, "transcript_log", []) if toolbox else []
            summary = (
                await generate_summary(
                    toolbox, transcript, anthropic_api_key=settings.anthropic_api_key
                )
                if toolbox
                else "Звонок завершён."
            )
            await run_client.completed(
                summary, metrics=metrics.summary() if metrics else None
            )
            return
        if policy.should_retry(outcome, attempt):
            delay = policy.delay_s(attempt)
            logger.info(
                "run %s attempt %d ended %s; retrying in %.0fs", msg.run_id, attempt,
                outcome.value, delay,
            )
            await run_client.status(RunStatus.queued, call_state=f"retry_wait:{outcome.value}")
            await asyncio.sleep(delay)
            continue
        await run_client.failed(
            f"call ended in state {outcome.value} after {attempt} attempt(s)",
            metrics=metrics.summary() if metrics else None,
        )
        return


async def _attempt_call(
    msg: QueuedRun,
    *,
    config: AgentConfig,
    run_client: RunClient,
    redis: aioredis.Redis,
    settings: WorkerSettings,
    registry: CallRegistry,
    http: httpx.AsyncClient,
) -> tuple[CallState, CallToolbox | None, MetricsCollector | None]:
    future = registry.register(
        msg.run_id,
        {
            "config": config,
            "run_client": run_client,
            "settings": settings,
            "redis": redis,
        },
    )
    try:
        await run_client.status(RunStatus.running, call_state=CallState.dialing.value)
        call_sid = await start_outbound_call(
            settings,
            to_number=(await fetch_task(http, settings, msg.task_id))["target_phone"],
            run_id=msg.run_id,
            task_id=msg.task_id,
            status_callback_url=f"{settings.api_base_url}/webhooks/twilio/status?run_id={msg.run_id}",
            http=http,
        )
        logger.info("run %s dialing, call_sid=%s", msg.run_id, call_sid)
        try:
            return await asyncio.wait_for(future, timeout=CONNECT_TIMEOUT_S + 600)
        except TimeoutError:
            return CallState.no_answer, None, None
    finally:
        registry.cleanup(msg.run_id)
