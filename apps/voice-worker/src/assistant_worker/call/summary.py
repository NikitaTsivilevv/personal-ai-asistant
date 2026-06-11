"""Post-call summary: LLM-generated when a key is configured, otherwise a
deterministic template from agent-proposed summary + logged facts (spec §2)."""

from __future__ import annotations

import logging

from .tools import CallToolbox

logger = logging.getLogger(__name__)

_OUTCOME_LABELS = {
    "achieved": "Цель достигнута",
    "partially_achieved": "Цель достигнута частично",
    "not_achieved": "Цель не достигнута",
    "callee_refused": "Собеседник отказался говорить с ИИ-ассистентом",
}


def template_summary(toolbox: CallToolbox, transcript_tail: list[str] | None = None) -> str:
    parts: list[str] = []
    if toolbox.end_outcome:
        parts.append(_OUTCOME_LABELS.get(toolbox.end_outcome, toolbox.end_outcome) + ".")
    if toolbox.proposed_summary:
        parts.append(toolbox.proposed_summary)
    if toolbox.logged_facts:
        parts.append("Записанные факты: " + "; ".join(toolbox.logged_facts) + ".")
    if toolbox.proposed_next_steps:
        parts.append("Следующие шаги: " + toolbox.proposed_next_steps)
    if not parts:
        parts.append("Звонок завершён, агент не оставил итогов.")
        if transcript_tail:
            parts.append("Конец разговора: " + " / ".join(transcript_tail[-3:]))
    return " ".join(parts)


async def generate_summary(
    toolbox: CallToolbox,
    transcript: list[str],
    *,
    anthropic_api_key: str = "",
    model: str = "claude-haiku-4-5-20251001",
) -> str:
    """LLM summary over the full transcript; falls back to the template."""
    if not anthropic_api_key or anthropic_api_key.startswith("PLACEHOLDER"):
        return template_summary(toolbox, transcript)
    try:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=anthropic_api_key)
        response = await client.messages.create(
            model=model,
            max_tokens=500,
            system=(
                "Суммируй телефонный звонок ИИ-ассистента для его клиента. 2-4 предложения: "
                "итог относительно цели, ключевые договорённости/факты, следующие шаги. "
                "Пиши на языке клиента (русский)."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Цель звонка: {toolbox.config.goal.objective}\n\n"
                        f"Итог агента: {toolbox.proposed_summary or '-'}\n"
                        f"Факты: {'; '.join(toolbox.logged_facts) or '-'}\n\n"
                        "Транскрипт:\n" + "\n".join(transcript)
                    ),
                }
            ],
        )
        return response.content[0].text.strip()
    except Exception:
        logger.exception("LLM summary failed, using template")
        return template_summary(toolbox, transcript)
