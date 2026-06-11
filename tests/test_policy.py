"""Policy engine rule table (plan C2)."""

from assistant_policy import PolicyAction, TaskContext, evaluate
from assistant_policy.engine import DecisionType
from assistant_shared.schemas import ApprovalKind


def test_level0_requires_approval_for_everything():
    ctx = TaskContext(autonomy_level=0)
    for action in PolicyAction:
        decision = evaluate(action, ctx)
        assert decision.type == DecisionType.require_approval, action


def test_level1_allows_low_sensitivity_facts():
    ctx = TaskContext(autonomy_level=1)
    assert evaluate(PolicyAction.share_low_sensitivity_fact, ctx).type == DecisionType.allow
    assert (
        evaluate(PolicyAction.share_medium_sensitivity_fact, ctx).type
        == DecisionType.require_approval
    )


def test_level2_allows_booking():
    ctx = TaskContext(autonomy_level=2)
    assert evaluate(PolicyAction.book_appointment, ctx).type == DecisionType.allow
    assert evaluate(PolicyAction.cancel_service, ctx).type == DecisionType.require_approval


def test_payments_always_require_approval():
    for level in range(4):
        decision = evaluate(PolicyAction.make_payment, TaskContext(autonomy_level=level))
        assert decision.type == DecisionType.require_approval
        assert decision.approval_kind == ApprovalKind.payment


def test_question_includes_detail():
    decision = evaluate(
        PolicyAction.make_payment, TaskContext(autonomy_level=3), detail="50 EUR за приём"
    )
    assert "50 EUR за приём" in decision.question


def test_invalid_autonomy_denied():
    decision = evaluate(PolicyAction.book_appointment, TaskContext(autonomy_level=7))
    assert decision.type == DecisionType.deny
