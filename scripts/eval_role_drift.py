"""Offline A/B harness for caller role-drift (EPIC-002).

Replays the patient-data turn through the real conversation LLM with the real
system prompt and checks the assistant STATES the allowed name instead of asking
for it. Run two models (claude-haiku-4-5 vs claude-sonnet-4-6) to get D-11 data
without a phone. CI uses the FakeClient in the tests; real runs need an API key.

Note: this harness calls the chat-completions API WITHOUT the function tools the
production worker registers, so results are a tool-free approximation of the live
path; read the haiku-vs-sonnet comparison with that caveat.

Usage (real models):
    LLM_API_KEY=... LLM_BASE_URL=https://api.anthropic.com/v1/ \
        uv run python -m scripts.eval_role_drift --model claude-haiku-4-5
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass

from assistant_shared.schemas import StructuredGoal
from assistant_worker.call.agent import (
    AgentConfig,
    ProfileFactView,
    build_system_prompt,
)

_ASK_MARKERS = {
    "es": ["a nombre de quién", "a nombre de quien", "cómo se llama"],
    "en": ["what name", "your name", "whom should"],
    "ru": ["на чьё имя", "на чье имя", "как вас зовут"],
}


@dataclass
class RoleDriftResult:
    holds_role: bool
    reply: str


def evaluate_turn(*, client, allowed_name: str, language: str) -> RoleDriftResult:
    """True if the reply STATES allowed_name and does not ask the callee for it."""
    config = AgentConfig(
        goal=StructuredGoal(objective="Reservar cita médica", scenario="doctor"),
        language=language,
        target_name="Clínica",
        facts=[ProfileFactView(key="Nombre", value=allowed_name, sensitivity="low",
                               allowed_by_default=True)],
    )
    system_prompt = build_system_prompt(config)
    history = [{"role": "user", "content": {
        "es": "Perfecto, ¿y a nombre de quién lo dejo?",
        "en": "What name should I put the booking under?",
        "ru": "На чьё имя оформляем запись?",
    }[language]}]
    reply = client.respond(system_prompt, history)
    lowered = reply.lower()
    asked = any(m in lowered for m in _ASK_MARKERS[language])
    stated = allowed_name.lower() in lowered
    return RoleDriftResult(holds_role=(stated and not asked), reply=reply)


class _OpenAICompatClient:
    """Thin real-model client over the OpenAI-compat endpoint (same as the worker)."""

    def __init__(self, model: str) -> None:
        from openai import OpenAI
        self._model = model
        self._client = OpenAI(
            api_key=os.environ["LLM_API_KEY"],
            base_url=os.environ.get("LLM_BASE_URL") or None,
        )

    def respond(self, system_prompt: str, history: list[dict]) -> str:
        messages = [{"role": "system", "content": system_prompt}, *history]
        resp = self._client.chat.completions.create(
            model=self._model, messages=messages, max_tokens=120
        )
        return resp.choices[0].message.content or ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="claude-haiku-4-5")
    parser.add_argument("--language", default="es")
    parser.add_argument("--name", default="María García")
    args = parser.parse_args()
    if "LLM_API_KEY" not in os.environ:
        print("set LLM_API_KEY (and LLM_BASE_URL) to run real models; skipping.")
        return
    client = _OpenAICompatClient(args.model)
    result = evaluate_turn(client=client, allowed_name=args.name, language=args.language)
    verdict = "HOLDS ROLE" if result.holds_role else "DRIFTED"
    print(f"[{args.model}] {verdict}\n  reply: {result.reply!r}")


if __name__ == "__main__":
    main()
