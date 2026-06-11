"""Task lifecycle endpoints + audit trail (plan B2)."""

from __future__ import annotations

import httpx
from sqlalchemy import select

from assistant_db.models import AuditLog
from assistant_shared.queue import TASK_QUEUE_KEY, QueuedRun


async def _audit_types(app) -> list[str]:
    async with app.state.session_factory() as session:
        rows = await session.execute(select(AuditLog.event_type).order_by(AuditLog.created_at))
        return [r for (r,) in rows]


async def test_health(client: httpx.AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_create_and_get_task(client: httpx.AsyncClient, app, task_payload):
    resp = await client.post("/tasks", json=task_payload)
    assert resp.status_code == 201
    task = resp.json()
    assert task["status"] == "ready"
    assert task["structured_goal"]["autonomy_level"] == 1

    resp = await client.get(f"/tasks/{task['id']}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["runs"] == []
    assert detail["approvals"] == []

    resp = await client.get("/tasks")
    assert len(resp.json()) == 1

    assert "task.created" in await _audit_types(app)


async def test_queue_task_creates_run_and_redis_message(
    client: httpx.AsyncClient, app, fake_redis, task_payload
):
    task = (await client.post("/tasks", json=task_payload)).json()
    resp = await client.post(f"/tasks/{task['id']}/queue")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["status"] == "queued"
    assert len(detail["runs"]) == 1
    run = detail["runs"][0]
    assert run["status"] == "queued"
    assert run["attempt_no"] == 1

    raw = await fake_redis.rpop(TASK_QUEUE_KEY)
    msg = QueuedRun.model_validate_json(raw)
    assert msg.run_id == run["id"]
    assert msg.task_id == task["id"]

    # Double-queue while already queued is rejected.
    resp = await client.post(f"/tasks/{task['id']}/queue")
    assert resp.status_code == 409

    assert "task.queued" in await _audit_types(app)


async def test_cancel_queued_task(client: httpx.AsyncClient, app, task_payload):
    task = (await client.post("/tasks", json=task_payload)).json()
    await client.post(f"/tasks/{task['id']}/queue")
    resp = await client.post(f"/tasks/{task['id']}/cancel")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["status"] == "cancelled"
    assert detail["runs"][0]["status"] == "aborted"
    assert "task.cancelled" in await _audit_types(app)


async def test_cancel_done_task_rejected(client: httpx.AsyncClient, task_payload):
    task = (await client.post("/tasks", json=task_payload)).json()
    resp = await client.post(f"/tasks/{task['id']}/cancel")
    assert resp.status_code == 409


async def test_get_missing_task_404(client: httpx.AsyncClient):
    resp = await client.get("/tasks/nonexistent")
    assert resp.status_code == 404
