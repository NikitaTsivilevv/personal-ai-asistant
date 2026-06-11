"""Policy engine v1 (EPIC-003 spec §3).

The LLM proposes actions; this engine disposes. Rules are data
(``rules/*.json``, one file per scenario profile); the engine is the loader
plus a small deterministic evaluator:

    evaluate(request, ctx) -> Decision(allow | require_approval | deny)

Every decision carries the matched rule id and a hash of the inputs so the
caller can write an auditable trail (acceptance criterion 5).

Hard floor (D-7 / AGENTS.md safety rule), enforced in code so no rule file
can lower it: financial/legal/medical actions and high-sensitivity
disclosures never resolve to ``allow``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources

from assistant_shared.policy import (
    ActionRequest,
    FactSensitivity,
    PolicyActionType,
    PolicyOutcome,
    PolicyRule,
    Scenario,
    ScenarioRules,
)
from assistant_shared.schemas import ApprovalKind

# Actions that may never resolve to `allow`, regardless of rules (spec §2:
# "hard floor, not configurable down").
HARD_FLOOR_ACTIONS: frozenset[PolicyActionType] = frozenset(
    {
        PolicyActionType.agree_payment,
        PolicyActionType.accept_terms,
        PolicyActionType.say_sensitive,
    }
)

_FLOOR_APPROVAL_KIND: dict[PolicyActionType, ApprovalKind] = {
    PolicyActionType.agree_payment: ApprovalKind.payment,
    PolicyActionType.accept_terms: ApprovalKind.other,
    PolicyActionType.say_sensitive: ApprovalKind.sensitive_data,
}

_FLOOR_QUESTION = "Требуется подтверждение: {detail}?"


@dataclass
class TaskContext:
    autonomy_level: int = 1  # 0-3, TZ §4
    scenario: str = Scenario.generic.value
    allowed_facts: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)


@dataclass
class Decision:
    type: PolicyOutcome
    rule_id: str
    inputs_hash: str
    approval_kind: ApprovalKind | None = None
    question: str | None = None
    reason: str | None = None


@lru_cache(maxsize=1)
def load_rule_files() -> dict[str, ScenarioRules]:
    """Load and validate every rule file shipped with the package."""
    loaded: dict[str, ScenarioRules] = {}
    rules_dir = resources.files("assistant_policy").joinpath("rules")
    for entry in rules_dir.iterdir():
        if not entry.name.endswith(".json"):
            continue
        profile = ScenarioRules.model_validate(json.loads(entry.read_text(encoding="utf-8")))
        loaded[profile.scenario.value] = profile
    if Scenario.generic.value not in loaded:
        raise RuntimeError("policy rules misconfigured: generic.json missing")
    return loaded


def scenario_profile(scenario: str) -> ScenarioRules:
    profiles = load_rule_files()
    return profiles.get(scenario, profiles[Scenario.generic.value])


def default_allowed_facts(scenario: str) -> list[str]:
    return list(scenario_profile(scenario).default_allowed_facts)


def _inputs_hash(request: ActionRequest, ctx: TaskContext) -> str:
    canonical = json.dumps(
        {
            "action": request.action.value,
            "detail": request.detail,
            "fact_key": request.fact_key,
            "fact_sensitivity": (
                request.fact_sensitivity.value if request.fact_sensitivity else None
            ),
            "scenario": ctx.scenario,
            "autonomy_level": ctx.autonomy_level,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _match(rules: list[PolicyRule], request: ActionRequest, ctx: TaskContext) -> PolicyRule | None:
    for rule in rules:
        if rule.matches(request.action, ctx.autonomy_level, request.fact_sensitivity):
            return rule
    return None


def evaluate(request: ActionRequest, ctx: TaskContext) -> Decision:
    """Deterministic outcome for every (scenario, action, autonomy, sensitivity)."""
    inputs_hash = _inputs_hash(request, ctx)

    if not 0 <= ctx.autonomy_level <= 3:
        return Decision(
            type=PolicyOutcome.deny,
            rule_id="code-invalid-autonomy",
            inputs_hash=inputs_hash,
            reason=f"invalid autonomy_level {ctx.autonomy_level}",
        )

    # Fact access control (spec §2): a fact must be allowed by the task or by
    # the scenario profile before disclose_fact is even considered.
    if request.action == PolicyActionType.disclose_fact and request.fact_key:
        allowed = set(ctx.allowed_facts) | set(default_allowed_facts(ctx.scenario))
        if request.fact_key not in allowed:
            return Decision(
                type=PolicyOutcome.deny,
                rule_id="code-fact-not-allowed",
                inputs_hash=inputs_hash,
                reason=f"fact {request.fact_key!r} is not allowed for this task",
            )

    profile = scenario_profile(ctx.scenario)
    generic = scenario_profile(Scenario.generic.value)
    rule = _match(profile.rules, request, ctx)
    if rule is None and profile is not generic:
        rule = _match(generic.rules, request, ctx)

    if rule is None:
        # Unmatched actions escalate rather than slip through.
        decision = Decision(
            type=PolicyOutcome.require_approval,
            rule_id="code-default-escalate",
            inputs_hash=inputs_hash,
            approval_kind=ApprovalKind.other,
            question=_FLOOR_QUESTION.format(detail=request.detail or request.action.value),
        )
    else:
        question = None
        if rule.question_template:
            question = rule.question_template.format(detail=request.detail or "(без деталей)")
        decision = Decision(
            type=rule.outcome,
            rule_id=rule.id,
            inputs_hash=inputs_hash,
            approval_kind=rule.approval_kind,
            question=question,
            reason=rule.deny_reason,
        )

    return _apply_hard_floor(decision, request)


def _apply_hard_floor(decision: Decision, request: ActionRequest) -> Decision:
    if decision.type != PolicyOutcome.allow:
        return decision
    floored = request.action in HARD_FLOOR_ACTIONS or (
        request.action == PolicyActionType.disclose_fact
        and request.fact_sensitivity == FactSensitivity.high
    )
    if not floored:
        return decision
    kind = _FLOOR_APPROVAL_KIND.get(request.action, ApprovalKind.sensitive_data)
    return Decision(
        type=PolicyOutcome.require_approval,
        rule_id=f"code-hard-floor({decision.rule_id})",
        inputs_hash=decision.inputs_hash,
        approval_kind=kind,
        question=_FLOOR_QUESTION.format(detail=request.detail or request.action.value),
    )
