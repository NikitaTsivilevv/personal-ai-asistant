"""End-to-end control loop: queue -> worker simulation -> approval pause ->
resolve -> done (phase C checkpoint)."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from sqlalchemy import select

from assistant_db.models import AuditLog
from assistant_shared.queue import dequeue_run
from assistant_worker.settings import WorkerSettings
from assistant_worker.simulator import simulate_run


@pytest.fixture
def worker_settings() -> WorkerSettings:
    return WorkerSettings(
        _env_file=None,  # tests must not depend on the developer's .env
        api_base_url="http://test",
        internal_api_token="test-internal-token",
        approval_timeout_s=10,
        step_delay_s=0,
    )


async def _wait_for(predicate, timeout: float = 15.0):
    async with asyncio.timeout(timeout):
        while True:
            result = await predicate()
            if result is not None:
                return result
            await asyncio.sleep(0.05)


async def _pending_approval(client: httpx.AsyncClient, task_id: str):
    detail = (await client.get(f"/tasks/{task_id}")).json()
    for approval in detail["approvals"]:
        if approval["status"] == "pending":
            return approval
    return None


async def _run_e2e(client, fake_redis, worker_settings, task_payload, decision: str) -> dict:
    task = (await client.post("/tasks", json=task_payload)).json()
    await client.post(f"/tasks/{task['id']}/queue")

    msg = await dequeue_run(fake_redis, timeout=1)
    assert msg is not None and msg.task_id == task["id"]

    worker = asyncio.create_task(
        simulate_run(msg, http=client, redis=fake_redis, settings=worker_settings)
    )
    async def pending_or_worker_crash():
        if worker.done():
            if worker.exception() is not None:
                raise worker.exception()
            # Worker finished without ever pausing on an approval: fail fast
            # with the final state instead of polling until the timeout.
            detail = (await client.get(f"/tasks/{task['id']}")).json()
            raise AssertionError(f"worker finished without approval pause: {detail}")
        return await _pending_approval(client, task["id"])

    approval = await _wait_for(pending_or_worker_crash)
    resp = await client.post(
        f"/approvals/{approval['id']}/resolve",
        json={"decision": decision, "resolved_via": "telegram"},
    )
    assert resp.status_code == 200
    await asyncio.wait_for(worker, timeout=10)
    return (await client.get(f"/tasks/{task['id']}")).json()


async def test_full_lifecycle_with_approval(
    client, app, fake_redis, worker_settings, task_payload
):
    detail = await _run_e2e(client, fake_redis, worker_settings, task_payload, "approved")

    assert detail["status"] == "done"
    run = detail["runs"][0]
    assert run["status"] == "completed"
    assert "Симуляция звонка завершена" in run["result_summary"]
    assert detail["approvals"][0]["status"] == "approved"

    # Acceptance criterion 5: every transition is in audit_log.
    async with app.state.session_factory() as session:
        rows = await session.execute(select(AuditLog.event_type))
        events = {r for (r,) in rows}
    assert {
        "task.created",
        "task.queued",
        "run.status_changed",
        "run.transcript_segment",
        "run.approval_requested",
        "approval.resolved",
        "run.run_completed",
    } <= events


async def test_full_lifecycle_with_rejection(
    client, fake_redis, worker_settings, task_payload
):
    detail = await _run_e2e(client, fake_redis, worker_settings, task_payload, "rejected")

    assert detail["status"] == "failed"
    run = detail["runs"][0]
    assert run["status"] == "failed"
    assert "rejected" in run["failure_reason"]


async def test_high_autonomy_skips_approval(client, fake_redis, worker_settings, task_payload):
    task_payload["structured_goal"]["autonomy_level"] = 2
    task = (await client.post("/tasks", json=task_payload)).json()
    await client.post(f"/tasks/{task['id']}/queue")
    msg = await dequeue_run(fake_redis, timeout=1)

    await asyncio.wait_for(
        simulate_run(msg, http=client, redis=fake_redis, settings=worker_settings), timeout=10
    )
    detail = (await client.get(f"/tasks/{task['id']}")).json()
    assert detail["status"] == "done"
    assert detail["approvals"] == []
