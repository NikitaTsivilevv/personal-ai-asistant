"""Bot: heuristic normalization fallback + module smoke (plan D1-D3).

Full aiogram flows need a live bot token; covered manually after registration.
"""

from __future__ import annotations

from assistant_bot.normalize import _normalize_heuristic, normalize_instruction
from assistant_bot.settings import BotSettings


def test_heuristic_extracts_phone_and_title():
    n = _normalize_heuristic(
        "Запиши меня к стоматологу на этой неделе, клиника Дента +34 911 222-333. Лучше после 17:00"
    )
    assert n.target_phone == "+34911222333"
    assert n.objective.startswith("Запиши меня к стоматологу")
    assert n.autonomy_level == 1


def test_heuristic_without_phone():
    n = _normalize_heuristic("Узнай часы работы аптеки")
    assert n.target_phone is None
    assert n.title == "Узнай часы работы аптеки"


async def test_normalize_uses_fallback_without_api_key():
    settings = BotSettings(anthropic_api_key="", telegram_allowed_user_ids="123")
    n = await normalize_instruction("Отмени подписку на интернет, звонить в Movistar", settings)
    assert n.objective
    assert settings.allowed_ids == {123}


def test_bot_modules_import():
    from assistant_bot import api_client, handlers, main, notifier  # noqa: F401

    assert handlers.router is not None
