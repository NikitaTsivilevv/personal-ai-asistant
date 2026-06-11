"""Crash recovery: mark runs that stopped producing events as failed.

EPIC-002 acceptance criterion 5: killing the worker mid-call must leave the
task_run failed with the partial transcript intact. Transcript segments are
persisted per-event, so the only missing piece is failing the silent run.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

import redis.asyncio as aioredis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from assistant_db.models import AuditLog, Task, TaskRun
from assistant_shared.events import PublishedRunEvent, RunEventType
from assistant_shared.schemas import Actor, RunStatus, TaskStatus

from .audit import write_audit
from .bus import publish_event

logger = logging.getLogger(__name__)

_ACTIVE = (RunStatus.running.value, RunStatus.waiting_approval.value)


async def sweep_stale_runs(
    session: AsyncSession, redis: aioredis.Redis, *, stale_after_s: int
) -> list[str]:
    """Fail active runs whose last audit event is older than the threshold.
    Returns the failed run ids."""
    cutoff = datetime.now(UTC) - timedelta(seconds=stale_after_s)
    last_event = (
        select(AuditLog.task_run_id, func.max(AuditLog.created_at).label("last_at"))
        .where(AuditLog.task_run_id.is_not(None))
        .group_by(AuditLog.task_run_id)
        .subquery()
    )
    rows = await session.execute(
        select(TaskRun, last_event.c.last_at)
        .join(last_event, last_event.c.task_run_id == TaskRun.id)
        .where(TaskRun.status.in_(_ACTIVE), last_event.c.last_at < cutoff)
    )
    failed: list[str] = []
    for run, last_at in rows:
        task = (await session.execute(select(Task).where(Task.id == run.task_id))).scalar_one()
        reason = f"worker went silent (no events since {last_at})"
        run.status = RunStatus.failed.value
        run.ended_at = datetime.now(UTC)
        run.failure_reason = reason
        task.status = TaskStatus.failed.value
        write_audit(
            session,
            user_id=task.user_id,
            actor=Actor.system,
            event_type="run.swept_stale",
            payload={"failure_reason": reason},
            task_run_id=run.id,
        )
        await session.commit()
        await publish_event(
            redis,
            PublishedRunEvent(
                type=RunEventType.run_failed,
                run_id=run.id,
                task_id=task.id,
                user_id=task.user_id,
                data={"failure_reason": reason},
            ),
        )
        failed.append(run.id)
        logger.warning("swept stale run %s", run.id)
    return failed


async def sweeper_loop(
    session_factory: async_sessionmaker[AsyncSession],
    redis: aioredis.Redis,
    *,
    stale_after_s: int,
    interval_s: int,
) -> None:
    while True:
        await asyncio.sleep(interval_s)
        try:
            async with session_factory() as session:
                await sweep_stale_runs(session, redis, stale_after_s=stale_after_s)
        except Exception:
            logger.exception("stale-run sweep failed")
