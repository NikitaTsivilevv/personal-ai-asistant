# Live Call Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the validated night-session working tree as PR1, then fix the two live-call quality bugs (turn-detection losing callee utterances; haiku role drift) as PR2.

**Architecture:** PR1 is a mechanical commit of already-green changes plus the new design/handover docs and a `.gitignore` entry. PR2 carries two independent fixes in non-overlapping files: turn-detection config in `apps/voice-worker/.../call/pipeline.py` (Task 2) and role-drift few-shot + offline A/B harness in `apps/voice-worker/.../call/agent.py` + `scripts/` (Task 3). VAD/turn behaviour is made testable by extracting small builder functions that unit tests assert on; live validation is the owner's, post-merge.

**Tech Stack:** Python 3.12, uv workspace, pytest, ruff, pipecat-ai 1.3.0 (Silero VAD + `LocalSmartTurnAnalyzerV3` smart-turn), Anthropic OpenAI-compat LLM (claude-haiku-4-5 / claude-sonnet-4-6).

**Spec:** `docs/superpowers/specs/2026-06-11-live-call-quality-design.md`

---

## File Structure

- `.gitignore` — add `.cloudflared-session.log` (Task 1).
- `apps/voice-worker/src/assistant_worker/call/pipeline.py` — add `build_vad_analyzer()` and
  `build_turn_analyzer()` builders; wire tuned VAD + smart-turn + barge-in into the transport
  per the 1.3 turns API (Task 2). One file, already the pipeline assembly layer.
- `apps/voice-worker/src/assistant_worker/call/agent.py` — add a language-aware few-shot block
  to `build_system_prompt` (Task 3).
- `scripts/eval_role_drift.py` — standalone offline A/B harness (Task 3). New file; imports
  `build_system_prompt`, no pipeline dependency.
- `tests/test_turn_config.py` — config-level tests for Task 2 builders (new).
- `tests/test_agent_core.py` — extend with few-shot prompt test (Task 3).
- `tests/test_eval_role_drift.py` — harness-against-mock test (Task 3, new).

Task 2 (`pipeline.py`) and Task 3 (`agent.py` + `scripts/`) touch disjoint files → executable
in parallel after PR1 merges.

---

## Task 1: PR1 — land the validated working tree

**Files:**
- Create branch: `feature/stage2-night-resilience` off `main`
- Modify: `.gitignore` (add `.cloudflared-session.log`)
- Commit (already modified, validated): `packages/shared/src/assistant_shared/queue.py`,
  `apps/voice-worker/src/assistant_worker/call/pipeline.py`,
  `apps/voice-worker/src/assistant_worker/call/agent.py`,
  `tests/test_queue_timeouts.py`, `tests/test_agent_core.py`, and the doc updates
  (`DECISIONS.md`, `PROJECT_CONTEXT.md`, `docs/epics/EPIC-002-outbound-calls.md`,
  `docs/epics/EPIC-003-policy-approvals.md`, `docs/product/open-questions.md`,
  `docs/product/risks.md`)
- Add (untracked docs): `docs/superpowers/handovers/HANDOVER-2026-06-11-live-call-quality.md`,
  `docs/superpowers/specs/2026-06-11-live-call-quality-design.md`,
  `docs/superpowers/plans/2026-06-11-live-call-quality.md`

- [ ] **Step 1: Create the branch off main**

```bash
git checkout main
git checkout -b feature/stage2-night-resilience
```

Expected: `Switched to a new branch 'feature/stage2-night-resilience'`

- [ ] **Step 2: Verify the tree is green before committing**

Run:
```bash
uv run pytest -q
uv run ruff check .
```
Expected: `85 passed` (or more), ruff `All checks passed!`. If anything fails, STOP and report
— do not "fix" night-session work blind; it was green at handover.

- [ ] **Step 3: Gitignore the cloudflared session log**

Append to `.gitignore` (do not commit the log itself — it is local tunnel session output):

```gitignore
.cloudflared-session.log
```

- [ ] **Step 4: Verify the log is now ignored**

Run: `git status --short`
Expected: `.cloudflared-session.log` no longer appears; modified files, the `.gitignore`
change, and the three untracked docs do appear.

- [ ] **Step 5: Stage everything except the ignored log**

```bash
git add -A
git status --short
```
Expected: all `M` files, `.gitignore`, and the three docs staged (`A`/`M`); no
`.cloudflared-session.log`.

- [ ] **Step 6: Commit**

```bash
git commit -m "feat: night-session resilience + call-quality design docs

- queue: survive redis ConnectionError in dequeue_run/wait_control (+2 tests)
- worker: InboundAudioProbe between transport.input() and STT
- agent: WHO YOU ARE CALLING role block + [SENSITIVE] fact marking (+2 tests)
- docs: live-call-quality handover, spec, and implementation plan
- gitignore .cloudflared-session.log

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 7: Push and open the PR**

```bash
git push -u origin feature/stage2-night-resilience
gh pr create --base main --title "Night-session resilience + call-quality design docs" --body "$(cat <<'EOF'
## Summary
Lands the validated night-session working tree and the design/plan docs for the live-call
quality fixes.

- Queue survives Upstash TLS drops (`redis.ConnectionError` retry) in `dequeue_run`/`wait_control`.
- `InboundAudioProbe` diagnoses "bot hears nothing" (frame count + peak amplitude).
- Agent prompt: explicit `WHO YOU ARE CALLING` role block; `[SENSITIVE]` fact marking.
- Docs: handover + spec + plan for turn-detection and role-drift fixes (PR2).

## Validation
- `uv run pytest -q` → 85 passed
- `uv run ruff check .` → clean

## Out of scope
Turn-detection and role-drift code fixes land in a follow-up PR (see the plan doc). Live
acceptance (Stage 1, EPIC-003 D scenarios, D1 booking) is run on the phone by the owner.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL printed.

---

## Task 2: PR2 fix 1 — turn-detection (pipecat 1.3 turns API)

**Branch:** `feature/stage2-turn-detection` off `main` (after PR1 merges).

**Files:**
- Modify: `apps/voice-worker/src/assistant_worker/call/pipeline.py`
- Test: `tests/test_turn_config.py` (create)

**Context the engineer needs (verified against the installed venv):**
- `pipecat-ai == 1.3.0`. `TransportParams` (in `pipecat/transports/base_transport.py`) has
  **no** `vad_analyzer` or `turn_analyzer` field, and pydantic ignores unknown kwargs. So the
  current `FastAPIWebsocketParams(... vad_analyzer=SileroVADAnalyzer() ...)` in `pipeline.py`
  is a **silent no-op** — that is the root cause: VAD config never takes effect, leaving
  default turn behaviour (`strategy: None`).
- Turn-taking in 1.3 lives in `pipecat/turns/user_stop/*` (stop strategies:
  `turn_analyzer_user_turn_stop_strategy`, `deferred_user_turn_stop_strategy`,
  `external_user_turn_completion_stop_strategy`) and `pipecat/audio/turn/smart_turn/*`.
- `VADParams(confidence, start_secs, stop_secs, min_volume)` — import from
  `pipecat.audio.vad.vad_analyzer`.
- `from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3` —
  imports cleanly; instantiation pulls an ONNX model (may need network/cache).

- [ ] **Step 1: Investigate the 1.3 turns wiring (bounded, ~10 min)**

Read these exact files and answer the three questions below; capture answers as a comment
block at the top of the change. Do NOT skip — the attach points differ from 1.2.
- `.venv/Lib/site-packages/pipecat/transports/websocket/fastapi.py` (how `FastAPIWebsocketTransport`/`...Params` take VAD/turn config in 1.3, if at all)
- `.venv/Lib/site-packages/pipecat/turns/user_stop/__init__.py` and
  `.venv/Lib/site-packages/pipecat/turns/user_stop/turn_analyzer_user_turn_stop_strategy.py`
- `.venv/Lib/site-packages/pipecat/audio/turn/smart_turn/base_smart_turn.py`
- `.venv/Lib/site-packages/pipecat/audio/vad/silero.py` (how `SileroVADAnalyzer` takes `VADParams`)

Questions to resolve:
1. **Where does VAD attach in 1.3?** (transport param under a different name, the STT service,
   the user-context aggregator, or a `PipelineTask`/turn-controller param)
2. **Where does the smart-turn stop strategy attach?** (same set of candidates)
3. **Where is barge-in / interruptions enabled?** (e.g. an `allow_interruptions` flag on the
   aggregator, the `PipelineTask`, or a turn-controller — `PipelineParams` in 1.3.0 does
   **not** expose it, confirmed)

- [ ] **Step 2: Write the failing config test**

Create `tests/test_turn_config.py`. Tests the extracted builders, not pipecat runtime:

```python
import pytest

pipecat = pytest.importorskip("pipecat")  # skip if the 'call' extra isn't installed

from assistant_worker.call.pipeline import build_vad_analyzer, build_turn_analyzer


def test_vad_analyzer_uses_tuned_params():
    vad = build_vad_analyzer()
    params = vad.params  # SileroVADAnalyzer stores VADParams on .params
    # Shorter stop than the 0.8s default so short replies close a turn.
    assert params.stop_secs <= 0.5
    assert 0.0 < params.confidence <= 1.0
    assert params.min_volume >= 0.0


def test_turn_analyzer_builds_or_falls_back():
    # Returns a smart-turn analyzer, or None if the ONNX model can't load.
    analyzer = build_turn_analyzer()
    assert analyzer is None or analyzer.__class__.__name__ == "LocalSmartTurnAnalyzerV3"
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/test_turn_config.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_vad_analyzer'` (or skip if extra
absent; if skipped, install the call extra: `cd apps/voice-worker && uv sync --extra call`).

- [ ] **Step 4: Add the builder functions**

In `apps/voice-worker/src/assistant_worker/call/pipeline.py`, inside the `if PIPECAT_AVAILABLE:`
block, add the import and two builders. Tune `stop_secs` down from the 0.8s default so short
"si, dime" replies close a turn; keep `confidence`/`min_volume` moderate to avoid false
triggers on hold music.

```python
    from pipecat.audio.vad.vad_analyzer import VADParams

    def build_vad_analyzer() -> "SileroVADAnalyzer":
        """Silero VAD tuned for short Spanish call-centre replies.

        Default stop_secs (0.8s) was too long: short utterances never closed a
        turn. 0.4s closes turns faster while staying above word-gap pauses.
        """
        return SileroVADAnalyzer(
            params=VADParams(confidence=0.6, start_secs=0.2, stop_secs=0.4, min_volume=0.5)
        )

    def build_turn_analyzer():
        """Semantic end-of-turn classifier (smart-turn V3).

        Falls back to None (VAD-only) if the ONNX model can't load offline, so a
        provisioning host without the model still runs calls.
        """
        try:
            from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import (
                LocalSmartTurnAnalyzerV3,
            )

            return LocalSmartTurnAnalyzerV3()
        except Exception as exc:  # model download / load failure
            logger.warning("smart-turn V3 unavailable, VAD-only turn-taking: %s", exc)
            return None
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/test_turn_config.py -v`
Expected: PASS (or `test_turn_analyzer_builds_or_falls_back` passes via the None branch if the
model can't load — that is acceptable and logged).

- [ ] **Step 6: Wire the builders + barge-in into the pipeline per Step 1 findings**

Replace the silent-no-op `vad_analyzer=SileroVADAnalyzer()` and attach the smart-turn strategy
and interruptions at the attach points found in Step 1. The transport/aggregator/task
construction in `run_call_pipeline` currently reads:

```python
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            vad_analyzer=SileroVADAnalyzer(),   # <-- silent no-op in 1.3
            serializer=serializer,
        ),
    )
```

Change `vad_analyzer=SileroVADAnalyzer()` to `vad_analyzer=build_vad_analyzer()` **only if**
Step 1 confirms the transport honours it in 1.3; otherwise move VAD to the correct attach point
found in Step 1. Attach `build_turn_analyzer()` as the turn/stop strategy and enable
interruptions at the attach points from Step 1. Add a one-line comment at each attach point
citing the 1.3 source file that confirms it.

- [ ] **Step 7: Verify the full suite still passes**

Run:
```bash
uv run pytest -q
uv run ruff check .
```
Expected: all pass (Task-1 count + the 2 new tests), ruff clean.

- [ ] **Step 8: Commit**

```bash
git add apps/voice-worker/src/assistant_worker/call/pipeline.py tests/test_turn_config.py
git commit -m "fix(worker): tune VAD + smart-turn so short callee replies register

- build_vad_analyzer(): VADParams stop_secs 0.4s (was default 0.8s)
- build_turn_analyzer(): LocalSmartTurnAnalyzerV3 with VAD-only fallback
- wire VAD/turn/barge-in at the correct pipecat 1.3 turns attach points
  (previous vad_analyzer= kwarg was a silent no-op on TransportParams)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

**Boundary:** Live validation (one call: short replies + speech-over-disclosure register) is
the owner's, post-merge. Agent-side proof = config tests green + clean wiring.

---

## Task 3: PR2 fix 2 — role-drift few-shot + offline A/B harness

**Branch:** same PR2 branch as Task 2 if executed together, else `feature/stage2-role-drift`
off `main`. Touches different files than Task 2, so no conflict.

**Files:**
- Modify: `apps/voice-worker/src/assistant_worker/call/agent.py`
- Modify: `tests/test_agent_core.py`
- Create: `scripts/eval_role_drift.py`
- Create: `tests/test_eval_role_drift.py`

**Context:** `build_system_prompt(config)` in `agent.py` assembles the system prompt from
`_POLICY_PREAMBLE`, OBJECTIVE, the `WHO YOU ARE CALLING` block, CONSTRAINTS, ALLOWED FACTS,
AUTONOMY LEVEL, and whispers. `_LANGUAGE_NAMES = {"es","en","ru"}`. The drift: at the
patient-data stage haiku asks "¿A nombre de quién?" instead of stating the allowed name.

### Part 1 — few-shot block

- [ ] **Step 1: Write the failing few-shot prompt test**

Add to `tests/test_agent_core.py`:

```python
def test_prompt_includes_role_fewshot_for_es():
    from assistant_worker.call.agent import AgentConfig, build_system_prompt, ProfileFactView
    from assistant_shared.schemas import StructuredGoal

    config = AgentConfig(
        goal=StructuredGoal(objective="Reservar cita", scenario="doctor"),
        language="es",
        target_name="Clínica Dental",
        facts=[ProfileFactView(key="Nombre", value="Nikita", sensitivity="low",
                               allowed_by_default=True)],
    )
    prompt = build_system_prompt(config)
    assert "EXAMPLE" in prompt
    # The example must demonstrate STATING the name, not asking for it.
    assert "a nombre de" in prompt.lower()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_agent_core.py::test_prompt_includes_role_fewshot_for_es -v`
Expected: FAIL — `assert "EXAMPLE" in prompt` (no few-shot block yet).

- [ ] **Step 3: Add a language-aware few-shot block**

In `agent.py`, add the constant and append it in `build_system_prompt`:

```python
# Few-shot reinforcing the caller role at the data stage (EPIC-002 role-drift fix).
ROLE_FEWSHOT: dict[str, str] = {
    "es": (
        "EXAMPLE (correct behaviour at the data stage):\n"
        "Callee: ¿A nombre de quién hago la reserva?\n"
        "You: A nombre de Nikita.  <- you STATE the name from ALLOWED FACTS; "
        "you are the caller, you never ask the callee for your own client's data."
    ),
    "en": (
        "EXAMPLE (correct behaviour at the data stage):\n"
        "Callee: And what name should I put the booking under?\n"
        "You: Under Nikita.  <- you STATE the name from ALLOWED FACTS; you are the "
        "caller, you never ask the callee for your own client's data."
    ),
    "ru": (
        "EXAMPLE (correct behaviour at the data stage):\n"
        "Callee: На чьё имя оформляем запись?\n"
        "You: На имя Nikita.  <- you STATE the name from ALLOWED FACTS; you are the "
        "caller, you never ask the callee for your own client's data."
    ),
}
```

Then in `build_system_prompt`, append it right after the `whisper_block` in the return
expression (the name in the example is illustrative; the model uses real ALLOWED FACTS):

```python
        + whisper_block
        + "\n\n"
        + ROLE_FEWSHOT.get(config.language, ROLE_FEWSHOT[DEFAULT_LANGUAGE])
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_agent_core.py::test_prompt_includes_role_fewshot_for_es -v`
Expected: PASS.

### Part 2 — offline A/B harness

- [ ] **Step 5: Write the failing harness test (mock LLM)**

Create `tests/test_eval_role_drift.py`:

```python
from scripts.eval_role_drift import evaluate_turn, RoleDriftResult


class _FakeClient:
    def __init__(self, reply: str) -> None:
        self._reply = reply

    def respond(self, system_prompt: str, history: list[dict]) -> str:
        return self._reply


def test_states_name_is_pass():
    result = evaluate_turn(
        client=_FakeClient("A nombre de Nikita."),
        allowed_name="Nikita",
        language="es",
    )
    assert isinstance(result, RoleDriftResult)
    assert result.holds_role is True


def test_asking_for_name_is_drift():
    result = evaluate_turn(
        client=_FakeClient("¿A nombre de quién hago la reserva?"),
        allowed_name="Nikita",
        language="es",
    )
    assert result.holds_role is False
```

- [ ] **Step 6: Run the test to verify it fails**

Run: `uv run pytest tests/test_eval_role_drift.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.eval_role_drift'`.

- [ ] **Step 7: Implement the harness**

Create `scripts/__init__.py` (empty) and `scripts/eval_role_drift.py`:

```python
"""Offline A/B harness for caller role-drift (EPIC-002).

Replays the patient-data turn through the real conversation LLM with the real
system prompt and checks the assistant STATES the allowed name instead of asking
for it. Run two models (claude-haiku-4-5 vs claude-sonnet-4-6) to get D-11 data
without a phone. CI uses the FakeClient in the tests; real runs need an API key.

Usage (real models):
    LLM_API_KEY=... LLM_BASE_URL=https://api.anthropic.com/v1/ \
        uv run python -m scripts.eval_role_drift --model claude-haiku-4-5
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass

from assistant_worker.call.agent import (
    AgentConfig,
    ProfileFactView,
    build_system_prompt,
)
from assistant_shared.schemas import StructuredGoal

# Phrasings that mean "asking the callee for the client's own data" = drift.
_ASK_MARKERS = {
    "es": ["a nombre de quién", "a nombre de quien", "cómo se llama", "su nombre"],
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
        "es": "¿A nombre de quién hago la reserva?",
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
    parser.add_argument("--name", default="Nikita")
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
```

- [ ] **Step 8: Run the harness test to verify it passes**

Run: `uv run pytest tests/test_eval_role_drift.py -v`
Expected: PASS (both tests, against `_FakeClient`).

- [ ] **Step 9: Verify the full suite + lint**

Run:
```bash
uv run pytest -q
uv run ruff check .
```
Expected: all pass, ruff clean. If ruff flags `scripts/` import order or the `*history`
unpack, fix inline.

- [ ] **Step 10: Commit**

```bash
git add apps/voice-worker/src/assistant_worker/call/agent.py tests/test_agent_core.py scripts/eval_role_drift.py scripts/__init__.py tests/test_eval_role_drift.py
git commit -m "fix(worker): few-shot to hold caller role + offline role-drift A/B harness

- agent: language-aware ROLE_FEWSHOT block (state the name, never ask the callee)
- scripts/eval_role_drift.py: replays the data-stage turn through the real LLM,
  checks the assistant states the allowed name; haiku vs sonnet for D-11 data
- tests: few-shot in prompt; harness against a mock LLM

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

**Boundary:** real-model A/B run (`uv run python -m scripts.eval_role_drift --model ...` for
haiku and sonnet) and the D-11 follow-up note are the owner's call after reviewing harness
output; the harness makes drift measurable offline.

---

## Self-review notes

- **Spec coverage:** A→Task 1; B→Task 2; C→Task 3. Out-of-scope (live acceptance, EPIC-003 D,
  D1) explicitly deferred to the owner in both spec and plan. Error-handling (smart-turn ONNX
  fallback; missing API key) implemented in Task 2 Step 4 and Task 3 Step 7.
- **No placeholders:** every code step shows full code; the only investigation step (Task 2
  Step 1) names exact files and exact questions, then Steps 4/6 apply concrete param objects.
- **Type consistency:** `build_vad_analyzer`/`build_turn_analyzer` (Task 2) and `evaluate_turn`
  /`RoleDriftResult`/`respond(system_prompt, history)` (Task 3) are used identically across
  their tests and implementations.
