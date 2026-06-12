from assistant_worker.settings import WorkerSettings


def test_termination_limit_defaults():
    s = WorkerSettings()
    assert s.max_call_duration_s == 360
    assert s.max_call_turns == 16
