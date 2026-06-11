"""Task lifecycle endpoints (spec §4)."""

from __future__ import annotations

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from assistant_db.models import Approval, Task, TaskRun, User
from assistant_shared.queue import ControlMessage, QueuedRun, enqueue_run, send_control
from assistant_shared.schemas import (
    Actor,
    RunStatus,
    TaskCreate,
    TaskDetailOut,
    TaskOut,
    TaskStatus,
)

from ..audit import write_audit
from ..deps import get_default_user, get_redis, get_session

router = APIRouter(prefix="/tasks", tags=["tasks"])

_QUEUEABLE = {TaskStatus.draft.value, TaskStatus.ready.value, TaskStatus.failed.value}
_CANCELLABLE = {
    TaskStatus.queued.value,
    TaskStatus.running.value,
    TaskStatus.waiting_approval.value,
}


async def _get_task_or_404(session: AsyncSession, task_id: str, user_id: str) -> Task:
    task = (
        await session.execute(
            select(Task)
            .where(Task.id == task_id, Task.user_id == user_id)
            .options(selectinload(Task.runs).selectinload(TaskRun.approvals))
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


def _detail(task: Task) -> TaskDetailOut:
    approvals: list[Approval] = [a for run in task.runs for a in run.approvals]
    return TaskDetailOut.model_validate(
        {
            **TaskOut.model_validate(task).model_dump(),
            "runs": task.runs,
            "approvals": approvals,
        }
    )


@router.post("", response_model=TaskOut, status_code=201)
async def create_task(
    payload: TaskCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_default_user),
) -> Task:
    task = Task(
        user_id=user.id,
        title=payload.title,
        instructions=payload.instructions,
        structured_goal=payload.structured_goal.model_dump(),
        target_phone=payload.target_phone,
        target_name=payload.target_name,
        language_pref=payload.language_pref,
        status=TaskStatus.ready.value,
    )
    session.add(task)
    await session.flush()
    write_audit(
        session,
        user_id=user.id,
        actor=Actor.user,
        event_type="task.created",
        payload={"task_id": task.id, "title": task.title},
    )
    await session.commit()
    await session.refresh(task)
    return task


@router.get("", response_model=list[TaskOut])
async def list_tasks(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_default_user),
) -> list[Task]:
    rows = await session.execute(
        select(Task).where(Task.user_id == user.id).order_by(Task.created_at.desc())
    )
    return list(rows.scalars())


@router.get("/{task_id}", response_model=TaskDetailOut)
async def get_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_default_user),
) -> TaskDetailOut:
    task = await _get_task_or_404(session, task_id, user.id)
    return _detail(task)


@router.post("/{task_id}/queue", response_model=TaskDetailOut)
async def queue_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_default_user),
    redis: aioredis.Redis = Depends(get_redis),
) -> TaskDetailOut:
    task = await _get_task_or_404(session, task_id, user.id)
    if task.status not in _QUEUEABLE:
        raise HTTPException(status_code=409, detail=f"task in status {task.status} cannot be queued")

    run = TaskRun(
        task_id=task.id,
        attempt_no=len(task.runs) + 1,
        status=RunStatus.queued.value,
    )
    session.add(run)
    task.status = TaskStatus.queued.value
    await session.flush()
    write_audit(
        session,
        user_id=user.id,
        actor=Actor.user,
        event_type="task.queued",
        payload={"task_id": task.id, "run_id": run.id, "attempt_no": run.attempt_no},
        task_run_id=run.id,
    )
    await session.commit()
    await enqueue_run(redis, QueuedRun(task_id=task.id, run_id=run.id, user_id=user.id))
    task = await _get_task_or_404(session, task_id, user.id)
    return _detail(task)


@router.post("/{task_id}/cancel", response_model=TaskDetailOut)
async def cancel_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_default_user),
    redis: aioredis.Redis = Depends(get_redis),
) -> TaskDetailOut:
    task = await _get_task_or_404(session, task_id, user.id)
    if task.status not in _CANCELLABLE:
        raise HTTPException(
            status_code=409, detail=f"task in status {task.status} cannot be cancelled"
        )

    task.status = TaskStatus.cancelled.value
    active_run = next(
        (
            r
            for r in task.runs
            if r.status
            in (RunStatus.queued.value, RunStatus.running.value, RunStatus.waiting_approval.value)
        ),
        None,
    )
    if active_run is not None:
        active_run.status = RunStatus.aborted.value
    write_audit(
        session,
        user_id=user.id,
        actor=Actor.user,
        event_type="task.cancelled",
        payload={"task_id": task.id},
        task_run_id=active_run.id if active_run else None,
    )
    await session.commit()
    if active_run is not None:
        await send_control(redis, active_run.id, ControlMessage(type="cancel"))
    task = await _get_task_or_404(session, task_id, user.id)
    return _detail(task)
