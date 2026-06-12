"""Scenario list consistency: shared constant <-> policy rule files (spec Part 1)."""

from importlib.resources import files


def test_shared_scenarios_match_policy_rule_files():
    from assistant_shared.schemas import SCENARIOS

    rule_files = {
        entry.name.removesuffix(".json")
        for entry in files("assistant_policy").joinpath("rules").iterdir()
        if entry.name.endswith(".json")
    }
    assert set(SCENARIOS) == rule_files
    assert SCENARIOS[0] == "generic"  # conservative default stays first


def test_shared_scenarios_match_scenario_enum():
    from assistant_shared.schemas import SCENARIOS
    from assistant_shared.policy import Scenario

    assert set(SCENARIOS) == {s.value for s in Scenario}


def test_structured_goal_default_scenario_is_generic():
    from assistant_shared.schemas import StructuredGoal

    assert StructuredGoal(objective="x").scenario == "generic"
