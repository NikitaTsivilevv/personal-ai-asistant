"""Stage 2 API surface: twilio webhook, hangup/whisper, stale-run sweeper."""

from __future__ import annotations

from sqlalchemy import select, update

from assistant_db.models import AuditLog
from assistant_shared.queue import ControlMessage, run_control_key
from assistant_api.sweeper import sweep_stale_runs


async def _queued_run(client, task_payload) -> tuple[str, str]:
    task = (await client.post("/tasks", json=task_payload)).json()
    detail = (await client.post(f"/tasks/{task['id']}/queue")).json()
    return task["id"], detail["runs"][0]["id"]


async def _running(client, internal_headers, run_id):
    resp = await client.post(
        f"/internal/runs/{run_id}/events",
        json={"type": "status_changed", "data": {"status": "running"}},
        headers=internal_headers,
    )
    assert resp.status_code == 200


async def test_twilio_webhook_audits_status(client, app, task_payload):
    _, run_id = await _queued_run(client, task_payload)
    resp = await client.post(
        f"/webhooks/twilio/status?run_id={run_id}",
        data={"CallSid": "CA123", "CallStatus": "in-progress"},
    )
    assert resp.status_code == 200

    async with app.state.session_factory() as session:
        rows = (
            await session.execute(
                select(AuditLog).where(AuditLog.event_type == "telephony.status")
            )
        ).scalars().all()
    assert len(rows) == 1
    assert rows[0].payload["call_sid"] == "CA123"
    assert rows[0].task_run_id == run_id


async def test_twilio_webhook_unknown_run_404(client):
    resp = await client.post(
        "/webhooks/twilio/status?run_id=missing", data={"CallStatus": "busy"}
    )
    assert resp.status_code == 404


async def test_hangup_sends_control_and_audits(
    client, app, fake_redis, internal_headers, task_payload
):
    _, run_id = await _queued_run(client, task_payload)
    await _running(client, internal_headers, run_id)

    resp = await client.post(f"/runs/{run_id}/hangup")
    assert resp.status_code == 200

    raw = await fake_redis.rpop(run_control_key(run_id))
    msg = ControlMessage.model_validate_json(raw)
    assert msg.type == "hangup"

    async with app.state.session_factory() as session:
        rows = (
            await session.execute(
                select(AuditLog).where(AuditLog.event_type == "run.hangup_requested")
            )
        ).scalars().all()
    assert len(rows) == 1


async def test_whisper_sends_text(client, fake_redis, internal_headers, task_payload):
    _, run_id = await _queued_run(client, task_payload)
    await _running(client, internal_headers, run_id)

    resp = await client.post(f"/runs/{run_id}/whisper", json={"text": "не дороже 50 евро"})
    assert resp.status_code == 200

    raw = await fake_redis.rpop(run_control_key(run_id))
    msg = ControlMessage.model_validate_json(raw)
    assert msg.type == "whisper"
    assert msg.text == "не дороже 50 евро"


async def test_hangup_rejected_for_inactive_run(client, task_payload):
    _, run_id = await _queued_run(client, task_payload)  # still queued, not running
    resp = await client.post(f"/runs/{run_id}/hangup")
    assert resp.status_code == 409


async def test_sweeper_fails_silent_runs(client, app, fake_redis, internal_headers, task_payload):
    task_id, run_id = await _queued_run(client, task_payload)
    await _running(client, internal_headers, run_id)

    # Age all audit events for this run far into the past.
    async with app.state.session_factory() as session:
        from datetime import UTC, datetime, timedelta

        await session.execute(
            update(AuditLog)
            .where(AuditLog.task_run_id == run_id)
            .values(created_at=datetime.now(UTC) - timedelta(hours=1))
        )
        await session.commit()

    async with app.state.session_factory() as session:
        swept = await sweep_stale_runs(session, fake_redis, stale_after_s=600)
    assert swept == [run_id]

    detail = (await client.get(f"/tasks/{task_id}")).json()
    assert detail["status"] == "failed"
    assert detail["runs"][0]["status"] == "failed"
    assert "silent" in detail["runs"][0]["failure_reason"]


async def test_sweeper_leaves_fresh_runs(client, app, fake_redis, internal_headers, task_payload):
    task_id, run_id = await _queued_run(client, task_payload)
    await _running(client, internal_headers, run_id)

    async with app.state.session_factory() as session:
        swept = await sweep_stale_runs(session, fake_redis, stale_after_s=600)
    assert swept == []

    detail = (await client.get(f"/tasks/{task_id}")).json()
    assert detail["status"] == "running"
