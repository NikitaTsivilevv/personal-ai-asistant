from assistant_worker.call.termination import TerminationGuard
from assistant_worker.settings import WorkerSettings


def test_termination_limit_defaults():
    s = WorkerSettings()
    assert s.max_call_duration_s == 360
    assert s.max_call_turns == 16


def test_guard_triggers_on_turns():
    g = TerminationGuard(max_duration_s=999, max_turns=2, now=lambda: 0.0)
    assert not g.register_turn()  # turn 1
    assert g.register_turn()      # turn 2 -> limit reached


def test_guard_triggers_on_duration():
    clock = {"t": 0.0}
    g = TerminationGuard(max_duration_s=10, max_turns=999, now=lambda: clock["t"])
    assert not g.duration_exceeded()
    clock["t"] = 11.0
    assert g.duration_exceeded()


def test_guard_fires_once():
    g = TerminationGuard(max_duration_s=1, max_turns=1, now=lambda: 0.0)
    assert g.try_fire()
    assert not g.try_fire()  # idempotent
