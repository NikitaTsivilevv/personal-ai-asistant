"""Policy contract shared by the engine (packages/policy) and its callers (EPIC-003 spec §2).

The taxonomy and rule schema live here so the worker, api, and bot can talk
about policy decisions without importing the engine. Rules are data, not code:
the engine evaluates them; rule files live in ``assistant_policy/rules/``.
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, Field

from .schemas import ApprovalKind


class PolicyActionType(str, enum.Enum):
    """What the assistant proposes to do (spec §2 taxonomy)."""

    disclose_fact = "disclose_fact"
    commit_booking = "commit_booking"
    commit_change = "commit_change"
    commit_cancellation = "commit_cancellation"
    agree_payment = "agree_payment"
    share_contact = "share_contact"
    accept_terms = "accept_terms"
    end_call = "end_call"
    transfer = "transfer"
    say_sensitive = "say_sensitive"


class Scenario(str, enum.Enum):
    """Per-scenario rule profiles (spec §2). ``generic`` is the fallback."""

    generic = "generic"
    insurance = "insurance"
    doctor = "doctor"
    restaurant = "restaurant"
    info_gathering = "info_gathering"


class FactSensitivity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class PolicyOutcome(str, enum.Enum):
    allow = "allow"
    require_approval = "require_approval"
    deny = "deny"


class PolicyRule(BaseModel):
    """One declarative rule. First match wins within a rule file.

    Match fields left as None match anything. ``autonomy`` lists the levels
    the rule applies to (e.g. [0, 1] = only low-autonomy tasks).
    """

    id: str
    action: PolicyActionType
    autonomy: list[int] | None = None
    fact_sensitivity: list[FactSensitivity] | None = None
    outcome: PolicyOutcome
    approval_kind: ApprovalKind | None = None
    question_template: str | None = None  # {detail} placeholder
    deny_reason: str | None = None

    def matches(self, action: PolicyActionType, autonomy_level: int,
                fact_sensitivity: FactSensitivity | None) -> bool:
        if self.action != action:
            return False
        if self.autonomy is not None and autonomy_level not in self.autonomy:
            return False
        if self.fact_sensitivity is not None:
            if fact_sensitivity is None or fact_sensitivity not in self.fact_sensitivity:
                return False
        return True


class ScenarioRules(BaseModel):
    """One rule file: a scenario profile."""

    scenario: Scenario
    # Facts a task in this scenario may use even if the task did not list them.
    default_allowed_facts: list[str] = Field(default_factory=list)
    rules: list[PolicyRule] = Field(default_factory=list)


class ActionRequest(BaseModel):
    """What the worker asks the engine about."""

    action: PolicyActionType
    detail: str = ""
    fact_key: str | None = None  # for disclose_fact
    fact_sensitivity: FactSensitivity | None = None
