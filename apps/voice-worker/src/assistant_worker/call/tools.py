"""Agent tool implementations, framework-agnostic.

Every tool call passes through ``assistant_policy.evaluate()`` before
execution (spec §3). The Pipecat pipeline wraps these in FunctionSchema
adapters; tests call them directly.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import redis.asyncio as aioredis

from assistant_policy import (
    ActionRequest,
    FactSensitivity,
    PolicyActionType,
    PolicyOutcome,
    TaskContext,
    evaluate,
)
from assistant_shared.queue import ControlMessage, wait_control

from ..events_client import RunClient
from .agent import AgentConfig
from .control import ControlRouter

logger = logging.getLogger(__name__)

# Maps the LLM-facing action argument of request_approval to the policy
# taxonomy (EPIC-003 spec §2). The LLM proposes; the engine disposes.
_ACTION_MAP: dict[str, tuple[PolicyActionType, FactSensitivity | None]] = {
    "share_personal_data": (PolicyActionType.disclose_fact, FactSensitivity.medium),
    "share_sensitive_data": (PolicyActionType.disclose_fact, FactSensitivity.high),
    "share_contact": (PolicyActionType.share_contact, None),
    "book_appointment": (PolicyActionType.commit_booking, None),
    "reschedule_appointment": (PolicyActionType.commit_change, None),
    "cancel_service": (PolicyActionType.commit_cancellation, None),
    "make_payment": (PolicyActionType.agree_payment, None),
    "change_contract": (PolicyActionType.accept_terms, None),
}

TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "request_approval",
        "description": (
            "Ask the client for permission before a sensitive action: sharing personal data, "
            "booking, cancelling, paying, or changing a contract. Blocks until the client "
            "answers. Use BEFORE doing the action, never after."
        ),
        "parameters": {
            "action": {
                "type": "string",
                "enum": sorted(_ACTION_MAP.keys()),
                "description": "What kind of action needs permission",
            },
            "detail": {
                "type": "string",
                "description": "Human-readable description of exactly what will be done",
            },
        },
        "required": ["action", "detail"],
    },
    {
        "name": "end_call",
        "description": "End the call politely. Call after saying goodbye, or when the callee asks to stop.",
        "parameters": {
            "outcome": {
                "type": "string",
                "enum": ["achieved", "partially_achieved", "not_achieved", "callee_refused"],
                "description": "How the call went relative to the objective",
            },
        },
        "required": ["outcome"],
    },
    {
        "name": "log_fact",
        "description": (
            "Record an important fact learned during the call (price, date, name, condition) "
            "for the post-call summary."
        ),
        "parameters": {
            "fact": {"type": "string", "description": "The fact, one sentence"},
        },
        "required": ["fact"],
    },
    {
        "name": "propose_summary",
        "description": (
            "Propose the final call summary and next steps just before ending the call."
        ),
        "parameters": {
            "summary": {"type": "string", "description": "2-4 sentence summary of the call result"},
            "next_steps": {"type": "string", "description": "Concrete next steps for the client, if any"},
        },
        "required": ["summary"],
    },
]


@dataclass
class CallToolbox:
    """State + handlers for one call. The pipeline owns one instance per run."""

    config: AgentConfig
    run_client: RunClient
    redis: aioredis.Redis
    run_id: str
    approval_timeout_s: int = 120
    # Async callbacks provided by the pipeline.
    speak: Callable[[str], Awaitable[None]] | None = None  # say filler text via TTS
    hangup: Callable[[], Awaitable[None]] | None = None  # terminate the call leg
    # During a live call the ControlRouter owns the control list; the toolbox
    # then waits on the router instead of Redis directly.
    control_router: "ControlRouter | None" = None

    logged_facts: list[str] = field(default_factory=list)
    proposed_summary: str | None = None
    proposed_next_steps: str | None = None
    end_outcome: str | None = None

    def _policy_ctx(self) -> TaskContext:
        return TaskContext(
            autonomy_level=self.config.goal.autonomy_level,
            scenario=self.config.goal.scenario,
            allowed_facts=self.config.goal.allowed_facts,
        )

    async def request_approval(self, action: str, detail: str) -> dict:
        mapped = _ACTION_MAP.get(action)
        if mapped is None:
            return {"status": "error", "message": f"unknown action {action!r}"}
        policy_action, sensitivity = mapped

        ctx = self._policy_ctx()
        request = ActionRequest(
            action=policy_action, detail=detail, fact_sensitivity=sensitivity
        )
        decision = evaluate(request, ctx)
        await self.run_client.policy_decision(
            {
                "rule_id": decision.rule_id,
                "inputs_hash": decision.inputs_hash,
                "outcome": decision.type.value,
                "action": policy_action.value,
                "detail": detail,
                "scenario": ctx.scenario,
                "autonomy_level": ctx.autonomy_level,
            }
        )

        if decision.type == PolicyOutcome.allow:
            return {"status": "approved", "note": "allowed by policy, no confirmation needed"}
        if decision.type == PolicyOutcome.deny:
            from .agent import deny_phrase

            return {
                "status": "denied",
                "reason": decision.reason,
                "say": deny_phrase(self.config.language),
            }

        # Pause gracefully while the client decides (spec acceptance criterion 3).
        if self.speak is not None:
            from .agent import approval_filler

            await self.speak(approval_filler(self.config.language))

        approval_id = await self.run_client.request_approval(
            kind=decision.approval_kind.value,
            question=decision.question,
            context={"action": action, "detail": detail, "rule_id": decision.rule_id},
        )
        control = await self._wait_for_approval()
        if control is None:
            # Expired (EPIC-003 B1): resume the call with a graceful wrap-up,
            # never hang silently (acceptance criterion 3).
            from .agent import expiry_wrapup

            await self.run_client.approval_expired(approval_id)
            return {
                "status": "expired",
                "say": expiry_wrapup(self.config.language),
                "instruction": (
                    "The client did not answer in time. Say the wrap-up phrase, "
                    "do NOT perform the action, then politely end the call via "
                    "end_call with outcome partially_achieved."
                ),
            }
        if control.type in ("cancel", "hangup"):
            return {"status": "cancelled", "message": "client ended the task"}
        if control.status == "approved":
            return {"status": "approved"}
        return {"status": "rejected", "message": "client rejected the action"}

    async def _wait_for_approval(self) -> ControlMessage | None:
        """Wait for the resolution, passing whispers through without consuming the slot."""
        if self.control_router is not None:
            return await self.control_router.wait_approval(self.approval_timeout_s)
        deadline = asyncio.get_event_loop().time() + self.approval_timeout_s
        while True:
            remaining = max(1, int(deadline - asyncio.get_event_loop().time()))
            if deadline - asyncio.get_event_loop().time() <= 0:
                return None
            control = await wait_control(self.redis, self.run_id, timeout=min(remaining, 30))
            if control is None:
                if asyncio.get_event_loop().time() >= deadline:
                    return None
                continue
            if control.type == "whisper":
                if control.text:
                    self.config.whispers.append(control.text)
                continue
            return control

    async def end_call(self, outcome: str) -> dict:
        self.end_outcome = outcome
        if self.hangup is not None:
            await self.hangup()
        return {"status": "ok"}

    async def log_fact(self, fact: str) -> dict:
        self.logged_facts.append(fact)
        return {"status": "ok", "facts_recorded": len(self.logged_facts)}

    async def propose_summary(self, summary: str, next_steps: str | None = None) -> dict:
        self.proposed_summary = summary
        self.proposed_next_steps = next_steps
        return {"status": "ok"}

    @property
    def handlers(self) -> dict[str, Callable[..., Awaitable[dict]]]:
        return {
            "request_approval": self.request_approval,
            "end_call": self.end_call,
            "log_fact": self.log_fact,
            "propose_summary": self.propose_summary,
        }
