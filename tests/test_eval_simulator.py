import asyncio

from assistant_evals.case import EvalCase
from assistant_evals.llm_client import FakeChat
from assistant_evals.simulator import HANGUP_TOKEN, CalleeSimulator, _merge_consecutive_roles


def _case() -> EvalCase:
    return EvalCase(
        goal={"objective": "Reservar mesa", "scenario": "restaurant"},
        persona="Eres el encargado de reservas.",
        probes=["Require a deposit."],
        language="es",
    )


def test_system_prompt_contains_persona_probes_language():
    sim = CalleeSimulator(FakeChat([]), _case())
    prompt = sim.system_prompt()
    assert "encargado de reservas" in prompt
    assert "Require a deposit." in prompt
    assert "Spanish" in prompt


def test_next_turn_returns_reply_and_strips_hangup_token():
    sim = CalleeSimulator(FakeChat([f"Adiós. {HANGUP_TOKEN}"]), _case())
    reply = asyncio.run(sim.next_turn([("assistant", "Hola")]))
    assert reply == "Adiós."
    assert sim.wants_hangup is True


def test_next_turn_no_hangup_token_leaves_wants_hangup_false():
    sim = CalleeSimulator(FakeChat(["Sí, dígame."]), _case())
    reply = asyncio.run(sim.next_turn([("assistant", "Buenas tardes")]))
    assert reply == "Sí, dígame."
    assert sim.wants_hangup is False


def test_merge_consecutive_roles_merges_same():
    msgs = [
        {"role": "user", "content": "Hello"},
        {"role": "user", "content": "World"},
        {"role": "assistant", "content": "Hi"},
    ]
    merged = _merge_consecutive_roles(msgs)
    assert len(merged) == 2
    assert merged[0]["role"] == "user"
    assert "Hello\nWorld" == merged[0]["content"]
    assert merged[1]["role"] == "assistant"


def test_merge_consecutive_roles_no_merge_when_alternating():
    msgs = [
        {"role": "user", "content": "A"},
        {"role": "assistant", "content": "B"},
        {"role": "user", "content": "C"},
    ]
    merged = _merge_consecutive_roles(msgs)
    assert len(merged) == 3


def test_merge_consecutive_roles_empty():
    assert _merge_consecutive_roles([]) == []


def test_next_turn_merges_consecutive_agent_turns():
    """Two consecutive assistant turns in transcript are merged before the LLM call."""
    sim = CalleeSimulator(FakeChat(["Entendido."]), _case())
    transcript = [
        ("assistant", "Hola, llamo para reservar."),
        ("assistant", "¿Tienen mesa para dos?"),
    ]
    reply = asyncio.run(sim.next_turn(transcript))
    assert reply == "Entendido."
    # wants_hangup must still be False
    assert sim.wants_hangup is False
