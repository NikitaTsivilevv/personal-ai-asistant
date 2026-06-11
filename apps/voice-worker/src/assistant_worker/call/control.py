"""Single consumer of the run control list during a live call.

The control list carries approval resolutions, whispers, hangup, and cancel.
Only one consumer may BRPOP it, so this router dispatches:

- whisper  -> on_whisper callback (inject into agent context)
- hangup   -> on_hangup callback (graceful wrap-up)
- cancel   -> on_hangup callback (same handling mid-call)
- approval_resolved -> internal queue consumed by CallToolbox.request_approval
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

import redis.asyncio as aioredis

from assistant_shared.queue import ControlMessage, wait_control

logger = logging.getLogger(__name__)


class ControlRouter:
    def __init__(
        self,
        redis: aioredis.Redis,
        run_id: str,
        *,
        on_whisper: Callable[[str], Awaitable[None]] | None = None,
        on_hangup: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        self._redis = redis
        self._run_id = run_id
        self._on_whisper = on_whisper
        self._on_hangup = on_hangup
        self._resolutions: asyncio.Queue[ControlMessage] = asyncio.Queue()
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                msg = await wait_control(self._redis, self._run_id, timeout=5)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("control list read failed")
                await asyncio.sleep(1)
                continue
            if msg is None:
                continue
            await self._dispatch(msg)

    async def _dispatch(self, msg: ControlMessage) -> None:
        if msg.type == "whisper":
            if msg.text and self._on_whisper is not None:
                await self._on_whisper(msg.text)
        elif msg.type in ("hangup", "cancel"):
            if self._on_hangup is not None:
                await self._on_hangup(msg.type)
        elif msg.type == "approval_resolved":
            await self._resolutions.put(msg)
        else:
            logger.warning("unknown control message type %s", msg.type)

    async def wait_approval(self, timeout_s: int) -> ControlMessage | None:
        try:
            return await asyncio.wait_for(self._resolutions.get(), timeout=timeout_s)
        except TimeoutError:
            return None
