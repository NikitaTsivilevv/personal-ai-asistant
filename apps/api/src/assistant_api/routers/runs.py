"""Run event ingestion (internal, worker-facing) and public SSE stream (spec §4).

The worker pushes RunEvent envelopes; the API persists state changes, writes
the audit trail, and rebroadcasts every event on the Redis event bus so SSE
clients and the Telegram bot see the same stream.
"""

from __future__ import annotations

from datetime import UTC, datetime

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from assistant_shared.queue import ControlMessage, send_control

from assistant_db.models import Approval, Task, TaskRun, TranscriptSegment
from assistant_shared.events import (
    ApprovalExpiredData,
    ApprovalRequestedData,
    PublishedRunEvent,
    RunCompletedData,
    RunEvent,
    RunEventType,
    RunFailedData,
    StatusChangedData,
    TranscriptSegmentData,
)
from assistant_shared.schemas import Actor, ApprovalStatus, RunStatus, TaskStatus

from ..audit import write_audit
from ..bus import publish_event, subscribe_events
from ..deps import get_redis, get_session, require_internal_token

router = APIRouter(tags=["runs"])

_RUN_TO_TASK_STATUS = {
    RunStatus.running.value: TaskStatus.running.value,
    RunStatus.waiting_approval.value: TaskStatus.waiting_approval.value,
    RunStatus.completed.value: TaskStatus.done.value,
    RunStatus.failed.value: TaskStatus.failed.value,
}


async def _apply_event(
    session: AsyncSession, run: TaskRun, task: Task, event: RunEvent
) -> dict:
    """Mutate run/task/approval state for one event. Returns extra response data."""
    extra: dict = {}
    now = datetime.now(UTC)

    match event.type:
        case RunEventType.status_changed:
            data = StatusChangedData.model_validate(event.data)
            run.status = data.status.value
            if data.status == RunStatus.running and run.started_at is None:
                run.started_at = now
            if data.status.value in _RUN_TO_TASK_STATUS:
                task.status = _RUN_TO_TASK_STATUS[data.status.value]

        case RunEventType.transcript_segment:
            data = TranscriptSegmentData.model_validate(event.data)
            session.add(
                TranscriptSegment(
                    task_run_id=run.id,
                    seq=data.seq,
                    speaker=data.speaker.value,
                    text=data.text,
                    ts_ms=data.ts_ms,
                )
            )

        case RunEventType.approval_requested:
            data = ApprovalRequestedData.model_validate(event.data)
            approval = Approval(
                task_run_id=run.id,
                kind=data.kind.value,
                question=data.question,
                context=data.context,
                status=ApprovalStatus.pending.value,
            )
            session.add(approval)
            run.status = RunStatus.waiting_approval.value
            task.status = TaskStatus.waiting_approval.value
            await session.flush()
            event.data["approval_id"] = approval.id
            extra["approval_id"] = approval.id

        case RunEventType.run_completed:
            data = RunCompletedData.model_validate(event.data)
            run.status = RunStatus.completed.value
            run.ended_at = now
            run.result_summary = data.result_summary
            run.estimated_cost_cents = data.estimated_cost_cents
            task.status = TaskStatus.done.value

        case RunEventType.run_failed:
            data = RunFailedData.model_validate(event.data)
            run.status = RunStatus.failed.value
            run.ended_at = now
            run.failure_reason = data.failure_reason
            task.status = TaskStatus.failed.value

        case RunEventType.approval_expired:
            data = ApprovalExpiredData.model_validate(event.data)
            approval = (
                await session.execute(select(Approval).where(Approval.id == data.approval_id))
            ).scalar_one_or_none()
            if approval is None or approval.task_run_id != run.id:
                raise HTTPException(status_code=404, detail="approval not found for this run")
            if approval.status == ApprovalStatus.pending.value:
                approval.status = ApprovalStatus.expired.value
                approval.resolved_at = now
                approval.resolved_via = "timeout"
            # The call continues with a graceful wrap-up (EPIC-003 B1).
            run.status = RunStatus.running.value
            task.status = TaskStatus.running.value

        case RunEventType.approval_resolved:
            # Resolution happens via POST /approvals/{id}/resolve; the worker
            # never sends this event type.
            raise HTTPException(status_code=422, detail="approval_resolved is api-originated")

    return extra


@router.post("/internal/runs/{run_id}/events", dependencies=[Depends(require_internal_token)])
async def ingest_run_event(
    run_id: str,
    event: RunEvent,
    session: AsyncSession = Depends(get_session),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    run = (
        await session.execute(select(TaskRun).where(TaskRun.id == run_id))
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    task = (await session.execute(select(Task).where(Task.id == run.task_id))).scalar_one()

    extra = await _apply_event(session, run, task, event)
    actor = Actor.policy if event.type == RunEventType.policy_decision else Actor.assistant
    write_audit(
        session,
        user_id=task.user_id,
        actor=actor,
        event_type=f"run.{event.type.value}",
        payload=event.data,
        task_run_id=run.id,
    )
    await session.commit()

    await publish_event(
        redis,
        PublishedRunEvent(
            type=event.type,
            data=event.data,
            ts=event.ts,
            run_id=run.id,
            task_id=task.id,
            user_id=task.user_id,
        ),
    )
    return {"ok": True, **extra}


class WhisperIn(BaseModel):
    text: str


async def _get_active_run(session: AsyncSession, run_id: str) -> tuple[TaskRun, Task]:
    run = (
        await session.execute(select(TaskRun).where(TaskRun.id == run_id))
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    if run.status not in (RunStatus.running.value, RunStatus.waiting_approval.value):
        raise HTTPException(status_code=409, detail=f"run is {run.status}, not active")
    task = (await session.execute(select(Task).where(Task.id == run.task_id))).scalar_one()
    return run, task


@router.post("/runs/{run_id}/hangup")
async def hangup_run(
    run_id: str,
    session: AsyncSession = Depends(get_session),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    """Live-call control (EPIC-002): ask the worker to end the call gracefully."""
    run, task = await _get_active_run(session, run_id)
    write_audit(
        session,
        user_id=task.user_id,
        actor=Actor.user,
        event_type="run.hangup_requested",
        payload={},
        task_run_id=run.id,
    )
    await session.commit()
    await send_control(redis, run.id, ControlMessage(type="hangup"))
    return {"ok": True}


@router.post("/runs/{run_id}/whisper")
async def whisper_run(
    run_id: str,
    payload: WhisperIn,
    session: AsyncSession = Depends(get_session),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    """Live-call control (EPIC-002): inject a client instruction into the agent."""
    run, task = await _get_active_run(session, run_id)
    write_audit(
        session,
        user_id=task.user_id,
        actor=Actor.user,
        event_type="run.whisper",
        payload={"text": payload.text},
        task_run_id=run.id,
    )
    await session.commit()
    await send_control(redis, run.id, ControlMessage(type="whisper", text=payload.text))
    return {"ok": True}


@router.get("/runs/{run_id}/events")
async def stream_run_events(
    run_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    redis: aioredis.Redis = Depends(get_redis),
) -> EventSourceResponse:
    run = (
        await session.execute(select(TaskRun).where(TaskRun.id == run_id))
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")

    async def event_stream():
        async for event in subscribe_events(redis, run_id=run_id):
            if await request.is_disconnected():
                break
            yield {"event": event.type.value, "data": event.model_dump_json()}
            if event.type in (RunEventType.run_completed, RunEventType.run_failed):
                break

    return EventSourceResponse(event_stream())
