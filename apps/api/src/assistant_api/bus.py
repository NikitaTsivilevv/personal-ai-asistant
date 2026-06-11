"""Run event bus on Redis pub/sub: SSE clients and the Telegram bot subscribe."""

from __future__ import annotations

from collections.abc import AsyncIterator

import redis.asyncio as aioredis

from assistant_shared.events import PublishedRunEvent
from assistant_shared.queue import EVENTS_CHANNEL


async def publish_event(redis: aioredis.Redis, event: PublishedRunEvent) -> None:
    await redis.publish(EVENTS_CHANNEL, event.model_dump_json())


async def subscribe_events(
    redis: aioredis.Redis, *, run_id: str | None = None
) -> AsyncIterator[PublishedRunEvent]:
    """Yield bus events, optionally filtered to one run. Runs until cancelled."""
    pubsub = redis.pubsub()
    await pubsub.subscribe(EVENTS_CHANNEL)
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            event = PublishedRunEvent.model_validate_json(message["data"])
            if run_id is not None and event.run_id != run_id:
                continue
            yield event
    finally:
        await pubsub.unsubscribe(EVENTS_CHANNEL)
        await pubsub.aclose()
