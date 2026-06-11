"""Push notifications: consumes the run event bus and messages the owner.

Approval requests get inline Approve/Reject buttons; completions/failures get
summary messages (plan task D3).
"""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import redis.asyncio as aioredis

from assistant_shared.events import PublishedRunEvent, RunEventType
from assistant_shared.queue import EVENTS_CHANNEL

from .settings import BotSettings

logger = logging.getLogger(__name__)


def _approval_keyboard(approval_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Разрешить", callback_data=f"approval:{approval_id}:approved"
                ),
                InlineKeyboardButton(
                    text="⛔ Отклонить", callback_data=f"approval:{approval_id}:rejected"
                ),
            ]
        ]
    )


async def handle_event(bot: Bot, settings: BotSettings, event: PublishedRunEvent) -> None:
    chat_ids = settings.allowed_ids
    if not chat_ids:
        logger.warning("no allowed telegram users configured; dropping notification")
        return

    text: str | None = None
    keyboard: InlineKeyboardMarkup | None = None

    if event.type == RunEventType.approval_requested:
        question = event.data.get("question", "Требуется подтверждение")
        text = f"⏸ <b>Нужно твоё решение</b>\n\n{question}"
        keyboard = _approval_keyboard(event.data["approval_id"])
    elif event.type == RunEventType.run_completed:
        text = f"✅ <b>Задача выполнена</b>\n\n{event.data.get('result_summary', '')}"
    elif event.type == RunEventType.run_failed:
        text = f"❌ <b>Задача не выполнена</b>\n\n{event.data.get('failure_reason', '')}"

    if text is None:
        return
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="HTML")
        except Exception:
            logger.exception("failed to notify chat %s", chat_id)


async def run_notifier(bot: Bot, settings: BotSettings, redis: aioredis.Redis) -> None:
    pubsub = redis.pubsub()
    await pubsub.subscribe(EVENTS_CHANNEL)
    logger.info("notifier subscribed to %s", EVENTS_CHANNEL)
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                event = PublishedRunEvent.model_validate_json(message["data"])
                await handle_event(bot, settings, event)
            except Exception:
                logger.exception("failed to handle bus event")
    finally:
        await pubsub.unsubscribe(EVENTS_CHANNEL)
        await pubsub.aclose()
