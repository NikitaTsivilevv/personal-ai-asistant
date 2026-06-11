# Live Call Quality: turn-detection + role-drift fixes (design)

**Date:** 2026-06-11
**Status:** Approved (brainstorming)
**Epics:** EPIC-002 (outbound calls), EPIC-003 (policy/approvals, downstream)
**Related decisions:** D-5 (Pipecat + swappable providers), D-11 (claude-haiku-4-5 via OpenAI-compat)
**Handover:** `docs/superpowers/handovers/HANDOVER-2026-06-11-live-call-quality.md`

## Problem

Live multi-turn calls work end-to-end (Twilio → Cloudflare quick tunnel → Pipecat 1.3 →
Deepgram → claude-haiku-4-5 via Anthropic OpenAI-compat → Cartesia), but two quality bugs
block EPIC-002 phase D (real booking) and EPIC-003 D live scenarios:

1. **Turn-detection loses callee utterances.** ~33 s from disclosure to first registered
   user turn. Speech during the bot's disclosure and short replies ("si, dime") don't close
   a turn (`User stopped speaking (strategy: None)`), so no LLM inference fires. The callee
   has to repeat 2-3 times.
2. **Residual role drift on haiku.** After the prompt fix (explicit `WHO YOU ARE CALLING`
   block), the call opens correctly but at the patient-data stage the bot slips back into
   the receptionist role ("¿A nombre de quién hago la reserva?") instead of stating the
   name from ALLOWED FACTS ("a nombre de Nikita").

There is also unmerged, validated work in the tree (queue ConnectionError resilience,
`InboundAudioProbe`, prompt role/sensitive fixes, +4 tests; 85 passed, ruff clean) that must
land first so later fixes branch from a clean base.

## Grounding (verified 2026-06-11 against the installed venv)

- `pipecat-ai == 1.3.0`. Declared extra: `pipecat-ai[deepgram,cartesia,openai,silero,websocket]`.
- Turn-taking in 1.3 lives in a **`pipecat.turns` subsystem**: `pipecat.turns.user_stop.*`
  stop strategies (`turn_analyzer_user_turn_stop_strategy`, `deferred_user_turn_stop_strategy`,
  `external_user_turn_completion_stop_strategy`) plus `pipecat.audio.turn.smart_turn.*`. The
  `strategy: None` log originates here.
- `vad_analyzer` / `turn_analyzer` are **not** fields of `TransportParams` in 1.3
  (`TransportParams.model_fields` does not contain them). The current code still passes
  `vad_analyzer=SileroVADAnalyzer()` to `FastAPIWebsocketParams` — this may be a silent no-op
  under pydantic and must be confirmed/fixed.
- `VADParams(confidence, start_secs, stop_secs, min_volume)` exists.
- `from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3`
  imports successfully. Instantiation pulls an ONNX model — verify it loads in our build.

## Scope

In scope (code completable and offline-verifiable by an agent):

- **A.** Land the unmerged working tree as PR1.
- **B.** Turn-detection fix in `apps/voice-worker/.../call/pipeline.py` (PR2).
- **C.** Role-drift fix in `apps/voice-worker/.../call/agent.py` + offline A/B harness (PR2).

Out of scope (requires a phone; owner runs after merge):

- Stage-1 formal acceptance (`/new → Approve → Reject → summary`).
- EPIC-003 D live scenarios (doctor/insurance/restaurant/expiry/pause-whisper).
- EPIC-002 D1 real restaurant booking.

Not touched (backlog): api-resilience to network blips, structural withholding of high-facts
until approval, logging Twilio 400 error bodies, named tunnel / VPS.

## Design

### A. PR1 — land the working tree

Mechanical. New branch `feature/stage2-night-resilience` off `main`. The tree already holds
queue resilience, `InboundAudioProbe`, prompt role/sensitive fixes, and +4 tests. No new
logic. Run `uv run pytest -q` and `uv run ruff check .`, commit, open PR. Boundary: only
commit already-validated changes (85 tests).

### B. PR2 fix 1 — turn-detection (pipecat 1.3 turns API)

Root cause: short replies and speech-over-disclosure never close a user turn. Steps:

1. **1.3 archaeology.** Read `pipecat/turns/user_stop/*` and `pipecat/audio/turn/smart_turn/*`
   to learn how 1.3 actually wires VAD + a stop strategy, and whether the existing
   `vad_analyzer=` kwarg to `FastAPIWebsocketParams` is honored or a silent no-op. Fix the
   wiring so VAD config is actually applied.
2. **VAD tuning.** Pass explicit `VADParams` (shorter `stop_secs`, tuned `confidence`,
   `min_volume`) so the turn closes sooner and short "si, dime" replies register.
3. **Smart-turn.** Wire `LocalSmartTurnAnalyzerV3` as the stop strategy (semantic
   end-of-turn instead of a pure timeout). Confirm the ONNX model loads in our build; if it
   cannot load offline, fall back to VAD-only tuning and record the blocker.
4. **Barge-in.** Enable interruptions so speech over the disclosure registers.
5. **Tests.** Config-level only: parameters are assembled and handed to the right place; the
   stop strategy / analyzer instantiates. Live validation is the owner's (one call).

Boundary: behavior is validated live by the owner; agent-side proof is config-level tests +
clean import/instantiation.

### C. PR2 fix 2 — role-drift (few-shot + offline A/B)

1. **Few-shot.** Add 1-2 short examples to the system prompt in `agent.py` showing the
   correct patient-data turn (state the name from ALLOWED FACTS, do not ask the callee). Keep
   it language-aware and small.
2. **Offline A/B harness.** `scripts/eval_role_drift.py` replays a scripted patient-data
   exchange through the real LLM with the real system prompt and asserts the assistant
   **states** the allowed name rather than asking for it. Run against `claude-haiku-4-5` and
   `claude-sonnet-4-6` and compare — this yields D-11 data **without a phone**. Real-model
   runs are gated behind an env flag / API key; CI uses a mock LLM.
3. **Tests.** Unit: the few-shot block lands in the assembled prompt. Harness: runs against a
   mock LLM in CI (deterministic), real models only on manual/env-gated runs.
4. **D-11 follow-up.** After the A/B run, append the result (which minimum tier holds the
   caller role) to D-11 / open-questions; switch the default model only if data justifies it.

Boundary: the harness proves drift offline against real models; the live A/B on the phone is
the owner's, but is no longer the only way to get the signal.

## Data flow / interfaces

- `pipeline.py` owns transport + VAD + turn strategy + barge-in (fix B). Single file.
- `agent.py` owns `build_system_prompt` and the few-shot block (fix C). Single file.
- `scripts/eval_role_drift.py` is a standalone harness importing `build_system_prompt` and the
  worker's LLM client config; no pipeline dependency.
- B and C do not share files → parallelizable as independent subagent tasks in PR2.

## Error handling

- Smart-turn V3 model fails to load → fall back to VAD-only tuning, log + record blocker, do
  not crash the pipeline.
- A/B harness with no API key → skip real-model path, run mock path, print a clear "set KEY to
  run real models" message; never fail CI on a missing key.

## Testing

- `uv run pytest -q` stays green (currently 85). New: config-level turn tests, few-shot
  prompt test, harness-against-mock test.
- `uv run ruff check .` clean.
- Live verification (owner, post-merge): one call for turn-detection; optionally the live A/B.

## Sequencing

PR1 (A) merges first. PR2 carries B + C as two independent tasks (different files), executed
via subagent-driven development, then a combined review and one PR.
