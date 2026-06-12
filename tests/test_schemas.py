from assistant_shared.schemas import StructuredGoal


def test_structured_goal_call_facts_defaults_empty_and_roundtrips():
    g = StructuredGoal(objective="x")
    assert g.call_facts == {}
    g2 = StructuredGoal(objective="x", call_facts={"имя брони": "Victoria"})
    assert g2.call_facts == {"имя брони": "Victoria"}
    # survives JSON round-trip (structured_goal is persisted as JSON)
    assert StructuredGoal.model_validate(g2.model_dump()).call_facts == {"имя брони": "Victoria"}
