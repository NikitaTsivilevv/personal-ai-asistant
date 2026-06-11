"""Matrix tests for policy engine v1 (EPIC-003 acceptance criterion 1)."""

import pytest

from assistant_policy import (
    ActionRequest,
    FactSensitivity,
    PolicyActionType,
    PolicyOutcome,
    TaskContext,
    default_allowed_facts,
    evaluate,
)
from assistant_policy.engine import HARD_FLOOR_ACTIONS, load_rule_files

SCENARIOS = ["generic", "insurance", "doctor", "restaurant", "info_gathering", "unknown"]
LEVELS = [0, 1, 2, 3]
SENSITIVITIES = [FactSensitivity.low, FactSensitivity.medium, FactSensitivity.high]


def _requests_for(action: PolicyActionType) -> list[ActionRequest]:
    if action == PolicyActionType.disclose_fact:
        return [
            ActionRequest(action=action, detail="тест", fact_key="имя", fact_sensitivity=s)
            for s in SENSITIVITIES
        ]
    return [ActionRequest(action=action, detail="тест")]


def test_full_matrix_is_deterministic_and_complete():
    """Every (scenario x action x autonomy x sensitivity) has a decision with a rule id."""
    for scenario in SCENARIOS:
        for level in LEVELS:
            ctx = TaskContext(autonomy_level=level, scenario=scenario, allowed_facts=["имя"])
            for action in PolicyActionType:
                for request in _requests_for(action):
                    decision = evaluate(request, ctx)
                    assert decision.type in PolicyOutcome
                    assert decision.rule_id, (scenario, level, action)
                    assert decision.inputs_hash
                    # Same inputs -> same outcome (deterministic).
                    again = evaluate(request, ctx)
                    assert again.type == decision.type
                    assert again.rule_id == decision.rule_id
                    if decision.type == PolicyOutcome.require_approval:
                        assert decision.approval_kind is not None
                        assert decision.question
                    if decision.type == PolicyOutcome.deny:
                        assert decision.reason


def test_hard_floor_actions_never_allow():
    """Acceptance criterion 1: financial/legal/medical can never resolve to allow."""
    for scenario in SCENARIOS:
        for level in LEVELS:
            ctx = TaskContext(autonomy_level=level, scenario=scenario, allowed_facts=["имя"])
            for action in HARD_FLOOR_ACTIONS:
                decision = evaluate(ActionRequest(action=action, detail="50 EUR"), ctx)
                assert decision.type != PolicyOutcome.allow, (scenario, level, action)
            high_disclosure = ActionRequest(
                action=PolicyActionType.disclose_fact,
                detail="диагноз",
                fact_key="имя",
                fact_sensitivity=FactSensitivity.high,
            )
            assert evaluate(high_disclosure, ctx).type != PolicyOutcome.allow


def test_fact_not_allowed_is_denied():
    ctx = TaskContext(autonomy_level=3, scenario="generic", allowed_facts=["имя"])
    request = ActionRequest(
        action=PolicyActionType.disclose_fact,
        detail="номер DNI",
        fact_key="DNI",
        fact_sensitivity=FactSensitivity.low,
    )
    decision = evaluate(request, ctx)
    assert decision.type == PolicyOutcome.deny
    assert decision.rule_id == "code-fact-not-allowed"


def test_scenario_default_facts_extend_task_facts():
    # "номер полиса" comes from the insurance profile, not the task.
    ctx = TaskContext(autonomy_level=2, scenario="insurance", allowed_facts=[])
    request = ActionRequest(
        action=PolicyActionType.disclose_fact,
        detail="номер полиса",
        fact_key="номер полиса",
        fact_sensitivity=FactSensitivity.medium,
    )
    assert evaluate(request, ctx).type == PolicyOutcome.allow
    assert "номер полиса" in default_allowed_facts("insurance")


def test_insurance_acceptance_scenario():
    """Acceptance criterion 2: share policy number, refuse claim closure, escalate payment."""
    ctx = TaskContext(autonomy_level=2, scenario="insurance", allowed_facts=["номер полиса"])

    share = ActionRequest(
        action=PolicyActionType.disclose_fact,
        detail="номер полиса",
        fact_key="номер полиса",
        fact_sensitivity=FactSensitivity.medium,
    )
    assert evaluate(share, ctx).type == PolicyOutcome.allow

    close = ActionRequest(action=PolicyActionType.commit_cancellation, detail="закрыть дело")
    decision = evaluate(close, ctx)
    assert decision.type == PolicyOutcome.deny
    assert decision.rule_id == "ins-cancel-deny"

    pay = ActionRequest(action=PolicyActionType.agree_payment, detail="платная услуга 30 EUR")
    decision = evaluate(pay, ctx)
    assert decision.type == PolicyOutcome.require_approval
    assert decision.approval_kind.value == "payment"


def test_restaurant_level1_booking_needs_no_approval():
    """Stage-3 plan D1: restaurant level 1 is the no-approval path."""
    ctx = TaskContext(autonomy_level=1, scenario="restaurant", allowed_facts=[])
    booking = ActionRequest(action=PolicyActionType.commit_booking, detail="столик на двоих")
    assert evaluate(booking, ctx).type == PolicyOutcome.allow


def test_doctor_medical_data_requires_approval():
    ctx = TaskContext(autonomy_level=3, scenario="doctor", allowed_facts=["дата рождения"])
    request = ActionRequest(
        action=PolicyActionType.disclose_fact,
        detail="дата рождения",
        fact_key="дата рождения",
        fact_sensitivity=FactSensitivity.medium,
    )
    decision = evaluate(request, ctx)
    assert decision.type == PolicyOutcome.require_approval
    assert decision.rule_id == "doc-disclose-medical"


def test_level0_commits_escalate_not_allow():
    ctx = TaskContext(autonomy_level=0, scenario="generic", allowed_facts=[])
    for action in (
        PolicyActionType.commit_booking,
        PolicyActionType.commit_change,
        PolicyActionType.commit_cancellation,
    ):
        decision = evaluate(ActionRequest(action=action, detail="тест"), ctx)
        assert decision.type == PolicyOutcome.require_approval, action


def test_invalid_autonomy_denied():
    decision = evaluate(
        ActionRequest(action=PolicyActionType.commit_booking),
        TaskContext(autonomy_level=7),
    )
    assert decision.type == PolicyOutcome.deny


def test_unknown_scenario_falls_back_to_generic():
    ctx_unknown = TaskContext(autonomy_level=1, scenario="unknown")
    ctx_generic = TaskContext(autonomy_level=1, scenario="generic")
    request = ActionRequest(action=PolicyActionType.commit_booking, detail="тест")
    assert evaluate(request, ctx_unknown).rule_id == evaluate(request, ctx_generic).rule_id


def test_rule_files_load_and_have_unique_ids():
    profiles = load_rule_files()
    assert {"generic", "insurance", "doctor", "restaurant", "info_gathering"} <= set(profiles)
    seen: set[str] = set()
    for profile in profiles.values():
        for rule in profile.rules:
            assert rule.id not in seen, f"duplicate rule id {rule.id}"
            seen.add(rule.id)


@pytest.mark.parametrize("scenario", ["generic", "restaurant"])
def test_inputs_hash_varies_with_context(scenario):
    request = ActionRequest(action=PolicyActionType.commit_booking, detail="тест")
    h1 = evaluate(request, TaskContext(autonomy_level=1, scenario=scenario)).inputs_hash
    h2 = evaluate(request, TaskContext(autonomy_level=2, scenario=scenario)).inputs_hash
    assert h1 != h2
