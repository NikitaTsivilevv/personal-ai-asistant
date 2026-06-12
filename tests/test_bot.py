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


def test_parse_fact_add_full_form():
    from assistant_bot.handlers import parse_fact_add

    parsed = parse_fact_add("дата рождения = 12.05.1990 | high | doctor,insurance")
    assert parsed == {
        "key": "дата рождения",
        "value": "12.05.1990",
        "sensitivity": "high",
        "allowed_by_default": False,
        "allowed_scenarios": ["doctor", "insurance"],
    }


def test_parse_fact_add_minimal_and_default_flag():
    from assistant_bot.handlers import parse_fact_add

    parsed = parse_fact_add("имя = Никита | low | default")
    assert parsed["key"] == "имя"
    assert parsed["value"] == "Никита"
    assert parsed["sensitivity"] == "low"
    assert parsed["allowed_by_default"] is True
    assert parsed["allowed_scenarios"] == []

    minimal = parse_fact_add("город = Барселона")
    assert minimal["sensitivity"] == "medium"


def test_parse_fact_add_value_with_equals_sign():
    from assistant_bot.handlers import parse_fact_add

    parsed = parse_fact_add("email = a=b@example.com")
    assert parsed["key"] == "email"
    assert parsed["value"] == "a=b@example.com"


def test_parse_fact_add_rejects_garbage():
    from assistant_bot.handlers import parse_fact_add

    assert parse_fact_add("просто текст без равно") is None
    assert parse_fact_add("= значение без ключа") is None


def test_parse_llm_reply_keeps_valid_scenario():
    from assistant_bot.normalize import _parse_llm_reply

    raw = (
        '{"objective": "Записаться к врачу", "constraints": [], "allowed_facts": [],'
        ' "autonomy_level": 1, "target_phone": null, "target_name": "Clinica",'
        ' "title": "Врач", "scenario": "doctor"}'
    )
    assert _parse_llm_reply(raw).scenario == "doctor"


def test_parse_llm_reply_coerces_unknown_scenario_to_generic():
    from assistant_bot.normalize import _parse_llm_reply

    raw = (
        '{"objective": "x", "constraints": [], "allowed_facts": [], "autonomy_level": 1,'
        ' "target_phone": null, "target_name": null, "title": "x", "scenario": "dentist"}'
    )
    assert _parse_llm_reply(raw).scenario == "generic"


def test_parse_llm_reply_missing_scenario_defaults_generic_and_strips_fences():
    from assistant_bot.normalize import _parse_llm_reply

    raw = (
        '```json\n{"objective": "x", "constraints": [], "allowed_facts": [],'
        ' "autonomy_level": 1, "target_phone": null, "target_name": null, "title": "x"}\n```'
    )
    assert _parse_llm_reply(raw).scenario == "generic"


def test_heuristic_fallback_scenario_is_generic():
    n = _normalize_heuristic("Узнай часы работы аптеки")
    assert n.scenario == "generic"


def test_normalize_prompt_mentions_scenario_enum():
    from assistant_bot.normalize import _SYSTEM_PROMPT
    from assistant_shared.schemas import SCENARIOS

    for name in SCENARIOS:
        assert name in _SYSTEM_PROMPT
