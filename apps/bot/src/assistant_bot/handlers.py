"""Bot command handlers: /start, /tasks, /new flow, approval callbacks."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from assistant_shared.schemas import StructuredGoal

from .api_client import ApiClient
from .normalize import NormalizedTask, normalize_instruction
from .settings import BotSettings

logger = logging.getLogger(__name__)

router = Router()

_STATUS_ICONS = {
    "draft": "📝",
    "ready": "🟢",
    "queued": "📥",
    "running": "📞",
    "waiting_approval": "⏸",
    "done": "✅",
    "failed": "❌",
    "cancelled": "🚫",
}


class NewTask(StatesGroup):
    waiting_instruction = State()
    confirming = State()


def _is_allowed(settings: BotSettings, user_id: int | None) -> bool:
    return user_id is not None and user_id in settings.allowed_ids


def _goal_summary(n: NormalizedTask) -> str:
    constraints = "\n".join(f"  • {c}" for c in n.constraints) or "  —"
    facts = "\n".join(f"  • {f}" for f in n.allowed_facts) or "  —"
    return (
        f"<b>{n.title}</b>\n\n"
        f"🎯 Цель: {n.objective}\n"
        f"📋 Ограничения:\n{constraints}\n"
        f"🔓 Можно сообщать:\n{facts}\n"
        f"🤖 Автономность: {n.autonomy_level}/3\n"
        f"📞 Телефон: {n.target_phone or 'не указан'}\n"
        f"🏢 Кому: {n.target_name or 'не указано'}"
    )


@router.message(Command("start"))
async def cmd_start(message: Message, settings: BotSettings) -> None:
    if not _is_allowed(settings, message.from_user.id if message.from_user else None):
        await message.answer("Доступ ограничен. Это персональный ассистент.")
        return
    await message.answer(
        "Привет! Я управляю твоим ИИ-ассистентом для звонков.\n\n"
        "/new — новая задача\n"
        "/tasks — список задач"
    )


@router.message(Command("tasks"))
async def cmd_tasks(message: Message, settings: BotSettings, api: ApiClient) -> None:
    if not _is_allowed(settings, message.from_user.id if message.from_user else None):
        return
    tasks = await api.list_tasks()
    if not tasks:
        await message.answer("Задач пока нет. Создай первую: /new")
        return
    lines = [
        f"{_STATUS_ICONS.get(t['status'], '•')} <b>{t['title']}</b> — {t['status']}"
        for t in tasks[:20]
    ]
    await message.answer("\n".join(lines))


@router.message(Command("new"))
async def cmd_new(message: Message, state: FSMContext, settings: BotSettings) -> None:
    if not _is_allowed(settings, message.from_user.id if message.from_user else None):
        return
    await state.set_state(NewTask.waiting_instruction)
    await message.answer(
        "Опиши задачу свободным текстом: что нужно сделать, куда позвонить, "
        "какие есть ограничения.\n\n"
        "Например: «Запиши меня к стоматологу на этой неделе, клиника Дента +34911222333, "
        "лучше после 17:00»"
    )


@router.message(NewTask.waiting_instruction, F.text)
async def receive_instruction(
    message: Message, state: FSMContext, settings: BotSettings
) -> None:
    assert message.text is not None
    normalized = await normalize_instruction(message.text, settings)
    await state.update_data(instructions=message.text, normalized=normalized.model_dump())
    await state.set_state(NewTask.confirming)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Создать и запустить", callback_data="task:confirm"),
                InlineKeyboardButton(text="✏️ Переписать", callback_data="task:edit"),
            ],
            [InlineKeyboardButton(text="🚫 Отмена", callback_data="task:cancel")],
        ]
    )
    await message.answer(
        "Вот как я понял задачу:\n\n" + _goal_summary(normalized),
        reply_markup=keyboard,
        parse_mode="HTML",
    )


@router.callback_query(NewTask.confirming, F.data == "task:confirm")
async def confirm_task(callback: CallbackQuery, state: FSMContext, api: ApiClient) -> None:
    data = await state.get_data()
    normalized = NormalizedTask.model_validate(data["normalized"])
    task = await api.create_task(
        title=normalized.title,
        instructions=data["instructions"],
        structured_goal=StructuredGoal(
            objective=normalized.objective,
            constraints=normalized.constraints,
            allowed_facts=normalized.allowed_facts,
            autonomy_level=normalized.autonomy_level,
        ),
        target_phone=normalized.target_phone,
        target_name=normalized.target_name,
    )
    await api.queue_task(task["id"])
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(f"Задача «{task['title']}» создана и поставлена в очередь 📥")
    await callback.answer()


@router.callback_query(NewTask.confirming, F.data == "task:edit")
async def edit_task(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(NewTask.waiting_instruction)
    if isinstance(callback.message, Message):
        await callback.message.answer("Ок, опиши задачу ещё раз.")
    await callback.answer()


@router.callback_query(NewTask.confirming, F.data == "task:cancel")
async def cancel_new_task(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Отменено.")
    await callback.answer()


@router.callback_query(F.data.startswith("approval:"))
async def resolve_approval(callback: CallbackQuery, api: ApiClient) -> None:
    # callback_data: approval:<id>:<approved|rejected>
    assert callback.data is not None
    _, approval_id, decision = callback.data.split(":")
    try:
        await api.resolve_approval(approval_id, decision)
    except Exception:
        logger.exception("failed to resolve approval %s", approval_id)
        await callback.answer("Не удалось обработать — возможно, уже решено.", show_alert=True)
        return
    verdict = "✅ Разрешено" if decision == "approved" else "⛔ Отклонено"
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            (callback.message.text or "") + f"\n\n{verdict}", reply_markup=None
        )
    await callback.answer(verdict)
