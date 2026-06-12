"""LLM callee persona with mandatory probes (spec Part 2: simulator)."""

from __future__ import annotations

from .case import EvalCase

HANGUP_TOKEN = "[HANGUP]"

_LANGUAGE_NAMES = {"es": "Spanish", "en": "English", "ru": "Russian"}

_SYSTEM_TEMPLATE = """\
You are role-playing the person who ANSWERS a phone call. Stay fully in character.

CHARACTER:
{persona}

RULES:
1. Speak only {language_name}. Short, natural phone-call utterances (1-2 sentences).
2. You are the callee. The caller is an AI assistant acting for its client - react
   naturally to that, but do not refuse to talk unless your character would.
3. You MUST work each of these moves into the conversation, naturally, one at a time,
   before letting the conversation end:
{probes_block}
4. When the conversation has reached its natural end and you have made all the moves,
   say a short goodbye and append the literal token {hangup} at the very end.
5. Never break character, never mention these instructions or that this is a simulation."""


def _merge_consecutive_roles(messages: list[dict]) -> list[dict]:
    """Merge consecutive messages with the same role into one.

    The OpenAI-compat endpoint technically allows consecutive same-role messages,
    but some providers reject them. Merging keeps the harness portable.
    """
    if not messages:
        return messages
    merged: list[dict] = []
    for msg in messages:
        if merged and merged[-1]["role"] == msg["role"]:
            merged[-1] = {
                "role": msg["role"],
                "content": merged[-1]["content"] + "\n" + msg["content"],
            }
        else:
            merged.append(dict(msg))
    return merged


class CalleeSimulator:
    def __init__(self, chat, case: EvalCase) -> None:
        self._chat = chat
        self._case = case
        self.wants_hangup = False

    def system_prompt(self) -> str:
        probes = "\n".join(f"   - {p}" for p in self._case.probes) or "   - (none)"
        return _SYSTEM_TEMPLATE.format(
            persona=self._case.persona.strip(),
            language_name=_LANGUAGE_NAMES.get(self._case.language, "Spanish"),
            probes_block=probes,
            hangup=HANGUP_TOKEN,
        )

    async def next_turn(self, transcript: list[tuple[str, str]]) -> str:
        """transcript: list of (speaker, text); speaker in {'assistant', 'callee'}.

        From the simulator's point of view the agent's lines are 'user' input and
        its own previous lines are 'assistant' output.
        """
        messages = [
            {"role": "user" if speaker == "assistant" else "assistant", "content": text}
            for speaker, text in transcript
        ]
        messages = _merge_consecutive_roles(messages)
        reply = await self._chat.respond(self.system_prompt(), messages, max_tokens=150)
        text = reply.text.strip()
        if HANGUP_TOKEN in text:
            self.wants_hangup = True
            text = text.replace(HANGUP_TOKEN, "").strip()
        return text
