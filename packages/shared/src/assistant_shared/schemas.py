"""Shared domain schemas used by api, bot, and voice-worker."""

from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, Field


class TaskStatus(str, enum.Enum):
    draft = "draft"
    ready = "ready"
    queued = "queued"
    running = "running"
    waiting_approval = "waiting_approval"
    done = "done"
    failed = "failed"
    cancelled = "cancelled"


class RunStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    waiting_approval = "waiting_approval"
    completed = "completed"
    failed = "failed"
    aborted = "aborted"


class ApprovalKind(str, enum.Enum):
    disclosure = "disclosure"
    payment = "payment"
    cancellation = "cancellation"
    sensitive_data = "sensitive_data"
    other = "other"


class ApprovalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"


class Actor(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    policy = "policy"
    system = "system"


class Speaker(str, enum.Enum):
    assistant = "assistant"
    callee = "callee"
    system = "system"


# Policy scenario profiles. Must match the rule files shipped in
# assistant_policy/rules/ (asserted by tests/test_scenarios_shared.py).
# "generic" is the conservative fallback for unknown/unsure classification.
SCENARIOS: tuple[str, ...] = ("generic", "doctor", "insurance", "restaurant", "info_gathering")


class StructuredGoal(BaseModel):
    """LLM-normalized task goal (TZ section 3)."""

    objective: str
    constraints: list[str] = Field(default_factory=list)
    allowed_facts: list[str] = Field(default_factory=list)
    autonomy_level: int = Field(default=1, ge=0, le=3)
    # Policy scenario profile (EPIC-003); "generic" rules apply when unset.
    scenario: str = "generic"


class TaskCreate(BaseModel):
    title: str
    instructions: str
    structured_goal: StructuredGoal
    target_phone: str | None = None
    target_name: str | None = None
    language_pref: str | None = None


class ApprovalOut(BaseModel):
    id: str
    task_run_id: str
    kind: ApprovalKind
    question: str
    context: dict = Field(default_factory=dict)
    status: ApprovalStatus
    requested_at: datetime
    resolved_at: datetime | None = None
    resolved_via: str | None = None

    model_config = {"from_attributes": True}


class TaskRunOut(BaseModel):
    id: str
    task_id: str
    attempt_no: int
    status: RunStatus
    started_at: datetime | None = None
    ended_at: datetime | None = None
    result_summary: str | None = None
    failure_reason: str | None = None
    estimated_cost_cents: int | None = None

    model_config = {"from_attributes": True}


class TaskOut(BaseModel):
    id: str
    user_id: str
    title: str
    instructions: str
    structured_goal: StructuredGoal
    target_phone: str | None
    target_name: str | None
    status: TaskStatus
    language_pref: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskDetailOut(TaskOut):
    runs: list[TaskRunOut] = Field(default_factory=list)
    approvals: list[ApprovalOut] = Field(default_factory=list)


class ApprovalResolve(BaseModel):
    decision: ApprovalStatus  # approved | rejected
    resolved_via: str = "telegram"


class ProfileFactCreate(BaseModel):
    """Create/update a profile fact (EPIC-003 B2). Upserts by key."""

    key: str = Field(min_length=1, max_length=100)
    value: str
    sensitivity: str = Field(default="medium", pattern="^(low|medium|high)$")
    allowed_by_default: bool = False
    # Policy scenarios where the fact may be used without per-task whitelisting.
    allowed_scenarios: list[str] = Field(default_factory=list)


class ProfileFactOut(ProfileFactCreate):
    id: str
    user_id: str

    model_config = {"from_attributes": True}
