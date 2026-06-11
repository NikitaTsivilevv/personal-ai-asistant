"""Bot entrypoint: aiogram polling + event-bus notifier in one process."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from assistant_shared.queue import create_redis

from .api_client import ApiClient
from .handlers import router
from .notifier import run_notifier
from .settings import BotSettings

logger = logging.getLogger(__name__)


async def run_bot(settings: BotSettings | None = None) -> None:
    settings = settings or BotSettings()
    if settings.telegram_bot_token.startswith("PLACEHOLDER"):
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN is not configured. Create a bot via @BotFather and put the "
            "token into .env (see .env.example)."
        )

    bot = Bot(settings.telegram_bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    api = ApiClient(settings)
    redis = create_redis(settings.redis_url)

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    # Injected into handlers by aiogram's dependency mechanism (kwargs by name).
    dispatcher["settings"] = settings
    dispatcher["api"] = api

    notifier_task = asyncio.create_task(run_notifier(bot, settings, redis))
    try:
        await dispatcher.start_polling(bot)
    finally:
        notifier_task.cancel()
        await api.aclose()
        await redis.aclose()


def cli() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_bot())
