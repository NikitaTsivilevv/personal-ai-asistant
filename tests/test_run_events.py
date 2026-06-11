"""Internal event ingestion, approvals, and event bus (plan B3)."""

from __future__ import annotations

import asyncio
import json

import httpx
from sqlalchemy import select

from assistant_db.models import TranscriptSegment
from assistant_shared.queue import EVENTS_CHANNEL, ControlMessage, run_control_key


async def _queued_run(client: httpx.AsyncClient, task_payload) -> tuple[str, str]:
    task = (await client.post("/tasks", json=task_payload)).json()
    detail = (await client.post(f"/tasks/{task['id']}/queue")).json()
    return task["id"], detail["runs"][0]["id"]


async def _send_event(
    client: httpx.AsyncClient, run_id: str, headers: dict, type_: str, data: dict
) -> httpx.Response:
    return await client.post(
        f"/internal/runs/{run_id}/events", json={"type": type_, "data": data}, headers=headers
    )


async def test_internal_token_required(client, task_payload):
    _, run_id = await _queued_run(client, task_payload)
    resp = await client.post(
        f"/internal/runs/{run_id}/events",
        json={"type": "status_changed", "data": {"status": "running"}},
    )
    assert resp.status_code == 401


async def test_status_change_updates_run_and_task(client, internal_headers, task_payload):
    task_id, run_id = await _queued_run(client, task_payload)
    resp = await _send_event(client, run_id, internal_headers, "status_changed", {"status": "running"})
    assert resp.status_code == 200

    detail = (await client.get(f"/tasks/{task_id}")).json()
    assert detail["status"] == "running"
    assert detail["runs"][0]["status"] == "running"
    assert detail["runs"][0]["started_at"] is not None


async def test_transcript_segments_persisted(client, app, internal_headers, task_payload):
    _, run_id = await _queued_run(client, task_payload)
    for seq, text in enumerate(["Здравствуйте!", "Слушаю вас."], start=1):
        resp = await _send_event(
            client,
            run_id,
            internal_headers,
            "transcript_segment",
            {"seq": seq, "speaker": "assistant", "text": text, "ts_ms": seq * 1000},
        )
        assert resp.status_code == 200

    async with app.state.session_factory() as session:
        rows = (
            (await session.execute(select(TranscriptSegment).order_by(TranscriptSegment.seq)))
            .scalars()
            .all()
        )
    assert [r.text for r in rows] == ["Здравствуйте!", "Слушаю вас."]


async def test_approval_request_and_resolution(client, app, fake_redis, internal_headers, task_payload):
    task_id, run_id = await _queued_run(client, task_payload)
    resp = await _send_event(
        client,
        run_id,
        internal_headers,
        "approval_requested",
        {"kind": "sensitive_data", "question": "Передать дату рождения?", "context": {}},
    )
    assert resp.status_code == 200
    approval_id = resp.json()["approval_id"]

    detail = (await client.get(f"/tasks/{task_id}")).json()
    assert detail["status"] == "waiting_approval"
    assert detail["approvals"][0]["status"] == "pending"

    resp = await client.post(
        f"/approvals/{approval_id}/resolve",
        json={"decision": "approved", "resolved_via": "telegram"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "approved"
    assert body["resolved_via"] == "telegram"

    # Worker gets unblocked via the control list.
    raw = await fake_redis.rpop(run_control_key(run_id))
    control = ControlMessage.model_validate_json(raw)
    assert control.type == "approval_resolved"
    assert control.approval_id == approval_id
    assert control.status == "approved"

    # Double resolution is rejected.
    resp = await client.post(
        f"/approvals/{approval_id}/resolve",
        json={"decision": "rejected", "resolved_via": "telegram"},
    )
    assert resp.status_code == 409


async def test_run_completed_finishes_task(client, internal_headers, task_payload):
    task_id, run_id = await _queued_run(client, task_payload)
    resp = await _send_event(
        client,
        run_id,
        internal_headers,
        "run_completed",
        {"result_summary": "Записал на четверг 18:00", "estimated_cost_cents": 42},
    )
    assert resp.status_code == 200
    detail = (await client.get(f"/tasks/{task_id}")).json()
    assert detail["status"] == "done"
    run = detail["runs"][0]
    assert run["status"] == "completed"
    assert run["result_summary"] == "Записал на четверг 18:00"
    assert run["estimated_cost_cents"] == 42


async def test_event_published_to_bus(client, fake_redis, internal_headers, task_payload):
    _, run_id = await _queued_run(client, task_payload)
    pubsub = fake_redis.pubsub()
    await pubsub.subscribe(EVENTS_CHANNEL)

    await _send_event(client, run_id, internal_headers, "status_changed", {"status": "running"})

    async def next_data_message():
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
            if msg is not None:
                return msg

    msg = await asyncio.wait_for(next_data_message(), timeout=5)
    payload = json.loads(msg["data"])
    assert payload["type"] == "status_changed"
    assert payload["run_id"] == run_id
    await pubsub.aclose()


async def test_event_for_unknown_run_404(client, internal_headers):
    resp = await _send_event(client, "missing", internal_headers, "status_changed", {"status": "running"})
    assert resp.status_code == 404
