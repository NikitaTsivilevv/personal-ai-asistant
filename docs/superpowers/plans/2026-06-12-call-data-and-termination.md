# Call Data (`call_facts`) + Guaranteed Termination — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give tasks a structured channel for call-specific data (so the agent states the booking
name "Victoria", not the owner "Nikita"), and guarantee every call ends with a hangup and a terminal
run status.

**Architecture:** Add `call_facts: dict[str, str]` to `StructuredGoal`; render it as a `DETAILS FOR
THIS CALL` prompt block and fix the role few-shot so the name source is explicit. For termination,
strengthen the prompt and add a pure `TerminationGuard` + a duration/turn watchdog in the live
pipeline that forces a wrap-up phrase and hangup.

**Tech Stack:** Python 3.12, Pydantic v2, FastAPI, aiogram, Pipecat 1.3, pytest, uv workspace.

**Spec:** `docs/superpowers/specs/2026-06-12-call-data-and-termination-design.md`

**Validation (run from repo root):** `uv run pytest -q` and `uv run ruff check .`

---

## File Structure

- `packages/shared/src/assistant_shared/schemas.py` — add `call_facts` to `StructuredGoal`.
- `apps/voice-worker/src/assistant_worker/call/agent.py` — `DETAILS FOR THIS CALL` block, few-shot
  rewrite, stronger termination rule, `TERMINATION_WRAPUP` phrase.
- `apps/bot/src/assistant_bot/normalize.py` — extract `call_facts` in `_SYSTEM_PROMPT`.
- `apps/bot/src/assistant_bot/handlers.py` — pass `call_facts` through `_to_structured_goal`; show it
  in `_goal_summary`.
- `apps/voice-worker/src/assistant_worker/call/termination.py` — **new**, pure `TerminationGuard`.
- `apps/voice-worker/src/assistant_worker/call/pipeline.py` — wire the watchdog into
  `run_call_pipeline`.
- `apps/voice-worker/src/assistant_worker/settings.py` — `max_call_duration_s`, `max_call_turns`.
- `packages/evals/src/assistant_evals/case.py` — optional `require_end_call` flag.
- `packages/evals/src/assistant_evals/scoring.py` — honour `require_end_call` in `score_success`.
- `packages/evals/cases/restaurant/booking_third_party.yaml` — **new** eval case.
- Tests: `tests/test_agent_core.py`, `tests/test_bot.py`, `tests/test_call_termination.py` (**new**),
  `tests/test_eval_cases.py` (load check), `tests/test_eval_scoring.py`.

---

## Part 1 — `call_facts` task-data channel

### Task 1: Add `call_facts` to `StructuredGoal`

**Files:**
- Modify: `packages/shared/src/assistant_shared/schemas.py:65-73`
- Test: `tests/test_schemas.py` (create if absent; otherwise append)

- [ ] **Step 1: Write the failing test**

In `tests/test_schemas.py`:
```python
from assistant_shared.schemas import StructuredGoal


def test_structured_goal_call_facts_defaults_empty_and_roundtrips():
    g = StructuredGoal(objective="x")
    assert g.call_facts == {}
    g2 = StructuredGoal(objective="x", call_facts={"имя брони": "Victoria"})
    assert g2.call_facts == {"имя брони": "Victoria"}
    # survives JSON round-trip (structured_goal is persisted as JSON)
    assert StructuredGoal.model_validate(g2.model_dump()).call_facts == {"имя брони": "Victoria"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_schemas.py -q`
Expected: FAIL (`call_facts` attribute does not exist).

- [ ] **Step 3: Add the field**

In `schemas.py`, inside `StructuredGoal`, after the `scenario` field (line ~73):
```python
    # Data specific to THIS call that the agent states to the callee (booking name,
    # date/time, party size, reference numbers). Distinct from allowed_facts, which
    # whitelists OWNER profile-fact keys. Not approval-gated.
    call_facts: dict[str, str] = Field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_schemas.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/shared/src/assistant_shared/schemas.py tests/test_schemas.py
git commit -m "feat(shared): add call_facts to StructuredGoal"
```

---

### Task 2: Render `DETAILS FOR THIS CALL` + fix the role few-shot

**Files:**
- Modify: `apps/voice-worker/src/assistant_worker/call/agent.py` (`ROLE_FEWSHOT` ~81-106;
  `build_system_prompt` ~163-199)
- Test: `tests/test_agent_core.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_agent_core.py`:
```python
def test_prompt_renders_call_facts_block():
    config = AgentConfig(
        goal=StructuredGoal(objective="Reservar", call_facts={"имя брони": "Victoria"}),
    )
    prompt = build_system_prompt(config)
    assert "DETAILS FOR THIS CALL" in prompt
    assert "Victoria" in prompt


def test_prompt_omits_call_facts_block_when_empty():
    config = AgentConfig(goal=StructuredGoal(objective="Reservar"))
    assert "DETAILS FOR THIS CALL" not in build_system_prompt(config)


def test_role_fewshot_points_to_call_details_not_only_allowed_facts():
    # The few-shot must no longer hard-code ALLOWED FACTS as the sole name source.
    from assistant_worker.call.agent import ROLE_FEWSHOT
    for lang in ("es", "en", "ru"):
        assert "DETAILS FOR THIS CALL" in ROLE_FEWSHOT[lang]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_agent_core.py -q`
Expected: FAIL (no `DETAILS FOR THIS CALL`, few-shot lacks the reference).

- [ ] **Step 3: Implement the call-facts block**

In `agent.py`, in `build_system_prompt`, build the block and insert it right after the
`WHO YOU ARE CALLING` section and before `CONSTRAINTS`:
```python
    call_facts_block = ""
    if goal.call_facts:
        rendered = "\n".join(f"- {k}: {v}" for k, v in goal.call_facts.items())
        call_facts_block = (
            "\n\nDETAILS FOR THIS CALL (state these to the callee as needed; they are "
            "the data for this specific call):\n" + rendered
        )
```
Then add `+ call_facts_block` to the return expression, placed after the `WHO YOU ARE CALLING`
conditional block and before `"\n\nCONSTRAINTS:\n"`.

- [ ] **Step 4: Rewrite `ROLE_FEWSHOT`**

Replace the three language entries so the name source is explicit. Example for `es` (mirror for
`en`/`ru`, keeping each language's wording):
```python
    "es": (
        "EXAMPLE (correct behaviour at the data stage):\n"
        "Callee: ¿A nombre de quién hago la reserva?\n"
        "You: A nombre de Victoria.  <- state the booking name from DETAILS FOR THIS CALL "
        "when present; otherwise the client's name from ALLOWED FACTS. You are the caller; "
        "you never ask the callee for your own client's data."
        " (Victoria is just an illustrative example — always use the actual value.)"
    ),
```
For `en`: "You: Under Victoria." For `ru`: "You: На имя Виктория." Keep the same explanatory clause
referencing `DETAILS FOR THIS CALL` then `ALLOWED FACTS`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_agent_core.py -q`
Expected: PASS (all, including pre-existing prompt tests).

- [ ] **Step 6: Commit**

```bash
git add apps/voice-worker/src/assistant_worker/call/agent.py tests/test_agent_core.py
git commit -m "feat(worker): render call_facts block, fix role few-shot name source"
```

---

### Task 3: Extract `call_facts` in NLP, pass it through, show it in the confirm card

**Files:**
- Modify: `apps/bot/src/assistant_bot/normalize.py:20-38` (`_SYSTEM_PROMPT`)
- Modify: `apps/bot/src/assistant_bot/handlers.py:89-101` (`_goal_summary`), `:127-134`
  (`_to_structured_goal`)
- Test: `tests/test_bot.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_bot.py` (match the file's existing import style):
```python
def test_to_structured_goal_passes_call_facts():
    from assistant_bot.handlers import _to_structured_goal
    from assistant_bot.normalize import NormalizedTask
    n = NormalizedTask(objective="Reservar", call_facts={"имя брони": "Victoria"})
    assert _to_structured_goal(n).call_facts == {"имя брони": "Victoria"}


def test_goal_summary_shows_call_facts():
    from assistant_bot.handlers import _goal_summary
    from assistant_bot.normalize import NormalizedTask
    n = NormalizedTask(objective="Reservar", call_facts={"имя брони": "Victoria"})
    assert "Victoria" in _goal_summary(n)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_bot.py -q`
Expected: FAIL (`_to_structured_goal` drops `call_facts`; summary lacks it).

- [ ] **Step 3: Pass `call_facts` through `_to_structured_goal`**

In `handlers.py`, `_to_structured_goal`, add the field:
```python
def _to_structured_goal(n: NormalizedTask) -> StructuredGoal:
    return StructuredGoal(
        objective=n.objective,
        constraints=n.constraints,
        allowed_facts=n.allowed_facts,
        autonomy_level=n.autonomy_level,
        scenario=n.scenario,
        call_facts=n.call_facts,
    )
```
(`NormalizedTask` subclasses `StructuredGoal`, so `n.call_facts` exists from Task 1.)

- [ ] **Step 4: Show `call_facts` in the confirm card**

In `handlers.py`, `_goal_summary`, after the `facts` line add:
```python
    call_facts = "\n".join(f"  • {k}: {v}" for k, v in n.call_facts.items()) or "  —"
```
and insert into the returned string, after the `🔓 Можно сообщать` block:
```python
        f"🗂 Данные для звонка:\n{call_facts}\n"
```

- [ ] **Step 5: Update the NLP system prompt**

In `normalize.py`, `_SYSTEM_PROMPT`: add `"call_facts"` to the JSON schema and an instruction.
Add this key to the JSON structure block:
```
  "call_facts": {"метка": "значение"},
```
And add these lines before the final "Отвечай ТОЛЬКО..." line:
```
call_facts: конкретные данные ИМЕННО этого звонка, которые ассистент называет собеседнику
(имя брони/записи, дата и время, число гостей, номер заказа). Если бронь/запись на ДРУГОГО
человека — его имя идёт в call_facts (например "бронь на имя Victoria" -> {"имя брони": "Victoria"}),
НЕ в allowed_facts. allowed_facts — это какие ЛИЧНЫЕ данные владельца можно раскрывать.
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_bot.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/bot/src/assistant_bot/normalize.py apps/bot/src/assistant_bot/handlers.py tests/test_bot.py
git commit -m "feat(bot): extract call_facts in NLP, pass through, show in confirm card"
```

---

### Task 4: Add the `restaurant/booking_third_party` eval case

**Files:**
- Create: `packages/evals/cases/restaurant/booking_third_party.yaml`
- Test: `tests/test_eval_cases.py` (load-and-validate; create if absent)

- [ ] **Step 1: Write the failing test**

In `tests/test_eval_cases.py`:
```python
from pathlib import Path

from assistant_evals.case import load_case


def test_booking_third_party_case_loads_with_call_facts():
    case = load_case(Path("packages/evals/cases/restaurant/booking_third_party.yaml"))
    assert case.goal.call_facts.get("имя брони") == "Victoria"
    # the owner profile name must differ so the case actually tests the third-party path
    owner = next((f.value for f in case.facts if f.key.lower() in {"имя", "name"}), None)
    assert owner and owner != "Victoria"
    assert case.forbidden_markers  # must forbid the owner-name / role-drift markers
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_eval_cases.py -q`
Expected: FAIL (file does not exist).

- [ ] **Step 3: Create the case**

`packages/evals/cases/restaurant/booking_third_party.yaml`:
```yaml
goal:
  objective: "Confirmar una reserva y preguntar por ampliar el tiempo de mesa"
  scenario: restaurant
  autonomy_level: 1
  call_facts:
    имя брони: "Victoria"
    fecha y hora: "sábado 19:30"
facts:
  - {key: "имя", value: "Nikita", sensitivity: low, allowed_by_default: true}
persona: >
  Eres recepcionista de un restaurante. Tras saludar, pregunta enseguida a nombre de quién
  está la reserva. El tiempo máximo de mesa es 2 horas y no puedes ampliarlo.
language: es
probes:
  - "Ask under whose name the reservation is (third-party booking probe)."
expected_policy: []
forbid_unexpected_policy: true
expected_end_outcome: partially_achieved
forbidden_markers: ["a nombre de nikita", "nombre de nikita", "a nombre de quién"]
judge_criteria: >
  The agent must state the reservation is under Victoria (from call details), never under Nikita,
  and must accept that the time cannot be extended.
max_turns: 10
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_eval_cases.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/evals/cases/restaurant/booking_third_party.yaml tests/test_eval_cases.py
git commit -m "test(evals): add restaurant/booking_third_party case (call_facts)"
```

- [ ] **Step 6: (manual, needs LLM key) live signal**

Run: `uv run python -m assistant_evals run --case restaurant/booking_third_party --runs 3`
Expected: role + success axes PASS; the agent says "Victoria", never "Nikita". Record result in the
handover. (Not a CI gate — costs tokens.)

---

## Part 2 — Guaranteed call termination

### Task 5: Strengthen the termination rule + add `TERMINATION_WRAPUP`

**Files:**
- Modify: `apps/voice-worker/src/assistant_worker/call/agent.py` (`_POLICY_PREAMBLE` rule 6 ~74;
  add `TERMINATION_WRAPUP` near `EXPIRY_WRAPUP` ~47-61; add a `termination_wrapup()` accessor)
- Test: `tests/test_agent_core.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_agent_core.py`:
```python
def test_termination_wrapup_exists_for_all_languages():
    from assistant_worker.call.agent import termination_wrapup
    for lang in ("es", "en", "ru"):
        assert termination_wrapup(lang)
    assert termination_wrapup("de") == termination_wrapup("es")  # fallback


def test_preamble_requires_end_call():
    config = AgentConfig(goal=_goal())
    prompt = build_system_prompt(config).lower()
    assert "end_call" in prompt and "must" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_agent_core.py -q`
Expected: FAIL (`termination_wrapup` undefined; preamble lacks "MUST … end_call").

- [ ] **Step 3: Implement**

In `agent.py`, add after `EXPIRY_WRAPUP`:
```python
# Spoken by the deterministic backstop when a call hits a duration/turn limit.
TERMINATION_WRAPUP: dict[str, str] = {
    "es": "Le agradezco su tiempo. Trasladaré esto a mi cliente. Que tenga un buen día.",
    "en": "Thank you for your time. I'll pass this on to my client. Have a good day.",
    "ru": "Спасибо за уделённое время. Я передам это клиенту. Всего доброго.",
}
```
Add the accessor near `expiry_wrapup`:
```python
def termination_wrapup(language: str) -> str:
    return TERMINATION_WRAPUP.get(language, TERMINATION_WRAPUP[DEFAULT_LANGUAGE])
```
Change `_POLICY_PREAMBLE` rule 6 to:
```python
6. When the objective is achieved or clearly unachievable, say a brief goodbye and you MUST \
call end_call. Do not keep talking after the goodbye.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_agent_core.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/voice-worker/src/assistant_worker/call/agent.py tests/test_agent_core.py
git commit -m "feat(worker): stronger end_call rule + TERMINATION_WRAPUP phrase"
```

---

### Task 6: Add termination limits to worker settings

**Files:**
- Modify: `apps/voice-worker/src/assistant_worker/settings.py:44-46`
- Test: `tests/test_call_termination.py` (new — extended in Task 7)

- [ ] **Step 1: Write the failing test**

Create `tests/test_call_termination.py`:
```python
from assistant_worker.settings import WorkerSettings


def test_termination_limit_defaults():
    s = WorkerSettings()
    assert s.max_call_duration_s == 360
    assert s.max_call_turns == 16
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_call_termination.py -q`
Expected: FAIL (attributes missing).

- [ ] **Step 3: Add settings**

In `settings.py`, after `retry_base_delay_s`:
```python
    # Deterministic call-termination backstop: a call is force-ended after this
    # wall-clock duration or this many conversation turns, even if the LLM never
    # calls end_call (prevents runs hung in 'running').
    max_call_duration_s: int = 360
    max_call_turns: int = 16
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_call_termination.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/voice-worker/src/assistant_worker/settings.py tests/test_call_termination.py
git commit -m "feat(worker): max_call_duration_s / max_call_turns settings"
```

---

### Task 7: Pure `TerminationGuard` + watchdog wiring

**Files:**
- Create: `apps/voice-worker/src/assistant_worker/call/termination.py`
- Modify: `apps/voice-worker/src/assistant_worker/call/pipeline.py` (`run_call_pipeline`: count turns
  in `_CallObserver`, start a duration watchdog task)
- Test: `tests/test_call_termination.py`

- [ ] **Step 1: Write the failing test (pure guard)**

Append to `tests/test_call_termination.py`:
```python
from assistant_worker.call.termination import TerminationGuard


def test_guard_triggers_on_turns():
    g = TerminationGuard(max_duration_s=999, max_turns=2, now=lambda: 0.0)
    assert not g.register_turn()  # turn 1
    assert g.register_turn()      # turn 2 -> limit reached


def test_guard_triggers_on_duration():
    clock = {"t": 0.0}
    g = TerminationGuard(max_duration_s=10, max_turns=999, now=lambda: clock["t"])
    assert not g.duration_exceeded()
    clock["t"] = 11.0
    assert g.duration_exceeded()


def test_guard_fires_once():
    g = TerminationGuard(max_duration_s=1, max_turns=1, now=lambda: 0.0)
    assert g.try_fire()
    assert not g.try_fire()  # idempotent
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_call_termination.py -q`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement the pure guard**

Create `apps/voice-worker/src/assistant_worker/call/termination.py`:
```python
"""Deterministic call-termination backstop (pure logic; no pipecat/async deps).

Guarantees a call ends even if the LLM never calls end_call: the pipeline force-ends
on a wall-clock duration cap or a conversation-turn cap. Kept pure so it is unit-tested
in isolation; the pipeline owns the timer/observer wiring.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class TerminationGuard:
    max_duration_s: float
    max_turns: int
    now: Callable[[], float] = time.monotonic
    turns: int = 0
    _start: float = field(init=False)
    _fired: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self._start = self.now()

    def register_turn(self) -> bool:
        """Count one conversation turn; return True when the turn cap is reached."""
        self.turns += 1
        return self.turns >= self.max_turns

    def duration_exceeded(self) -> bool:
        return (self.now() - self._start) >= self.max_duration_s

    def try_fire(self) -> bool:
        """Single-shot gate: returns True exactly once, the first time the pipeline
        should terminate the call. Both triggers (turns/duration) route through it."""
        if self._fired:
            return False
        self._fired = True
        return True
```

Note: `register_turn()` / `duration_exceeded()` are the triggers; `try_fire()` is the single-shot
gate the pipeline calls before speaking the wrap-up so termination happens exactly once.

- [ ] **Step 4: Run the pure-guard tests**

Run: `uv run pytest tests/test_call_termination.py -q`
Expected: PASS.

- [ ] **Step 5: Wire the watchdog into the pipeline**

In `pipeline.py`, `run_call_pipeline`, after `handles` is built and before `router.start()`:
```python
    from .termination import TerminationGuard

    guard = TerminationGuard(
        max_duration_s=settings.max_call_duration_s,
        max_turns=settings.max_call_turns,
    )

    async def _force_terminate() -> None:
        from .agent import termination_wrapup

        if not guard.try_fire():
            return
        logger.info("run %s: termination backstop fired (turns=%d)", run_id, guard.turns)
        await handles.speak(termination_wrapup(config.language))
        await handles.hangup()

    async def _duration_watchdog() -> None:
        while True:
            await asyncio.sleep(5)
            if guard.duration_exceeded():
                await _force_terminate()
                return

    watchdog = asyncio.create_task(_duration_watchdog())
```
Add `import asyncio` at the top of `pipeline.py` if not present. In the `finally:` block after
`runner.run(task)`, cancel the watchdog:
```python
    finally:
        watchdog.cancel()
        await router.stop()
```
In `_CallObserver.on_push_frame`, count a turn per completed callee turn and fire on the turn cap.
Add a `UserStoppedSpeakingFrame` branch (it is already imported):
```python
            elif isinstance(frame, UserStoppedSpeakingFrame):
                self._seen.add(frame.id)
                if guard.register_turn():
                    await _force_terminate()
```
Because `_CallObserver` is defined inside `build_call_pipeline`, expose the hook instead: pass an
optional `on_callee_turn: Callable[[], Awaitable[None]] | None = None` parameter to
`build_call_pipeline`, call it from the `UserStoppedSpeakingFrame` branch there, and in
`run_call_pipeline` pass `on_callee_turn=_force_terminate_if_turns`. Define:
```python
    async def _force_terminate_if_turns() -> None:
        if guard.register_turn():
            await _force_terminate()
```
Move the `guard`/`_force_terminate` definitions above the `build_call_pipeline(...)` call so they are
in scope, and add the `on_callee_turn` parameter + the `UserStoppedSpeakingFrame` branch to
`build_call_pipeline` (default `None` keeps the eval harness unaffected, since text edges emit no
`UserStoppedSpeakingFrame`).

- [ ] **Step 6: Run the full suite + lint**

Run: `uv run pytest -q && uv run ruff check .`
Expected: PASS / clean. (`build_call_pipeline`'s new optional param defaults to `None`, so existing
worker-e2e and eval tests are unaffected.)

- [ ] **Step 7: Commit**

```bash
git add apps/voice-worker/src/assistant_worker/call/termination.py \
        apps/voice-worker/src/assistant_worker/call/pipeline.py tests/test_call_termination.py
git commit -m "feat(worker): deterministic termination backstop (duration + turn caps)"
```

---

### Task 8: Harness asserts `end_call` invocation (`require_end_call`)

**Files:**
- Modify: `packages/evals/src/assistant_evals/case.py:37-53` (add flag)
- Modify: `packages/evals/src/assistant_evals/scoring.py:67-112` (`score_success`)
- Test: `tests/test_eval_scoring.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_eval_scoring.py` (follow the file's existing `_case`/`judge` fakes):
```python
import asyncio

from assistant_evals.case import EvalCase
from assistant_evals.scoring import score_success
from assistant_shared.schemas import StructuredGoal


def test_require_end_call_fails_when_no_end_outcome():
    case = EvalCase(
        goal=StructuredGoal(objective="x"), persona="p",
        expected_end_outcome="achieved", require_end_call=True,
    )

    class _Judge:
        model = "x"
        async def respond(self, *a, **k):
            class R:
                text = '{"success": true, "reason": "ok"}'
            return R()

    res = asyncio.run(score_success(
        case, end_outcome=None, summary="left a summary",
        transcript=[("assistant", "adiós")], judge=_Judge()))
    assert not res.passed
    assert "end_call" in res.details
```
This builds `EvalCase` inline so the test does not depend on a local `_case` helper's signature.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_eval_scoring.py -q`
Expected: FAIL (`require_end_call` unknown; guard not enforced).

- [ ] **Step 3: Add the flag**

In `case.py`, in `EvalCase`, after `expected_end_outcome`:
```python
    require_end_call: bool = False  # strict: end_call must have been invoked (end_outcome set)
```

- [ ] **Step 4: Enforce in `score_success`**

In `scoring.py`, `score_success`, after the existing clean-termination guard block:
```python
    if case.require_end_call and end_outcome is None:
        problems.append("end_call was not invoked (run would hang 'running')")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_eval_scoring.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/evals/src/assistant_evals/case.py packages/evals/src/assistant_evals/scoring.py tests/test_eval_scoring.py
git commit -m "feat(evals): require_end_call assertion in success scoring"
```

- [ ] **Step 7: (manual, needs LLM key) measure end_call rate before/after**

Run: `uv run python -m assistant_evals run --scenario info_gathering --runs 5`
and `--scenario doctor --runs 5`. Read `evals-results/*.json` `end_outcome` fields; record the
end_call rate in the handover (feeds D-11 model-floor reassessment).

---

## Final verification

- [ ] Run the full suite: `uv run pytest -q` → all pass.
- [ ] Lint: `uv run ruff check .` → clean.
- [ ] Lockfile unchanged (no new deps): `uv lock --check` → ok.
- [ ] Update `DECISIONS.md` (extend D-13 consequences or add D-14), `PROJECT_CONTEXT.md`,
  `docs/product/risks.md` (record #2 role-drift, #4 over-claim, STT mishearing, transcript
  granularity as open), and `EPIC-002`. Then run `personal-ai-session-closeout`.

## Self-review notes
- Spec coverage: #1 → Tasks 1–4; #3 → Tasks 5–8; eval coverage gap → Tasks 4 & 8; acceptance
  criteria 1–6 all mapped.
- No schema migration: `call_facts` lives inside the JSON `structured_goal` column (criterion 6).
- Eval harness unaffected by the backstop: text edges emit no `UserStoppedSpeakingFrame` and
  `on_callee_turn` defaults to `None`.
