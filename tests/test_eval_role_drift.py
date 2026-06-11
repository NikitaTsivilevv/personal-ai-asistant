from scripts.eval_role_drift import evaluate_turn, RoleDriftResult


class _FakeClient:
    def __init__(self, reply: str) -> None:
        self._reply = reply

    def respond(self, system_prompt: str, history: list[dict]) -> str:
        return self._reply


def test_states_name_is_pass():
    result = evaluate_turn(
        client=_FakeClient("A nombre de Nikita."),
        allowed_name="Nikita",
        language="es",
    )
    assert isinstance(result, RoleDriftResult)
    assert result.holds_role is True


def test_asking_for_name_is_drift():
    result = evaluate_turn(
        client=_FakeClient("¿A nombre de quién hago la reserva?"),
        allowed_name="Nikita",
        language="es",
    )
    assert result.holds_role is False
