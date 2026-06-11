"""Free-text instruction -> StructuredGoal (plan task D2).

Uses Claude when an API key is configured; otherwise falls back to a heuristic
parse so the bot stays usable before any provider registration (plan risk note:
'if it stalls, fall back to a structured form-style dialog').
"""

from __future__ import annotations

import json
import logging
import re

from assistant_shared.schemas import StructuredGoal

from .settings import BotSettings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
Ты нормализуешь задачу для ИИ-ассистента, который звонит по телефону от имени клиента.
Из свободного текста пользователя извлеки JSON со структурой:
{
  "objective": "краткая цель звонка одним предложением",
  "constraints": ["ограничения и пожелания пользователя"],
  "allowed_facts": ["какие личные данные можно сообщать собеседнику"],
  "autonomy_level": 0-3,
  "target_phone": "телефон в международном формате или null",
  "target_name": "название организации/имя или null",
  "title": "короткий заголовок задачи"
}
autonomy_level: 0 - подтверждать каждое действие, 1 - по умолчанию, 2 - разрешены записи/переносы,
3 - максимум самостоятельности (платежи всё равно требуют подтверждения).
Отвечай ТОЛЬКО валидным JSON без пояснений."""


class NormalizedTask(StructuredGoal):
    title: str = "Задача"
    target_phone: str | None = None
    target_name: str | None = None


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
    raw = response.content[0].text
    # Strip optional markdown fences before parsing.
    raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    return NormalizedTask.model_validate(json.loads(raw))


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
