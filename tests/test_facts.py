"""Profile facts: CRUD API, scenario-aware agent allowlist, policy ctx (EPIC-003 B2)."""

from __future__ import annotations

from sqlalchemy import select

from assistant_db.models import AuditLog
from assistant_shared.schemas import StructuredGoal
from assistant_worker.call.agent import AgentConfig, ProfileFactView, allowed_facts


async def test_facts_crud_and_audit(client, app):
    created = (
        await client.post(
            "/facts",
            json={
                "key": "дата рождения",
                "value": "12.05.1990",
                "sensitivity": "high",
                "allowed_scenarios": ["doctor"],
            },
        )
    ).json()
    assert created["allowed_scenarios"] == ["doctor"]

    # Upsert by key updates in place.
    updated = (
        await client.post(
            "/facts",
            json={"key": "дата рождения", "value": "13.05.1990", "sensitivity": "high"},
        )
    ).json()
    assert updated["id"] == created["id"]
    assert updated["value"] == "13.05.1990"

    facts = (await client.get("/facts")).json()
    assert len(facts) == 1

    resp = await client.delete("/facts/дата рождения")
    assert resp.status_code == 204
    assert (await client.get("/facts")).json() == []
    assert (await client.delete("/facts/дата рождения")).status_code == 404

    # Audit entries exist and never contain the fact value (sensitive).
    async with app.state.session_factory() as session:
        rows = (
            await session.execute(
                select(AuditLog).where(AuditLog.event_type.like("fact.%"))
            )
        ).scalars().all()
    assert {r.event_type for r in rows} == {"fact.created", "fact.updated", "fact.deleted"}
    for row in rows:
        assert "12.05.1990" not in str(row.payload)
        assert "13.05.1990" not in str(row.payload)


def _config(scenario: str, task_whitelist: list[str] | None = None) -> AgentConfig:
    return AgentConfig(
        goal=StructuredGoal(
            objective="тест",
            scenario=scenario,
            allowed_facts=task_whitelist or [],
        ),
        facts=[
            ProfileFactView(key="имя", value="Никита", allowed_by_default=True),
            ProfileFactView(
                key="дата рождения",
                value="12.05.1990",
                sensitivity="high",
                allowed_scenarios=["doctor"],
            ),
            ProfileFactView(key="номер полиса", value="AB-1", allowed_scenarios=["insurance"]),
        ],
    )


def test_scenario_facts_visible_only_in_their_scenario():
    doctor_keys = {f.key for f in allowed_facts(_config("doctor"))}
    assert doctor_keys == {"имя", "дата рождения"}

    restaurant_keys = {f.key for f in allowed_facts(_config("restaurant"))}
    assert restaurant_keys == {"имя"}

    # Per-task whitelist still works regardless of scenario.
    whitelisted = {f.key for f in allowed_facts(_config("restaurant", ["номер полиса"]))}
    assert "номер полиса" in whitelisted


def test_policy_ctx_matches_prompt_allowlist(fake_redis):
    from assistant_worker.call.tools import CallToolbox

    toolbox = CallToolbox(
        config=_config("doctor"),
        run_client=None,
        redis=fake_redis,
        run_id="run-1",
    )
    ctx = toolbox._policy_ctx()
    assert "дата рождения" in ctx.allowed_facts
    assert "имя" in ctx.allowed_facts
    assert "номер полиса" not in ctx.allowed_facts
    assert ctx.scenario == "doctor"
