"""Worker entrypoint: consume the task queue and simulate runs."""

from __future__ import annotations

import asyncio
import logging

import httpx

from assistant_shared.queue import create_redis, dequeue_run

from .settings import WorkerSettings
from .simulator import simulate_run

logger = logging.getLogger(__name__)


async def run_worker(settings: WorkerSettings | None = None) -> None:
    settings = settings or WorkerSettings()
    redis = create_redis(settings.redis_url)
    async with httpx.AsyncClient() as http:
        logger.info("worker started, polling %s", settings.redis_url)
        while True:
            msg = await dequeue_run(redis, timeout=5)
            if msg is None:
                continue
            logger.info("picked up run %s (task %s)", msg.run_id, msg.task_id)
            try:
                await simulate_run(msg, http=http, redis=redis, settings=settings)
            except Exception:
                logger.exception("run %s crashed", msg.run_id)


def cli() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())
