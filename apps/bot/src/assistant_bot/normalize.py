"""Free-text instruction -> StructuredGoal (plan task D2).

Uses Claude when an API key is configured; otherwise falls back to a heuristic
parse so the bot stays usable before any provider registration (plan risk note:
'if it stalls, fall back to a structured form-style dialog').
"""

from __future__ import annotations

import json
import logging
import re

from assistant_shared.schemas import SCENARIOS, StructuredGoal

from .settings import BotSettings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
Ты нормализуешь задачу для ИИ-ассистента, который звонит по телефону от имени клиента.
Из свободного текста пользователя извлеки JSON со структурой:
{
  "objective": "краткая цель звонка одним предложением",
  "constraints": ["ограничения и пожелания пользователя"],
  "allowed_facts": ["какие личные данные можно сообщать собеседнику"],
  "call_facts": {"метка": "значение"},
  "autonomy_level": 0-3,
  "target_phone": "телефон в международном формате или null",
  "target_name": "название организации/имя или null",
  "title": "короткий заголовок задачи",
  "scenario": "generic|doctor|insurance|restaurant|info_gathering"
}
autonomy_level: 0 - подтверждать каждое действие, 1 - по умолчанию, 2 - разрешены записи/переносы,
3 - максимум самостоятельности (платежи всё равно требуют подтверждения).
scenario: тип звонка. doctor - клиники, врачи, медицинские записи; insurance - страховые компании;
restaurant - рестораны, бронь столиков; info_gathering - звонок только чтобы узнать информацию;
generic - всё остальное И ЛЮБОЙ случай, когда не уверен.
call_facts: конкретные данные ИМЕННО этого звонка, которые ассистент называет собеседнику
(имя брони/записи, дата и время, число гостей, номер заказа). Если бронь/запись на ДРУГОГО
человека — его имя идёт в call_facts (например "бронь на имя Victoria" -> {"имя брони": "Victoria"}),
НЕ в allowed_facts. allowed_facts — это какие ЛИЧНЫЕ данные владельца можно раскрывать.
Отвечай ТОЛЬКО валидным JSON без пояснений."""


class NormalizedTask(StructuredGoal):
    title: str = "Задача"
    target_phone: str | None = None
    target_name: str | None = None


def _coerce_scenario(value: object) -> str:
    if isinstance(value, str) and value in SCENARIOS:
        return value
    if value not in (None, ""):
        logger.warning("LLM returned unknown scenario %r; falling back to generic", value)
    return "generic"


def _parse_llm_reply(raw: str) -> NormalizedTask:
    raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    payload = json.loads(raw)
    payload["scenario"] = _coerce_scenario(payload.get("scenario"))
    return NormalizedTask.model_validate(payload)


async def normalize_instruction(text: str, settings: BotSettings) -> NormalizedTask:
    if settings.anthropic_api_key and not settings.anthropic_api_key.startswith("PLACEHOLDER"):
        try:
            return await _normalize_llm(text, settings)
        except Exception:
            logger.exception("LLM normalization failed, using heuristic fallback")
    return _normalize_heuristic(text)


async def _normalize_llm(text: str, settings: BotSettings) -> NormalizedTask:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
    )
    return _parse_llm_reply(response.content[0].text)


_PHONE_RE = re.compile(r"(\+?\d[\d\s\-()]{7,}\d)")


def _normalize_heuristic(text: str) -> NormalizedTask:
    phone_match = _PHONE_RE.search(text)
    phone = re.sub(r"[\s\-()]", "", phone_match.group(1)) if phone_match else None
    first_sentence = re.split(r"[.!?\n]", text.strip(), maxsplit=1)[0].strip()
    title = first_sentence[:60] or "Задача"
    return NormalizedTask(
        objective=first_sentence or text.strip(),
        constraints=[],
        allowed_facts=[],
        autonomy_level=1,
        target_phone=phone,
        target_name=None,
        title=title,
    )
