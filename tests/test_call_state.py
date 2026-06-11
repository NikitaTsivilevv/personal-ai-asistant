"""Call state machine (EPIC-002 plan B2)."""

import pytest

from assistant_shared.schemas import RunStatus
from assistant_worker.call.state import (
    CallState,
    CallStateMachine,
    InvalidTransition,
)


def test_happy_path():
    sm = CallStateMachine()
    for target in (
        CallState.connected,
        CallState.disclosure,
        CallState.conversation,
        CallState.waiting_approval,
        CallState.conversation,
        CallState.wrapping_up,
        CallState.ended,
    ):
        sm.transition(target)
    assert sm.is_terminal
    assert sm.run_status == RunStatus.completed
    assert len(sm.history) == 8


def test_no_answer_branch():
    sm = CallStateMachine()
    sm.transition(CallState.no_answer)
    assert sm.is_terminal
    assert sm.is_retryable
    assert sm.run_status == RunStatus.failed


def test_voicemail_not_retryable():
    sm = CallStateMachine()
    sm.transition(CallState.connected)
    sm.transition(CallState.voicemail)
    assert sm.is_terminal
    assert not sm.is_retryable


def test_invalid_transition_rejected():
    sm = CallStateMachine()
    with pytest.raises(InvalidTransition):
        sm.transition(CallState.conversation)  # dialing -> conversation skips connected


def test_terminal_states_have_no_exits():
    sm = CallStateMachine()
    sm.transition(CallState.failed)
    with pytest.raises(InvalidTransition):
        sm.transition(CallState.dialing)


def test_waiting_approval_maps_to_run_status():
    sm = CallStateMachine()
    sm.transition(CallState.connected)
    sm.transition(CallState.disclosure)
    sm.transition(CallState.conversation)
    sm.transition(CallState.waiting_approval)
    assert sm.run_status == RunStatus.waiting_approval
