"""Simulated call run (stage 1 stub).

Walks the fake lifecycle: running -> transcript -> policy check ->
approval request -> wait for resolution -> completed/aborted, pushing every
step through the internal API. Proves the whole control loop end-to-end
before any telephony exists (spec §6).
"""

from __future__ import annotations

import asyncio
import logging

import httpx
import redis.asyncio as aioredis

from assistant_policy import (
    ActionRequest,
    Decision,
    FactSensitivity,
    PolicyActionType,
    PolicyOutcome,
    TaskContext,
    evaluate,
)
from assistant_shared.events import RunEvent, RunEventType
from assistant_shared.queue import QueuedRun, wait_control
from assistant_shared.schemas import RunStatus, Speaker

from .events_client import RunClient
from .settings import WorkerSettings

logger = logging.getLogger(__name__)


async def fetch_task(http: httpx.AsyncClient, settings: WorkerSettings, task_id: str) -> dict:
    resp = await http.get(f"{settings.api_base_url}/tasks/{task_id}")
    resp.raise_for_status()
    return resp.json()


async def simulate_run(
    msg: QueuedRun,
    *,
    http: httpx.AsyncClient,
    redis: aioredis.Redis,
    settings: WorkerSettings,
) -> None:
    client = RunClient(http, settings, msg.run_id)
    task = await fetch_task(http, settings, msg.task_id)
    goal = task.get("structured_goal") or {}
    ctx = TaskContext(
        autonomy_level=int(goal.get("autonomy_level", 1)),
        scenario=goal.get("scenario", "generic"),
        allowed_facts=list(goal.get("allowed_facts", [])),
    )
    delay = settings.step_delay_s

    await client.status(RunStatus.running)
    await asyncio.sleep(delay)
    await client.say(1, Speaker.assistant, "Здравствуйте! Я ИИ-ассистент, звоню от имени клиента.")
    await client.say(2, Speaker.callee, "Здравствуйте, слушаю вас.")
    await asyncio.sleep(delay)
    await client.say(3, Speaker.assistant, f"Цель звонка: {goal.get('objective', task['title'])}")

    # The simulated sensitive moment: callee asks for personal data.
    decision: Decision = evaluate(
        ActionRequest(
            action=PolicyActionType.disclose_fact,
            detail="дата рождения",
            fact_sensitivity=FactSensitivity.medium,
        ),
        ctx,
    )
    await client.policy_decision(
        {
            "rule_id": decision.rule_id,
            "inputs_hash": decision.inputs_hash,
            "outcome": decision.type.value,
            "action": PolicyActionType.disclose_fact.value,
            "detail": "дата рождения",
            "scenario": ctx.scenario,
            "autonomy_level": ctx.autonomy_level,
        }
    )
    if decision.type == PolicyOutcome.deny:
        await client.send(
            RunEvent(type=RunEventType.run_failed, data={"failure_reason": decision.reason or "policy deny"})
        )
        return

    if decision.type == PolicyOutcome.require_approval:
        result = await client.send(
            RunEvent(
                type=RunEventType.approval_requested,
                data={
                    "kind": decision.approval_kind.value,
                    "question": decision.question,
                    "context": {"task_id": msg.task_id, "detail": "дата рождения"},
                },
            )
        )
        approval_id = result["approval_id"]
        logger.info("run %s waiting for approval %s", msg.run_id, approval_id)

        control = await wait_control(redis, msg.run_id, timeout=settings.approval_timeout_s)
        if control is None:
            await client.send(
                RunEvent(
                    type=RunEventType.run_failed,
                    data={"failure_reason": "approval timed out"},
                )
            )
            return
        if control.type == "cancel":
            logger.info("run %s cancelled while waiting", msg.run_id)
            return
        if control.status != "approved":
            await client.send(
                RunEvent(
                    type=RunEventType.run_failed,
                    data={"failure_reason": "approval rejected by user"},
                )
            )
            return
        await client.status(RunStatus.running)
        await client.say(4, Speaker.assistant, "Уточнил у клиента, передаю данные.")

    await asyncio.sleep(delay)
    await client.say(5, Speaker.callee, "Отлично, всё оформлено.")
    await client.send(
        RunEvent(
            type=RunEventType.run_completed,
            data={
                "result_summary": (
                    f"Симуляция звонка завершена. Цель: {goal.get('objective', task['title'])}. "
                    "Договорённость достигнута (заглушка stage 1)."
                ),
                "estimated_cost_cents": 0,
            },
        )
    )
