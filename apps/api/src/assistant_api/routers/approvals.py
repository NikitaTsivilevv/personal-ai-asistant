"""Approval resolution endpoint (spec §4)."""

from __future__ import annotations

from datetime import UTC, datetime

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from assistant_db.models import Approval, Task, TaskRun, User
from assistant_shared.events import PublishedRunEvent, RunEventType
from assistant_shared.queue import ControlMessage, send_control
from assistant_shared.schemas import Actor, ApprovalOut, ApprovalResolve, ApprovalStatus

from ..audit import write_audit
from ..bus import publish_event
from ..deps import get_default_user, get_redis, get_session

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.post("/{approval_id}/resolve", response_model=ApprovalOut)
async def resolve_approval(
    approval_id: str,
    payload: ApprovalResolve,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_default_user),
    redis: aioredis.Redis = Depends(get_redis),
) -> Approval:
    if payload.decision not in (ApprovalStatus.approved, ApprovalStatus.rejected):
        raise HTTPException(status_code=422, detail="decision must be approved or rejected")

    approval = (
        await session.execute(select(Approval).where(Approval.id == approval_id))
    ).scalar_one_or_none()
    if approval is None:
        raise HTTPException(status_code=404, detail="approval not found")
    if approval.status != ApprovalStatus.pending.value:
        raise HTTPException(status_code=409, detail=f"approval already {approval.status}")

    run = (
        await session.execute(select(TaskRun).where(TaskRun.id == approval.task_run_id))
    ).scalar_one()
    task = (await session.execute(select(Task).where(Task.id == run.task_id))).scalar_one()
    if task.user_id != user.id:
        raise HTTPException(status_code=404, detail="approval not found")

    approval.status = payload.decision.value
    approval.resolved_at = datetime.now(UTC)
    approval.resolved_via = payload.resolved_via
    write_audit(
        session,
        user_id=user.id,
        actor=Actor.user,
        event_type="approval.resolved",
        payload={
            "approval_id": approval.id,
            "decision": approval.status,
            "resolved_via": approval.resolved_via,
        },
        task_run_id=run.id,
    )
    await session.commit()

    # Unblock the waiting worker and notify subscribers (SSE, bot).
    await send_control(
        redis,
        run.id,
        ControlMessage(type="approval_resolved", approval_id=approval.id, status=approval.status),
    )
    await publish_event(
        redis,
        PublishedRunEvent(
            type=RunEventType.approval_resolved,
            run_id=run.id,
            task_id=task.id,
            user_id=user.id,
            data={
                "approval_id": approval.id,
                "status": approval.status,
                "resolved_via": approval.resolved_via,
            },
        ),
    )
    await session.refresh(approval)
    return approval
