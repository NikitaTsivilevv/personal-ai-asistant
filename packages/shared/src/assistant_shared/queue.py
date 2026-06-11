"""Redis key names and queue/bus helpers shared by api, bot, and voice-worker.

Conventions:
- Task dispatch: Redis list ``queue:task_runs`` (LPUSH by api, BRPOP by worker).
- Run control:   Redis list ``run:{run_id}:control`` (LPUSH by api on approval
  resolution, BRPOP by the worker while it waits).
- Event bus:     pub/sub channel ``events:runs`` carrying PublishedRunEvent JSON,
  consumed by SSE clients and the Telegram bot.
"""

from __future__ import annotations

import asyncio
import logging
import time
from urllib.parse import urlparse

import redis.asyncio as aioredis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Pause before re-polling after a dropped connection so a Redis outage does not
# turn the poll loop into a hot spin; redis-py reconnects on the next command.
_RECONNECT_DELAY_S = 1.0

TASK_QUEUE_KEY = "queue:task_runs"
EVENTS_CHANNEL = "events:runs"


def run_control_key(run_id: str) -> str:
    return f"run:{run_id}:control"


class QueuedRun(BaseModel):
    """Message placed on the task queue when a run is dispatched."""

    task_id: str
    run_id: str
    user_id: str


class ControlMessage(BaseModel):
    """Message delivered to the worker via the run control list.

    Types:
    - "approval_resolved": approval_id + status filled
    - "cancel": abort the task (stage 1 semantics)
    - "hangup": end the live call gracefully (wrap-up, then summary)
    - "whisper": text injected into the agent context mid-call
    """

    type: str
    approval_id: str | None = None
    status: str | None = None
    text: str | None = None


def create_redis(url: str) -> aioredis.Redis:
    return aioredis.from_url(url, decode_responses=True)


def describe_redis_target(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.hostname:
        return parsed.scheme or "redis"
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{parsed.hostname}{port}"


async def enqueue_run(redis: aioredis.Redis, msg: QueuedRun) -> None:
    await redis.lpush(TASK_QUEUE_KEY, msg.model_dump_json())


async def dequeue_run(redis: aioredis.Redis, timeout: int = 5) -> QueuedRun | None:
    try:
        item = await redis.brpop(TASK_QUEUE_KEY, timeout=timeout)
    except TimeoutError:
        return None
    except RedisConnectionError as exc:
        logger.warning("redis connection dropped during dequeue, will retry: %s", exc)
        await asyncio.sleep(_RECONNECT_DELAY_S)
        return None
    if item is None:
        return None
    _, raw = item
    return QueuedRun.model_validate_json(raw)


async def send_control(redis: aioredis.Redis, run_id: str, msg: ControlMessage) -> None:
    await redis.lpush(run_control_key(run_id), msg.model_dump_json())


async def wait_control(
    redis: aioredis.Redis, run_id: str, timeout: int = 5
) -> ControlMessage | None:
    key = run_control_key(run_id)
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        try:
            item = await redis.brpop(key, timeout=max(1, min(5, int(remaining))))
        except TimeoutError:
            continue
        except RedisConnectionError as exc:
            logger.warning("redis connection dropped during control wait, will retry: %s", exc)
            await asyncio.sleep(_RECONNECT_DELAY_S)
            continue
        if item is None:
            continue
        _, raw = item
        return ControlMessage.model_validate_json(raw)
