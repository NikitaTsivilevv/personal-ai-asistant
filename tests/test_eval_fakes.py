"""FakeRunClient + ApprovalResponder drive CallToolbox approvals fully offline."""

from assistant_shared.schemas import StructuredGoal
from assistant_worker.call.agent import AgentConfig
from assistant_worker.call.tools import CallToolbox


def _toolbox(run_client, fake_redis, *, scenario="generic", autonomy=1, timeout_s=2):
    return CallToolbox(
        config=AgentConfig(goal=StructuredGoal(objective="x", scenario=scenario,
                                               autonomy_level=autonomy)),
        run_client=run_client,
        redis=fake_redis,
        run_id="run-eval",
        approval_timeout_s=timeout_s,
    )


async def test_scripted_approve(fake_redis):
    from assistant_evals.case import ClientScriptItem
    from assistant_evals.fakes import ApprovalResponder, FakeRunClient

    rc = FakeRunClient()
    responder = ApprovalResponder(fake_redis, "run-eval", rc,
                                  [ClientScriptItem(decision="approve")])
    responder.start()
    try:
        result = await _toolbox(rc, fake_redis).request_approval("make_payment", "20 EUR")
    finally:
        await responder.stop()
    assert result["status"] == "approved"
    assert any(e[0] == "policy_decision" for e in rc.events)
    assert rc.policy_decisions[0]["action"] == "agree_payment"


async def test_scripted_expire(fake_redis):
    from assistant_evals.fakes import ApprovalResponder, FakeRunClient

    rc = FakeRunClient()
    responder = ApprovalResponder(fake_redis, "run-eval", rc, [])  # no answers scripted
    responder.start()
    try:
        result = await _toolbox(rc, fake_redis, timeout_s=1).request_approval(
            "share_personal_data", "адрес"
        )
    finally:
        await responder.stop()
    assert result["status"] == "expired"
    assert rc.expired_approvals == ["appr-1"]
