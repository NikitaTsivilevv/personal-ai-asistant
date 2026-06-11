"""Policy engine stub (stage 1).

One entry point used by the voice worker before any sensitive action:

    evaluate(action, task_context) -> allow | require_approval(kind, question) | deny(reason)

Stage 1 ships a rule table keyed by autonomy level (TZ §4). Real rules grow in
EPIC-003. Safety baseline from AGENTS.md: financial, legal, medical, or
contract-changing actions require explicit approval regardless of autonomy
level until a future decision narrows that rule.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

from assistant_shared.schemas import ApprovalKind


class PolicyAction(str, enum.Enum):
    share_low_sensitivity_fact = "share_low_sensitivity_fact"
    share_medium_sensitivity_fact = "share_medium_sensitivity_fact"
    share_high_sensitivity_fact = "share_high_sensitivity_fact"
    book_appointment = "book_appointment"
    reschedule_appointment = "reschedule_appointment"
    cancel_service = "cancel_service"
    make_payment = "make_payment"
    change_contract = "change_contract"


class DecisionType(str, enum.Enum):
    allow = "allow"
    require_approval = "require_approval"
    deny = "deny"


@dataclass
class TaskContext:
    autonomy_level: int = 1  # 0-3, TZ §4
    allowed_facts: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)


@dataclass
class Decision:
    type: DecisionType
    approval_kind: ApprovalKind | None = None
    question: str | None = None
    reason: str | None = None

    @classmethod
    def allow(cls) -> Decision:
        return cls(type=DecisionType.allow)

    @classmethod
    def require_approval(cls, kind: ApprovalKind, question: str) -> Decision:
        return cls(type=DecisionType.require_approval, approval_kind=kind, question=question)

    @classmethod
    def deny(cls, reason: str) -> Decision:
        return cls(type=DecisionType.deny, reason=reason)


# Minimum autonomy level at which the action runs without approval.
# None = never autonomous in stage 1 (always requires approval).
_MIN_AUTONOMY: dict[PolicyAction, int | None] = {
    PolicyAction.share_low_sensitivity_fact: 1,
    PolicyAction.share_medium_sensitivity_fact: 2,
    PolicyAction.share_high_sensitivity_fact: None,
    PolicyAction.book_appointment: 2,
    PolicyAction.reschedule_appointment: 2,
    PolicyAction.cancel_service: 3,
    PolicyAction.make_payment: None,  # AGENTS.md safety rule
    PolicyAction.change_contract: None,  # AGENTS.md safety rule
}

_APPROVAL_KIND: dict[PolicyAction, ApprovalKind] = {
    PolicyAction.share_low_sensitivity_fact: ApprovalKind.sensitive_data,
    PolicyAction.share_medium_sensitivity_fact: ApprovalKind.sensitive_data,
    PolicyAction.share_high_sensitivity_fact: ApprovalKind.sensitive_data,
    PolicyAction.book_appointment: ApprovalKind.other,
    PolicyAction.reschedule_appointment: ApprovalKind.other,
    PolicyAction.cancel_service: ApprovalKind.cancellation,
    PolicyAction.make_payment: ApprovalKind.payment,
    PolicyAction.change_contract: ApprovalKind.other,
}

_QUESTIONS: dict[PolicyAction, str] = {
    PolicyAction.share_low_sensitivity_fact: "Разрешить передать собеседнику данные: {detail}?",
    PolicyAction.share_medium_sensitivity_fact: "Разрешить передать собеседнику данные: {detail}?",
    PolicyAction.share_high_sensitivity_fact: "Разрешить передать чувствительные данные: {detail}?",
    PolicyAction.book_appointment: "Подтвердить запись: {detail}?",
    PolicyAction.reschedule_appointment: "Подтвердить перенос: {detail}?",
    PolicyAction.cancel_service: "Подтвердить отмену: {detail}?",
    PolicyAction.make_payment: "Подтвердить оплату: {detail}?",
    PolicyAction.change_contract: "Подтвердить изменение условий: {detail}?",
}


def evaluate(action: PolicyAction, ctx: TaskContext, detail: str = "") -> Decision:
    if not 0 <= ctx.autonomy_level <= 3:
        return Decision.deny(f"invalid autonomy_level {ctx.autonomy_level}")

    min_level = _MIN_AUTONOMY[action]
    question = _QUESTIONS[action].format(detail=detail or "(без деталей)")

    if min_level is None or ctx.autonomy_level < min_level:
        return Decision.require_approval(_APPROVAL_KIND[action], question)
    return Decision.allow()
