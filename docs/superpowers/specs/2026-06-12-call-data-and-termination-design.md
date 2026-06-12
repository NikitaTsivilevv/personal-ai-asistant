# Spec — Task-scoped call data (`call_facts`) + guaranteed call termination

**Date:** 2026-06-12
**Status:** Approved (brainstorming) — pending implementation plan
**Scope:** Two defects surfaced by the first real outbound call (run `84c4c3c6`, Pizza Parking,
2026-06-12): #1 the agent stated the wrong booking name, and #3 the agent never ended the call.
Role-drift at wrap-up (#2) and result over-claim (#4) are out of scope here and stay in `risks.md`.

## Evidence (real call, run 84c4c3c6)

- Task understood correctly: `target_name=Pizza Parking`, `scenario=restaurant`,
  `structured_goal.allowed_facts=["Victoria", "дата и время бронирования: суббота 19:30", ...]`.
  The NLP **did** extract "Victoria".
- Owner profile facts: `Имя=Nikita` (low, default), `nie=Y1715405X` (high, default), `номер машины`.
- In the call the agent said "en nombre de **Nikita**", answered "A nombre de **Nikita**" to
  "¿a nombre de quién?", and never said "Victoria".
- The agent said a full goodbye ("Muchas gracias y que disfruten…") but **never called `end_call`**;
  the run was left in status `running` with zero policy/tool events.

## Root causes

**#1 — wrong name.** `StructuredGoal.allowed_facts` is a **whitelist of profile-fact keys**, not a
carrier of values (`agent.py:142` `allowed_facts()` filters `config.facts` by `key`). "Victoria"
matched no profile fact key (`Имя`, `nie`, `номер машины`) and was silently dropped, so it never
reached the `ALLOWED FACTS` prompt block. The only name in that block was the owner's `Имя: Nikita`.
`ROLE_FEWSHOT` (`agent.py:81`) hard-instructs "STATE the name from ALLOWED FACTS", so the agent
confidently stated the owner's name. There is **no structured channel for data specific to this
call** (a booking under a third person, date/time, party size). It lives only as prose in
objective/constraints, which the few-shot actively steers away from.

**#3 — no termination.** Rule 6 of `_POLICY_PREAMBLE` ("wrap up politely and call `end_call`") is
too soft; haiku ignores it. The pipeline finalizes a run correctly **on media-stream close**
(`run_call_pipeline` → `EndFrame` → `run_call` → `completed`), but nothing forces the call to close
when the agent has verbally finished. The call hung open with no terminal status. (Worker-death
hangs are a separate gap, partly covered by the sweeper — out of scope, see Non-goals.)

## Part 1 — `call_facts`: task-scoped data channel

### Contract (`packages/shared/.../schemas.py`)
Add to `StructuredGoal`:
```python
call_facts: dict[str, str] = Field(default_factory=dict)
```
Semantics: concrete data for THIS call that the assistant states to the callee — booking/appointment
name, date/time, party size, order/reference numbers. Distinct from `allowed_facts` (a whitelist of
**owner profile-fact keys** the agent may disclose). `call_facts` are volunteered by the user for
this call.

Because `EvalCase.goal` is a `StructuredGoal` (`case.py:39`), eval cases get `call_facts` for free —
no `case.py` change needed.

### NLP (`apps/bot/.../normalize.py`, `_SYSTEM_PROMPT`)
Add `call_facts` to the extracted JSON and instruct the model to route:
- data/identity specific to this call, **including a booking under another person's name** →
  `call_facts` (e.g. "бронь на имя Victoria" → `{"имя брони": "Victoria"}`);
- which of the **owner's** personal data may be disclosed → `allowed_facts` (unchanged meaning).

`NormalizedTask`/`_to_structured_goal` (`handlers.py:127`) pass `call_facts` through to the task.

### Prompt (`apps/voice-worker/.../agent.py`, `build_system_prompt`)
- New block rendered near `OBJECTIVE`:
  ```
  DETAILS FOR THIS CALL:
  - имя брони: Victoria
  - дата и время: суббота 19:30
  ```
  Omitted when `call_facts` is empty.
- Rewrite `ROLE_FEWSHOT` so the name source is explicit: state the booking name from
  `DETAILS FOR THIS CALL` when present, otherwise the client's name from `ALLOWED FACTS`. This
  removes the hard "name = ALLOWED FACTS" coupling that produced "Nikita".

### Policy
`call_facts` are **not** approval-gated and do **not** enter the `disclose_fact` engine — they are
prompt content, not disclosure of a stored profile fact. `_policy_ctx` (`tools.py:125`) is unchanged.

### Bot confirm card (`handlers.py`, `_goal_summary`)
Render `call_facts` so the owner sees "имя брони: Victoria" before launching. Existing edit/scenario
controls unchanged.

### Eval (new case)
Add `packages/evals/cases/restaurant/booking_third_party.yaml`:
- `goal.call_facts: {"имя брони": "Victoria", ...}`, a profile fact `Имя` with a **different** owner
  name;
- persona asks "¿a nombre de quién?";
- assert the agent states **Victoria**; `forbidden_markers` include the owner name and
  "a nombre de quién".
This closes the "booking on behalf of a third person" class, which the current cases (client name ==
profile fact) cannot catch.

## Part 2 — Guaranteed call termination

### Prompt nudge (`agent.py`, `_POLICY_PREAMBLE` rule 6)
Strengthen: when the objective is achieved or clearly unachievable, say a brief goodbye and **you
MUST call `end_call`**; do not keep talking after the goodbye.

### Deterministic backstop (`apps/voice-worker/.../pipeline.py`) — model-independent
The call must always terminate and reach a terminal run status, even if the LLM never calls
`end_call`:
- Worker settings: `MAX_CALL_DURATION_S` (default ≈ 360) and `MAX_ASSISTANT_TURNS` (default ≈ 16).
- A lightweight in-pipeline guard (a small `FrameProcessor` in `post_llm`, or a counter in
  `_CallObserver` plus an `asyncio` duration timer on the `PipelineTask`) tracks assistant turns and
  elapsed time. On either limit it speaks a short wrap-up phrase (new key in `agent.py`, mirroring
  `EXPIRY_WRAPUP`) and calls `hangup()` (→ `EndFrame`). The existing `run_call` path then produces a
  summary and marks the run `completed`. Exact mechanism is a plan decision; the contract is: **a
  call always ends with a hangup and a terminal status.**

### Eval measurability
The harness already detects clean termination (`[HANGUP]` / `expected_end_outcome`). Add an explicit
assertion that `end_call` was invoked, and run `--runs 5` on `info_gathering`/`doctor` to measure the
prompt nudge before/after (this also discharges step 2 of the prior session's handover and feeds the
D-11 model-floor reassessment).

## Non-goals (tracked elsewhere)
- Role-drift at wrap-up ("que disfruten del cumpleaños" addressed to the callee) — #2, `risks.md`.
- Result over-claim ("la reserva está confirmada" when nothing was booked) — #4, `risks.md`.
- Process supervision / reconnect for api/bot and worker-death hangs — D-12 (c); the sweeper already
  aborts stale runs.
- STT mishearing ("Pizza Parking" → "Pisopaylink") and word-by-word transcript granularity with
  synthetic `ts_ms` — note in `risks.md`/open-questions; not addressed here.

## Acceptance criteria
1. A task with a booking under a third person produces `structured_goal.call_facts` containing that
   name; the bot confirm card shows it.
2. `build_system_prompt` renders a `DETAILS FOR THIS CALL` block from `call_facts` and the few-shot
   no longer hard-codes ALLOWED FACTS as the name source.
3. New eval case `restaurant/booking_third_party` passes: agent states the `call_facts` name, never
   the owner name, across `--runs 3`.
4. A call that reaches `MAX_CALL_DURATION_S` or `MAX_ASSISTANT_TURNS` ends with a hangup and the run
   reaches a terminal status (`completed`/`failed`), never left `running`.
5. The harness asserts `end_call` invocation; measured `end_call` rate on `info_gathering`/`doctor`
   over `--runs 5` is reported before/after the prompt nudge.
6. `uv run pytest -q` and `uv run ruff check .` are clean; no schema migration needed (`call_facts`
   lives in the JSON `structured_goal`, not a new column).
