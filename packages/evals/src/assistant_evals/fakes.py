"""In-memory stand-ins for the control plane during eval runs (spec Part 2).

FakeRunClient duck-types assistant_worker.events_client.RunClient and records every
event for scoring. ApprovalResponder plays the case's client_script: it watches for
approval requests and answers them through the standard Redis control list, so the
toolbox's real waiting/expiry code paths run.
"""

from __future__ import annotations

import asyncio
import itertools

from assistant_shared.queue import ControlMessage, send_control

from .case import ClientScriptItem


class FakeRunClient:
    def __init__(self) -> None:
        self.events: list[tuple] = []
        self.policy_decisions: list[dict] = []
        self.transcript_events: list[tuple[str, str]] = []  # (speaker, text)
        self.expired_approvals: list[str] = []
        self.approval_queue: asyncio.Queue[str] = asyncio.Queue()
        self._ids = itertools.count(1)

    async def status(self, status, *, call_state=None) -> None:
        self.events.append(("status", str(status), call_state))

    async def say(self, seq, speaker, text, ts_ms=None) -> None:
        self.events.append(("say", str(speaker), text))
        self.transcript_events.append((str(speaker), text))

    async def policy_decision(self, data: dict) -> None:
        self.events.append(("policy_decision", data))
        self.policy_decisions.append(data)

    async def request_approval(self, kind, question, context) -> str:
        approval_id = f"appr-{next(self._ids)}"
        self.events.append(("approval_requested", kind, question, approval_id))
        await self.approval_queue.put(approval_id)
        return approval_id

    async def approval_expired(self, approval_id) -> None:
        self.events.append(("approval_expired", approval_id))
        self.expired_approvals.append(approval_id)

    async def completed(self, result_summary, estimated_cost_cents=None, **extra) -> None:
        self.events.append(("completed", result_summary))

    async def failed(self, failure_reason, **extra) -> None:
        self.events.append(("failed", failure_reason))


class ApprovalResponder:
    """Answers approval requests per the case's client_script, in order.

    'approve'/'reject' send the standard approval_resolved control message;
    'expire' (or script exhaustion) answers nothing, so the toolbox times out.
    """

    def __init__(self, redis, run_id: str, run_client: FakeRunClient,
                 script: list[ClientScriptItem]) -> None:
        self._redis = redis
        self._run_id = run_id
        self._run_client = run_client
        self._script = list(script)
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        for item in self._script:
            approval_id = await self._run_client.approval_queue.get()
            if item.decision == "expire":
                continue  # never answer this one
            status = "approved" if item.decision == "approve" else "rejected"
            await send_control(
                self._redis, self._run_id,
                ControlMessage(type="approval_resolved", approval_id=approval_id,
                               status=status),
            )
        # Anything beyond the script is left unanswered (expires).
        while True:
            await self._run_client.approval_queue.get()
