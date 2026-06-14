# PROJECT_CONTEXT.md - Personal AI Assistant

**Last refreshed:** 2026-06-14 (whole-project audit + D-15; D-14 merged via PR #12)
**Status:** PRs #1-#10 merged to `main`. **First REAL third-party call placed 2026-06-12** (Pizza Parking; transcript pulled from Neon). It exposed two defects, both fixed (D-14, **merged to `main` via PR #12**) and live-validated: (#1) agent stated the owner's name "Nikita" instead of the booking name "Victoria" — root cause: `allowed_facts` is a profile-key whitelist, not a value carrier, so the booking name was dropped before the prompt. Fixed with a new `StructuredGoal.call_facts` channel (NLP → bot card → `DETAILS FOR THIS CALL` prompt block → few-shot rewrite); eval `restaurant/booking_third_party` ×3 says Victoria, never Nikita. (#3) agent never called `end_call`, run stuck `running` — fixed with a stronger prompt rule + a deterministic in-call backstop (`TerminationGuard` duration/turn caps) that guarantees a hangup + terminal status regardless of the LLM. 150 tests pass, ruff clean. Prior context: D-12/D-13 scenario routing + eval harness shipped on `main`. **Still open:** voluntary `end_call` unreliable on haiku (backstop covers prod; model-floor reassessment D-11); role drift at the data stage when a datum is missing (#2); over-claim (#4); STT mishears proper nouns; word-by-word transcript. Dev-stand supervision (D-12 c) still pending. Turn detection still awaiting live audio validation. **Audit 2026-06-14 (D-15):** the still-open defects are symptoms of two root causes — (1) the conversation LLM (haiku) is below the reliability floor for multi-turn tool-using voice, and (2) the dialog is a monolithic single-prompt agent (context rot), so patching each symptom with another prompt rule makes it worse; the text-edge eval is also blind to the audio/STT/backstop surface that actually broke the real call. Direction: migrate dialog to **Pipecat Flows** (per-node scoped tools/prompt), raise the model floor (**Gemini 2.5 Flash / GPT-4.1**, config-only per D-5), keep+strengthen the deterministic backstop (forced tool_choice), ground result-claims in tool results, **Nova-3 keyterm** STT, add an **audio eval tier**, and concentrate effort on the compliance/audit moat (D-7). Execution proceeds via brainstorm → spec → plan.

## Current Goal

An AI assistant that performs phone-based personal/admin tasks with live user control, approvals, transcripts, summaries, safe data use, and conservative inbound handling. Product goal in `docs/product/personal-ai-assistant-tz.md`. Strategy (D-7): build for self 6-12 months, EU/Spain compliance-first niche, then decide on commercialization.

## Current Decisions

See `DECISIONS.md` for the authoritative log. Most recent: D-11 (claude-haiku-4-5 conversation LLM), D-12 (eval-driven development, scenario-routing wiring, reliability before scale), D-13 (scenario routing + eval harness); D-14 (task-scoped `call_facts` + termination backstop). **D-15 (audit: stop symptom-patching; flow-based dialog, raise model floor, audio-aware evals, invest in the compliance moat)**.

## Tech Status

Core stack accepted 2026-06-11 (D-5..D-9): Pipecat voice worker (Twilio + Deepgram + swappable LLM + Cartesia), FastAPI api, aiogram bot (separate process), minimal Next.js web, Postgres (Neon), Upstash Redis, uv workspace. Policy engine v1 (`packages/policy`) is rules-as-data with a code hard floor and autonomy levels 0-3. Eval harness (`packages/evals`) added with 6 case cards across 5 scenarios. 136 tests pass; ruff clean.

## How To Resume

For the next session, read:

1. `AGENTS.md`
2. This file
3. `DECISIONS.md` (focus D-13, D-14, **D-15**)
4. The relevant epic: `docs/epics/EPIC-002-outbound-calls.md` and `EPIC-003-policy-approvals.md`

## Immediate Next Steps

Per the D-15 audit. **Next action: brainstorm → spec → plan** the change of method (architecture first), then execute in priority order:

1. **P0 — cheap, high-leverage (mostly config):** model A/B on the existing eval (haiku vs **Gemini 2.5 Flash / GPT-4.1**) to test the model-floor hypothesis; **Deepgram Nova-3 keyterm prompting** from `target_name`/`call_facts` (STT mishears); forced `tool_choice` at the terminal step so `end_call` is emitted, not "decided".
2. **P1 — architecture:** re-platform the dialog onto **Pipecat Flows** (per-node scoped sub-prompt + only the tools valid in that node), making role drift / wrong data / over-claim structurally impossible and letting a cheaper model survive. Likely its own epic.
3. **P2 — close eval blind spots:** add an **audio-in-the-loop eval tier** (TTS→STT→agent); fix honest gaps (`fact_key` not passed in `tools.py`; two conservative-refusal eval cases; prod/eval approval-timeout mismatch).
4. **P3 — moat + ops:** invest in the compliance/audit differentiator (D-7); process supervision + reconnect for api/bot and a move off the Cloudflare quick tunnel (D-12 c); transcript aggregation to per-utterance with real `ts_ms`.
5. **(needs a phone)** re-run the Pizza Parking task to confirm fixes live; live validation of turn detection + role in full audio; then EPIC-003 phase D, EPIC-002 D1 real booking, EPIC-003 C2/C3.

## Operational Notes

- Run the stack locally: `uv run assistant-api`, `uv run assistant-bot`, `uv run assistant-worker` (worker also needs the Cloudflare tunnel + Twilio for real calls). Only ONE Telegram poller at a time (a second `assistant-bot` causes Telegram 409 and "not reacting").
- Run evals: `uv run python -m assistant_evals run --scenario doctor --runs 3` (from repo root). Results in `evals-results/` (gitignored).
- `.env` (not in git) holds tokens; `LLM_BASE_URL=https://api.anthropic.com/v1/`, `LLM_MODEL=claude-haiku-4-5`. Local process/tunnel logs match `*-session.log` (gitignored).
- Validation: `uv run pytest -q` (136), `uv run ruff check .`.
