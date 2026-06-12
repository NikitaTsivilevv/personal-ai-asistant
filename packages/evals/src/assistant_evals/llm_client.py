"""Chat clients for the simulator and judge, with token usage tracking (spec: cost axis).

The agent's own usage is collected separately from pipecat metrics; this client covers
the simulator and judge calls, which go straight to the OpenAI-compat endpoint.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# USD per million tokens (input, output). Extend when new models are evaluated.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-4-6": (3.0, 15.0),
}


def cost_usd(model: str, *, input_tokens: int, output_tokens: int) -> float:
    if model not in PRICES_PER_MTOK:
        logger.warning("no price entry for model %r; counting cost as $0", model)
    in_price, out_price = PRICES_PER_MTOK.get(model, (0.0, 0.0))
    return (input_tokens * in_price + output_tokens * out_price) / 1_000_000


@dataclass
class ChatReply:
    text: str
    input_tokens: int
    output_tokens: int


class OpenAICompatChat:
    """Async chat over the OpenAI-compat endpoint (same env contract as the worker)."""

    def __init__(self, model: str, *, api_key: str | None = None, base_url: str | None = None):
        from openai import AsyncOpenAI

        self.model = model
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self._client = AsyncOpenAI(
            api_key=api_key or os.environ["LLM_API_KEY"],
            base_url=base_url or os.environ.get("LLM_BASE_URL") or None,
        )

    async def respond(self, system: str, messages: list[dict], max_tokens: int = 300) -> ChatReply:
        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, *messages],
            max_tokens=max_tokens,
        )
        usage = resp.usage
        in_tok = usage.prompt_tokens if usage else 0
        out_tok = usage.completion_tokens if usage else 0
        self.total_input_tokens += in_tok
        self.total_output_tokens += out_tok
        return ChatReply(resp.choices[0].message.content or "", in_tok, out_tok)


class FakeChat:
    """Scripted replies for tests; counts fake usage so cost code paths run."""

    def __init__(self, replies: list[str]):
        self.model = "fake"
        self._replies = list(replies)
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    async def respond(self, system: str, messages: list[dict], max_tokens: int = 300) -> ChatReply:
        text = self._replies.pop(0) if self._replies else ""
        self.total_input_tokens += 10
        self.total_output_tokens += 5
        return ChatReply(text, 10, 5)
