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

from assistant_shared.schemas import SCENARIOS, StructuredGoal

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


_SENSITIVITIES = {"low", "medium", "high"}
_SENSITIVITY_ICONS = {"low": "🟢", "medium": "🟡", "high": "🔴"}


def parse_fact_add(args: str) -> dict | None:
    """Parse '/fact_add key = value | sensitivity | scenario1,scenario2 | default'.

    Only 'key = value' is required; the optional parts may come in any order.
    Returns kwargs for ApiClient.upsert_fact, or None if unparseable.
    """
    parts = [p.strip() for p in args.split("|")]
    if "=" not in parts[0]:
        return None
    key, _, value = parts[0].partition("=")
    key, value = key.strip(), value.strip()
    if not key or not value:
        return None

    result: dict = {
        "key": key,
        "value": value,
        "sensitivity": "medium",
        "allowed_by_default": False,
        "allowed_scenarios": [],
    }
    for part in parts[1:]:
        if not part:
            continue
        lowered = part.lower()
        if lowered in _SENSITIVITIES:
            result["sensitivity"] = lowered
        elif lowered in ("default", "по умолчанию"):
            result["allowed_by_default"] = True
        else:
            result["allowed_scenarios"] = [
                s.strip() for s in part.split(",") if s.strip()
            ]
    return result


def _is_allowed(settings: BotSettings, user_id: int | None) -> bool:
    return user_id is not None and user_id in settings.allowed_ids


def _goal_summary(n: NormalizedTask) -> str:
    constraints = "\n".join(f"  • {c}" for c in n.constraints) or "  —"
    facts = "\n".join(f"  • {f}" for f in n.allowed_facts) or "  —"
    call_facts = "\n".join(f"  • {k}: {v}" for k, v in n.call_facts.items()) or "  —"
    return (
        f"<b>{n.title}</b>\n\n"
        f"🎯 Цель: {n.objective}\n"
        f"📋 Ограничения:\n{constraints}\n"
        f"🔓 Можно сообщать:\n{facts}\n"
        f"🗂 Данные для звонка:\n{call_facts}\n"
        f"🤖 Автономность: {n.autonomy_level}/3\n"
        f"🧭 Сценарий: {n.scenario}\n"
        f"📞 Телефон: {n.target_phone or 'не указан'}\n"
        f"🏢 Кому: {n.target_name or 'не указано'}"
    )


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Создать и запустить", callback_data="task:confirm"),
                InlineKeyboardButton(text="✏️ Переписать", callback_data="task:edit"),
            ],
            [
                InlineKeyboardButton(text="🧭 Сменить сценарий", callback_data="task:scenario"),
                InlineKeyboardButton(text="🚫 Отмена", callback_data="task:cancel"),
            ],
        ]
    )


def _scenario_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=s, callback_data=f"scenario:{s}")] for s in SCENARIOS
        ]
    )


def _to_structured_goal(n: NormalizedTask) -> StructuredGoal:
    return StructuredGoal(
        objective=n.objective,
        constraints=n.constraints,
        allowed_facts=n.allowed_facts,
        autonomy_level=n.autonomy_level,
        scenario=n.scenario,
        call_facts=n.call_facts,
    )


@router.message(Command("start"))
async def cmd_start(message: Message, settings: BotSettings) -> None:
    if not _is_allowed(settings, message.from_user.id if message.from_user else None):
        await message.answer("Доступ ограничен. Это персональный ассистент.")
        return
    await message.answer(
        "Привет! Я управляю твоим ИИ-ассистентом для звонков.\n\n"
        "/new — новая задача\n"
        "/tasks — список задач\n"
        "/facts — мои данные для звонков"
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


@router.message(Command("facts"))
async def cmd_facts(message: Message, settings: BotSettings, api: ApiClient) -> None:
    if not _is_allowed(settings, message.from_user.id if message.from_user else None):
        return
    facts = await api.list_facts()
    if not facts:
        await message.answer(
            "Фактов пока нет.\n\n"
            "Добавить: /fact_add ключ = значение | low/medium/high | сценарии | default\n"
            "Например: /fact_add дата рождения = 12.05.1990 | high | doctor"
        )
        return
    lines = []
    for f in facts:
        icon = _SENSITIVITY_ICONS.get(f["sensitivity"], "🟡")
        scope = []
        if f["allowed_by_default"]:
            scope.append("везде")
        if f["allowed_scenarios"]:
            scope.append(", ".join(f["allowed_scenarios"]))
        scope_text = " · ".join(scope) if scope else "только по белому списку задачи"
        lines.append(f"{icon} <b>{f['key']}</b>: {f['value']}\n    разрешён: {scope_text}")
    lines.append("\n/fact_add — добавить, /fact_del ключ — удалить")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("fact_add"))
async def cmd_fact_add(message: Message, settings: BotSettings, api: ApiClient) -> None:
    if not _is_allowed(settings, message.from_user.id if message.from_user else None):
        return
    args = (message.text or "").removeprefix("/fact_add").strip()
    parsed = parse_fact_add(args) if args else None
    if parsed is None:
        await message.answer(
            "Формат: /fact_add ключ = значение | low/medium/high | сценарии | default\n\n"
            "Примеры:\n"
            "/fact_add имя = Никита | low | default\n"
            "/fact_add дата рождения = 12.05.1990 | high | doctor\n"
            "/fact_add номер полиса = AB-123456 | medium | insurance"
        )
        return
    fact = await api.upsert_fact(**parsed)
    scope = "везде" if fact["allowed_by_default"] else (
        ", ".join(fact["allowed_scenarios"]) or "только по белому списку задачи"
    )
    await message.answer(
        f"Сохранил: <b>{fact['key']}</b> ({fact['sensitivity']}, разрешён: {scope})",
        parse_mode="HTML",
    )


@router.message(Command("fact_del"))
async def cmd_fact_del(message: Message, settings: BotSettings, api: ApiClient) -> None:
    if not _is_allowed(settings, message.from_user.id if message.from_user else None):
        return
    key = (message.text or "").removeprefix("/fact_del").strip()
    if not key:
        await message.answer("Формат: /fact_del ключ")
        return
    try:
        await api.delete_fact(key)
    except Exception:
        await message.answer(f"Факт «{key}» не найден.")
        return
    await message.answer(f"Удалил факт «{key}».")


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
    keyboard = _confirm_keyboard()
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
        structured_goal=_to_structured_goal(normalized),
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


@router.callback_query(NewTask.confirming, F.data == "task:scenario")
async def choose_scenario(callback: CallbackQuery) -> None:
    if isinstance(callback.message, Message):
        await callback.message.answer("Выбери сценарий звонка:", reply_markup=_scenario_keyboard())
    await callback.answer()


@router.callback_query(NewTask.confirming, F.data.startswith("scenario:"))
async def set_scenario(callback: CallbackQuery, state: FSMContext) -> None:
    assert callback.data is not None
    scenario = callback.data.removeprefix("scenario:")
    if scenario not in SCENARIOS:
        await callback.answer("Неизвестный сценарий", show_alert=True)
        return
    data = await state.get_data()
    normalized = NormalizedTask.model_validate(data["normalized"])
    normalized.scenario = scenario
    await state.update_data(normalized=normalized.model_dump())
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "Обновил:\n\n" + _goal_summary(normalized),
            reply_markup=_confirm_keyboard(),
            parse_mode="HTML",
        )
    await callback.answer(f"Сценарий: {scenario}")


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
