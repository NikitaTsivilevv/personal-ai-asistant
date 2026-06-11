"""Agent tools wired through the policy engine (EPIC-002 plan B3).

Uses the real API app (ASGI transport) so approval_requested events create
approval rows, and fakeredis for the control loop - same plumbing as stage 1.
"""

from __future__ import annotations

import asyncio

from assistant_shared.queue import ControlMessage, send_control
from assistant_shared.schemas import StructuredGoal
from assistant_worker.call.agent import AgentConfig
from assistant_worker.call.control import ControlRouter
from assistant_worker.call.tools import CallToolbox
from assistant_worker.events_client import RunClient
from assistant_worker.settings import WorkerSettings


def _worker_settings() -> WorkerSettings:
    return WorkerSettings(
        _env_file=None,  # tests must not depend on the developer's .env
        api_base_url="http://test",
        internal_api_token="test-internal-token",
        approval_timeout_s=5,
    )


async def _make_toolbox(client, fake_redis, task_payload, autonomy_level=1) -> CallToolbox:
    task_payload["structured_goal"]["autonomy_level"] = autonomy_level
    task = (await client.post("/tasks", json=task_payload)).json()
    detail = (await client.post(f"/tasks/{task['id']}/queue")).json()
    run_id = detail["runs"][0]["id"]
    goal = StructuredGoal.model_validate(task["structured_goal"])
    return CallToolbox(
        config=AgentConfig(goal=goal),
        run_client=RunClient(client, _worker_settings(), run_id),
        redis=fake_redis,
        run_id=run_id,
        approval_timeout_s=5,
    )


async def test_request_approval_approved(client, fake_redis, task_payload):
    toolbox = await _make_toolbox(client, fake_redis, task_payload)

    async def approve_soon():
        await asyncio.sleep(0.1)
        # The approval row exists by now; resolve it like the bot would.
        task_list = (await client.get("/tasks")).json()
        detail = (await client.get(f"/tasks/{task_list[0]['id']}")).json()
        approval = detail["approvals"][0]
        resp = await client.post(
            f"/approvals/{approval['id']}/resolve",
            json={"decision": "approved", "resolved_via": "telegram"},
        )
        assert resp.status_code == 200

    resolver = asyncio.create_task(approve_soon())
    result = await toolbox.request_approval("share_personal_data", "дата рождения")
    await resolver
    assert result["status"] == "approved"


async def test_request_approval_rejected(client, fake_redis, task_payload):
    toolbox = await _make_toolbox(client, fake_redis, task_payload)

    async def reject_soon():
        await asyncio.sleep(0.1)
        task_list = (await client.get("/tasks")).json()
        detail = (await client.get(f"/tasks/{task_list[0]['id']}")).json()
        await client.post(
            f"/approvals/{detail['approvals'][0]['id']}/resolve",
            json={"decision": "rejected", "resolved_via": "telegram"},
        )

    resolver = asyncio.create_task(reject_soon())
    result = await toolbox.request_approval("make_payment", "50 EUR")
    await resolver
    assert result["status"] == "rejected"


async def test_request_approval_allowed_by_policy_skips_approval(
    client, fake_redis, task_payload
):
    # Autonomy 2: booking allowed without approval.
    toolbox = await _make_toolbox(client, fake_redis, task_payload, autonomy_level=2)
    result = await toolbox.request_approval("book_appointment", "четверг 18:00")
    assert result["status"] == "approved"
    assert "no confirmation needed" in result["note"]


async def test_unknown_action_errors(client, fake_redis, task_payload):
    toolbox = await _make_toolbox(client, fake_redis, task_payload)
    result = await toolbox.request_approval("launch_rocket", "к луне")
    assert result["status"] == "error"


async def test_whisper_passthrough_during_wait(client, fake_redis, task_payload):
    toolbox = await _make_toolbox(client, fake_redis, task_payload)

    async def whisper_then_approve():
        await asyncio.sleep(0.1)
        await send_control(
            fake_redis, toolbox.run_id, ControlMessage(type="whisper", text="не дороже 50 евро")
        )
        await asyncio.sleep(0.1)
        task_list = (await client.get("/tasks")).json()
        detail = (await client.get(f"/tasks/{task_list[0]['id']}")).json()
        await client.post(
            f"/approvals/{detail['approvals'][0]['id']}/resolve",
            json={"decision": "approved", "resolved_via": "telegram"},
        )

    resolver = asyncio.create_task(whisper_then_approve())
    result = await toolbox.request_approval("share_personal_data", "адрес")
    await resolver
    assert result["status"] == "approved"
    assert "не дороже 50 евро" in toolbox.config.whispers


async def test_control_router_routes_messages(fake_redis):
    whispers: list[str] = []
    hangups: list[str] = []

    async def on_whisper(text: str) -> None:
        whispers.append(text)

    async def on_hangup(kind: str) -> None:
        hangups.append(kind)

    router = ControlRouter(fake_redis, "run-x", on_whisper=on_whisper, on_hangup=on_hangup)
    router.start()
    try:
        await send_control(fake_redis, "run-x", ControlMessage(type="whisper", text="тише"))
        await send_control(fake_redis, "run-x", ControlMessage(type="hangup"))
        await send_control(
            fake_redis, "run-x",
            ControlMessage(type="approval_resolved", approval_id="a1", status="approved"),
        )
        resolution = await router.wait_approval(timeout_s=5)
        assert resolution is not None
        assert resolution.approval_id == "a1"
        # Give the router loop a beat to drain callbacks.
        await asyncio.sleep(0.1)
        assert whispers == ["тише"]
        assert hangups == ["hangup"]
    finally:
        await router.stop()


async def test_denied_action_includes_callee_phrase(client, fake_redis, task_payload):
    """EPIC-003 spec §3: deny responses carry a callee-facing phrase."""
    task_payload["structured_goal"]["scenario"] = "insurance"
    toolbox = await _make_toolbox(client, fake_redis, task_payload, autonomy_level=3)
    result = await toolbox.request_approval("cancel_service", "закрыть страховое дело")
    assert result["status"] == "denied"
    assert result["reason"]
    assert result["say"]  # the agent has something polite to tell the callee


async def test_approval_expiry_returns_wrapup_and_marks_expired(
    client, fake_redis, task_payload
):
    """EPIC-003 B1: expiry -> graceful wrap-up instruction + approval row expired."""
    toolbox = await _make_toolbox(client, fake_redis, task_payload)
    toolbox.approval_timeout_s = 1

    result = await toolbox.request_approval("make_payment", "50 EUR")
    assert result["status"] == "expired"
    assert result["say"]
    assert "end_call" in result["instruction"]

    task_list = (await client.get("/tasks")).json()
    detail = (await client.get(f"/tasks/{task_list[0]['id']}")).json()
    assert detail["approvals"][0]["status"] == "expired"
    assert detail["approvals"][0]["resolved_via"] == "timeout"
    # The call resumes; the run is no longer blocked on the approval.
    assert detail["runs"][0]["status"] == "running"


async def test_policy_decisions_are_audited_with_rule_id(
    client, app, fake_redis, task_payload
):
    """EPIC-003 acceptance 5: every decision lands in audit_log with a rule id."""
    from sqlalchemy import select

    from assistant_db.models import AuditLog

    toolbox = await _make_toolbox(client, fake_redis, task_payload, autonomy_level=2)
    await toolbox.request_approval("book_appointment", "четверг 18:00")

    async with app.state.session_factory() as session:
        rows = (
            await session.execute(
                select(AuditLog).where(AuditLog.event_type == "run.policy_decision")
            )
        ).scalars().all()
    assert rows, "policy decision missing from audit_log"
    payload = rows[-1].payload
    assert payload["rule_id"]
    assert payload["inputs_hash"]
    assert payload["outcome"] == "allow"
    assert rows[-1].actor == "policy"


async def test_end_call_and_facts_and_summary_state(client, fake_redis, task_payload):
    toolbox = await _make_toolbox(client, fake_redis, task_payload)
    hangup_called = False

    async def fake_hangup():
        nonlocal hangup_called
        hangup_called = True

    toolbox.hangup = fake_hangup
    await toolbox.log_fact("Запись на четверг 18:00")
    await toolbox.propose_summary("Записал на четверг", next_steps="Прийти за 10 минут")
    result = await toolbox.end_call("achieved")
    assert result["status"] == "ok"
    assert hangup_called
    assert toolbox.logged_facts == ["Запись на четверг 18:00"]
    assert toolbox.end_outcome == "achieved"
