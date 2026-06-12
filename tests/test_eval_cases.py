"""Eval case cards parse and stay consistent with the policy scenario list."""

from pathlib import Path

CASES_DIR = Path("packages/evals/cases")


def test_load_all_cases():
    from assistant_evals.case import load_cases
    from assistant_shared.schemas import SCENARIOS

    cases = load_cases(CASES_DIR)
    assert len(cases) >= 6
    for case in cases:
        assert case.goal.scenario in SCENARIOS
        assert case.persona
        assert case.max_turns >= 4
        for item in case.client_script:
            assert item.decision in ("approve", "reject", "expire")


def test_every_scenario_has_at_least_one_case():
    from assistant_evals.case import load_cases
    from assistant_shared.schemas import SCENARIOS

    covered = {c.goal.scenario for c in load_cases(CASES_DIR)}
    assert covered == set(SCENARIOS)


def test_case_name_includes_scenario_dir():
    from assistant_evals.case import load_cases

    names = {c.name for c in load_cases(CASES_DIR)}
    assert "doctor/role_drift_probe" in names
