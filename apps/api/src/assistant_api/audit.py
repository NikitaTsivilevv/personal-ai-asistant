"""Every state change writes an audit_log row (spec §8)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from assistant_db.models import AuditLog
from assistant_shared.schemas import Actor


def write_audit(
    session: AsyncSession,
    *,
    user_id: str,
    actor: Actor,
    event_type: str,
    payload: dict | None = None,
    task_run_id: str | None = None,
) -> None:
    """Stage the audit row on the session; caller commits with the state change."""
    session.add(
        AuditLog(
            user_id=user_id,
            task_run_id=task_run_id,
            actor=actor.value,
            event_type=event_type,
            payload=payload or {},
        )
    )
