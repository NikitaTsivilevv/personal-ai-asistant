"""Call state machine (spec §2):

dialing -> connected -> disclosure -> conversation -> (waiting_approval) ->
wrapping_up -> ended; plus failed / no_answer / voicemail / busy branches.

Fine-grained call states map onto the coarse stage-1 RunStatus so the event
contract stays unchanged: the call state travels as ``call_state`` inside
status_changed event data.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import UTC, datetime

from assistant_shared.schemas import RunStatus


class CallState(str, enum.Enum):
    dialing = "dialing"
    connected = "connected"
    disclosure = "disclosure"
    conversation = "conversation"
    waiting_approval = "waiting_approval"
    wrapping_up = "wrapping_up"
    ended = "ended"
    failed = "failed"
    no_answer = "no_answer"
    voicemail = "voicemail"
    busy = "busy"


TERMINAL_STATES = {
    CallState.ended,
    CallState.failed,
    CallState.no_answer,
    CallState.voicemail,
    CallState.busy,
}

# Retryable terminal outcomes (spec: busy/no-answer -> bounded retries).
RETRYABLE_STATES = {CallState.no_answer, CallState.busy}

_ALLOWED: dict[CallState, set[CallState]] = {
    CallState.dialing: {CallState.connected, CallState.failed, CallState.no_answer, CallState.busy},
    CallState.connected: {CallState.disclosure, CallState.voicemail, CallState.failed},
    CallState.disclosure: {CallState.conversation, CallState.wrapping_up, CallState.failed},
    CallState.conversation: {
        CallState.waiting_approval,
        CallState.wrapping_up,
        CallState.failed,
    },
    CallState.waiting_approval: {CallState.conversation, CallState.wrapping_up, CallState.failed},
    CallState.wrapping_up: {CallState.ended, CallState.failed},
    # Terminal states have no exits.
    CallState.ended: set(),
    CallState.failed: set(),
    CallState.no_answer: set(),
    CallState.voicemail: set(),
    CallState.busy: set(),
}

_TO_RUN_STATUS: dict[CallState, RunStatus] = {
    CallState.dialing: RunStatus.running,
    CallState.connected: RunStatus.running,
    CallState.disclosure: RunStatus.running,
    CallState.conversation: RunStatus.running,
    CallState.waiting_approval: RunStatus.waiting_approval,
    CallState.wrapping_up: RunStatus.running,
    CallState.ended: RunStatus.completed,
    CallState.failed: RunStatus.failed,
    CallState.no_answer: RunStatus.failed,
    CallState.voicemail: RunStatus.failed,
    CallState.busy: RunStatus.failed,
}


class InvalidTransition(Exception):
    def __init__(self, current: CallState, target: CallState) -> None:
        super().__init__(f"cannot transition {current.value} -> {target.value}")
        self.current = current
        self.target = target


@dataclass
class CallStateMachine:
    state: CallState = CallState.dialing
    history: list[tuple[CallState, datetime]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.history:
            self.history.append((self.state, datetime.now(UTC)))

    def transition(self, target: CallState) -> CallState:
        if target not in _ALLOWED[self.state]:
            raise InvalidTransition(self.state, target)
        self.state = target
        self.history.append((target, datetime.now(UTC)))
        return target

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    @property
    def is_retryable(self) -> bool:
        return self.state in RETRYABLE_STATES

    @property
    def run_status(self) -> RunStatus:
        return _TO_RUN_STATUS[self.state]
