"""Worker entrypoint.

WORKER_MODE=simulate (default): stage-1 stub lifecycle, no telephony.
WORKER_MODE=call: real Twilio/Pipecat calls - runs the media-stream WebSocket
server and the queue consumer in one process (one active call per worker).
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from assistant_shared.queue import create_redis, dequeue_run, describe_redis_target

from .settings import WorkerSettings
from .simulator import simulate_run

logger = logging.getLogger(__name__)


async def run_worker(settings: WorkerSettings | None = None) -> None:
    settings = settings or WorkerSettings()
    if settings.worker_mode == "call":
        await _run_call_worker(settings)
    else:
        await _run_simulate_worker(settings)


async def _run_simulate_worker(settings: WorkerSettings) -> None:
    redis = create_redis(settings.redis_url)
    async with httpx.AsyncClient() as http:
        logger.info("simulate worker started, polling %s", describe_redis_target(settings.redis_url))
        while True:
            msg = await dequeue_run(redis, timeout=5)
            if msg is None:
                continue
            logger.info("picked up run %s (task %s)", msg.run_id, msg.task_id)
            try:
                await simulate_run(msg, http=http, redis=redis, settings=settings)
            except Exception:
                logger.exception("run %s crashed", msg.run_id)


async def _run_call_worker(settings: WorkerSettings) -> None:
    import uvicorn

    from .call.runner import CallRegistry, run_call
    from .call.server import create_ws_app

    registry = CallRegistry()
    redis = create_redis(settings.redis_url)
    ws_app = create_ws_app(registry)
    server = uvicorn.Server(
        uvicorn.Config(ws_app, host=settings.ws_host, port=settings.ws_port, log_level="info")
    )

    async def consume_queue() -> None:
        async with httpx.AsyncClient() as http:
            logger.info("call worker started; media ws on %s:%s", settings.ws_host, settings.ws_port)
            while True:
                msg = await dequeue_run(redis, timeout=5)
                if msg is None:
                    continue
                logger.info("picked up run %s (task %s)", msg.run_id, msg.task_id)
                try:
                    # One active call per worker instance (spec §3).
                    await run_call(
                        msg, http=http, redis=redis, settings=settings, registry=registry
                    )
                except Exception:
                    logger.exception("run %s crashed", msg.run_id)

    await asyncio.gather(server.serve(), consume_queue())


def cli() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())
