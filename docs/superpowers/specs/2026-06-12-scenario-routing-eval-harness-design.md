# Scenario Routing + Offline Eval Harness — Design

**Date:** 2026-06-12
**Status:** Approved (brainstormed with owner)
**Epics:** EPIC-002 (outbound calls), EPIC-003 (policy & approvals)
**Decisions:** implements D-12 items (a) and (b); feeds D-11 (model floor)

## Problem

1. The scenario system is built but dormant: `apps/bot/.../normalize.py` never extracts
   `scenario`, so `structured_goal.scenario` is always `generic` and the
   doctor/insurance/restaurant/info_gathering policy profiles plus scenario-scoped
   profile facts (`allowed_scenarios`) never activate.
2. There is no behavioral evaluation beyond `scripts/eval_role_drift.py`, which is
   tool-free and single-turn — prompt/model/scenario changes are made blind. A
   misclassified scenario changes which policy rules and facts apply, so scenario
   detection itself needs measurement too.

Both are fully offline (no phone needed). One workstream, one spec, two parts.

## Part 1 — Wire scenario detection into intake

### Scenario enum source of truth

The scenario list (`generic`, `doctor`, `insurance`, `restaurant`, `info_gathering`)
becomes a constant in `assistant_shared.schemas` next to `StructuredGoal` (the bot
must not depend on the policy package). The policy rule files remain the behavioral
definition; a test asserts the shared constant matches the rule files shipped in
`assistant_policy/rules/`.

### Extraction

- `_SYSTEM_PROMPT` in `normalize.py` gains a `"scenario"` field with the strict enum
  and the instruction: when unsure, use `generic`.
- `NormalizedTask` inherits `StructuredGoal`, so the field validates automatically.
- An out-of-enum value from the LLM coerces to `generic` with a warning log — never
  an error. The heuristic fallback keeps `generic`.

### Confirmation UX (bot)

- The task confirmation card shows the detected scenario
  («Сценарий: doctor») and an inline "Сменить сценарий" button.
- The button opens a one-tap choice of the five scenarios; the user's correction is
  written into `structured_goal.scenario` before the task is created.
- Rationale: a classification error changes the active policy profile, so the user
  must be able to see and fix it pre-call. `generic` stays the conservative default.

## Part 2 — Offline eval harness with LLM callee simulator

### Architecture decision: full pipecat pipeline with text edges

Chosen over a pipecat-free agent loop (owner decision): maximal fidelity — the eval
runs the same aggregators, LLM service, tool registration, toolbox, policy engine,
and control router as production, swapping only the audio edges.

Prerequisite refactor of `apps/voice-worker/.../call/pipeline.py`:

- `build_call_pipeline(...)` — pure assembly. Accepts pre-built transport edge
  processors (input/output), `stt | None`, `tts | None`, the LLM service, `config`,
  `toolbox`; returns the pipeline/task plus the observer hooks. No
  Twilio/Deepgram/Cartesia construction inside.
- `run_call_pipeline(...)` keeps its current signature and production behavior: it
  builds the Twilio transport, Deepgram STT, Cartesia TTS and calls the builder.
  Existing tests must pass unchanged.

Eval assembly (in the new evals package):

- **Input edge:** a source processor injects each simulator turn as
  `UserStartedSpeakingFrame → TranscriptionFrame → UserStoppedSpeakingFrame` (the
  user aggregator's native input). VAD/smart-turn are not attached in text mode —
  they cannot be exercised without audio and stay a live-validation item.
- **Output edge:** a passthrough capturer replaces TTS and records agent text,
  including `TTSSpeakFrame` phrases (disclosure, approval filler, deny phrase,
  expiry wrap-up) — these are part of observable behavior and belong in the eval
  transcript.
- **Real:** LLM service (OpenAI-compat, model configurable), context aggregators,
  `CallToolbox` (with the real `assistant_policy.evaluate()` inside),
  `ControlRouter`.
- **Faked:** Redis → fakeredis; `RunClient` → in-memory fake that records all
  events (`policy_decision`, approvals, status, transcript) for assertions.

### Package layout

New uv-workspace package `packages/evals` (`assistant_evals`), depending on
`assistant_worker[call]`. CLI:

```text
uv run python -m assistant_evals run [--scenario doctor] [--case <name>]
    [--model claude-haiku-4-5] [--runs 3] [--max-cost 5.0]
```

### Eval cases

One YAML card per case in `packages/evals/cases/<scenario>/<case>.yaml`:

- `goal`: the task's `StructuredGoal` (objective, constraints, allowed_facts,
  autonomy_level, scenario).
- `facts`: profile facts with sensitivity / allowed_by_default / allowed_scenarios.
- `persona`: callee description (clinic receptionist, insurance agent, …) + language.
- `probes`: ordered, mandatory moves the persona must make (ask the name, demand a
  DNI, offer a paid extra, …) — guarantees coverage of specific policy branches.
- `client_script`: for each expected approval, the simulated client's response:
  `approve` / `reject` / `expire` (no answer — exercises the expiry wrap-up path).
- `expectations`: expected `policy_decision` outcomes (rule_id + outcome per probe),
  target `end_call.outcome`, heuristic markers, judge criteria.
- `max_turns`: loop/budget guard.

### Callee simulator

A separate LLM call (model configurable, default haiku): system prompt = persona +
the not-yet-delivered probes. Plays naturally but must inject the probes. The
approval `client_script` is executed by the harness through the standard control
mechanism (fakeredis `run:{run_id}:control` list), so the waiting/expiry code paths
run for real.

### Scoring (hybrid: code where possible, judge where not)

Per case × N runs (default 3), five axes:

| Axis | Method |
|---|---|
| Policy correctness | Code: recorded `policy_decision` events (rule_id, outcome, action) vs expectations; plus a transcript assert that no high-sensitivity fact value is spoken before an approval. Binary, deterministic. |
| Task success | Code (`end_call.outcome`, `proposed_summary` present) + LLM judge (sonnet) over the transcript returning structured JSON (goal achieved? why). |
| Role-holding | Generalized `eval_role_drift` markers + a judge question. |
| Latency | Code: LLM TTFB from `MetricsCollector`, reported explicitly as "LLM TTFB, not end-to-end call latency". |
| Cost | Code: token usage of agent + simulator + judge, priced via a config table. |

### Output

- Console summary: case × axis, pass/fail/score, total cost.
- JSON artifact per run in `evals-results/` (gitignored): full transcript, all
  events, scores, config. Artifacts are the "record" mode — regression analysis on
  saved runs costs nothing.
- Non-zero exit code when the policy axis fails (it is binary and deterministic);
  thresholds for the soft axes are configurable.

## Testing

- Unit tests, no API key: scenario normalization (mocked LLM reply, including
  out-of-enum coercion), scenario-change button flow, builder assembles the eval
  pipeline, simulator/scoring against a FakeClient, case YAML parsing, shared
  enum ↔ rule-files consistency.
- Real-model runs are manual, key-gated (same convention as `eval_role_drift.py`).
- Existing suite (90 tests) and ruff must stay green; the pipeline refactor must not
  change production behavior.

## Budget

haiku agent + haiku simulator, 10–20 turns per case ≈ cents; a full sweep
(5 scenarios × ~2 cases × 3 runs) ≈ $1–3. The CLI prints actual cost; `--max-cost`
aborts the sweep when exceeded.

## Out of scope

- Dev-stand reliability (supervision, tunnel exit) — next workstream (D-12 c).
- Few-shot generalization — after the harness can measure it (D-12 d).
- Live validation of turn detection / role-holding, EPIC-003 phase D, EPIC-002 D1,
  C2/C3 — need a phone.
- Audio-level realism (PSTN noise, IVR, hold music): a simulated callee approximates
  but does not replace live calls (D-12 consequence).

## Consequences / follow-ups

- `scripts/eval_role_drift.py` is retired once the harness reproduces its check as a
  case (a doctor-scenario probe "ask whose name the booking is under").
- Eval results feed D-11 (model floor) and policy-rule tuning.
- Scenario detection quality becomes measurable: misrouting shows up as policy-axis
  failures in cross-scenario cases.
