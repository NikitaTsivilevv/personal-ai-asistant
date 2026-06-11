"""Schema v1 (spec 2026-06-11-mvp-stage1-control-plane §3).

All owned tables carry user_id (decision D-7, light multi-tenant groundwork).
JSON columns use JSONB on Postgres and plain JSON elsewhere (sqlite tests).
Money-relevant fields are integer cents.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JsonCol = JSON().with_variant(JSONB(), "postgresql")


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    locale: Mapped[str] = mapped_column(String(10), default="ru")


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    instructions: Mapped[str] = mapped_column(Text)
    structured_goal: Mapped[dict] = mapped_column(JsonCol, default=dict)
    target_phone: Mapped[str | None] = mapped_column(String(32))
    target_name: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    language_pref: Mapped[str | None] = mapped_column(String(10))

    runs: Mapped[list[TaskRun]] = relationship(back_populates="task", order_by="TaskRun.attempt_no")


class TaskRun(TimestampMixin, Base):
    __tablename__ = "task_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_summary: Mapped[str | None] = mapped_column(Text)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    estimated_cost_cents: Mapped[int | None] = mapped_column(Integer)

    task: Mapped[Task] = relationship(back_populates="runs")
    approvals: Mapped[list[Approval]] = relationship(back_populates="task_run")


class Approval(TimestampMixin, Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_run_id: Mapped[str] = mapped_column(ForeignKey("task_runs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    question: Mapped[str] = mapped_column(Text)
    context: Mapped[dict] = mapped_column(JsonCol, default=dict)
    status: Mapped[str] = mapped_column(String(10), default="pending", index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_via: Mapped[str | None] = mapped_column(String(10))

    task_run: Mapped[TaskRun] = relationship(back_populates="approvals")


class TranscriptSegment(TimestampMixin, Base):
    __tablename__ = "transcript_segments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_run_id: Mapped[str] = mapped_column(ForeignKey("task_runs.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    speaker: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)
    ts_ms: Mapped[int] = mapped_column(Integer)


class Contact(TimestampMixin, Base):
    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(32))
    org_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)


class ProfileFact(TimestampMixin, Base):
    __tablename__ = "profile_facts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    key: Mapped[str] = mapped_column(String(100))
    value: Mapped[str] = mapped_column(Text)
    sensitivity: Mapped[str] = mapped_column(String(10), default="medium")
    allowed_by_default: Mapped[bool] = mapped_column(Boolean, default=False)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    task_run_id: Mapped[str | None] = mapped_column(ForeignKey("task_runs.id"), index=True)
    actor: Mapped[str] = mapped_column(String(10))
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    payload: Mapped[dict] = mapped_column(JsonCol, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
