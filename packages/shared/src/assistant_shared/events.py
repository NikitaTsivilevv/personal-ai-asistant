"""Run event contract shared by the worker (producer), api (ingestion/SSE), and bot (consumer).

EPIC-002's real Pipecat worker must reuse this contract unchanged.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from .schemas import ApprovalKind, ApprovalStatus, RunStatus, Speaker


class RunEventType(str, enum.Enum):
    status_changed = "status_changed"
    transcript_segment = "transcript_segment"
    approval_requested = "approval_requested"
    approval_resolved = "approval_resolved"
    # In-call approval wait expired (EPIC-003 B1): worker resumes the call with
    # a graceful wrap-up; the API marks the pending approval row expired.
    approval_expired = "approval_expired"
    # Every policy engine decision, for the audit trail (EPIC-003 A3).
    policy_decision = "policy_decision"
    run_completed = "run_completed"
    run_failed = "run_failed"


class StatusChangedData(BaseModel):
    status: RunStatus


class TranscriptSegmentData(BaseModel):
    seq: int
    speaker: Speaker
    text: str
    ts_ms: int


class ApprovalRequestedData(BaseModel):
    kind: ApprovalKind
    question: str
    context: dict = Field(default_factory=dict)
    # Filled in by the API after it persists the approval row.
    approval_id: str | None = None


class ApprovalResolvedData(BaseModel):
    approval_id: str
    status: ApprovalStatus
    resolved_via: str


class ApprovalExpiredData(BaseModel):
    approval_id: str


class PolicyDecisionData(BaseModel):
    rule_id: str
    inputs_hash: str
    outcome: str  # allow | require_approval | deny
    action: str
    detail: str = ""
    scenario: str = "generic"
    autonomy_level: int = 1


class RunCompletedData(BaseModel):
    result_summary: str
    estimated_cost_cents: int | None = None


class RunFailedData(BaseModel):
    failure_reason: str


class RunEvent(BaseModel):
    """Envelope pushed by the worker to POST /internal/runs/{id}/events."""

    type: RunEventType
    data: dict = Field(default_factory=dict)
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PublishedRunEvent(RunEvent):
    """Envelope as broadcast on the event bus (SSE + bot)."""

    run_id: str
    task_id: str
    user_id: str
