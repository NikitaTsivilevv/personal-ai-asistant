# PROJECT_CONTEXT.md - Personal AI Assistant

**Last refreshed:** 2026-06-12 (closeout after the first real outbound call + D-14)
**Status:** PRs #1-#10 merged to `main`. **First REAL third-party call placed 2026-06-12** (Pizza Parking; transcript pulled from Neon). It exposed two defects, both fixed on branch **`feature/call-data-and-termination` (D-14, not yet merged → PR pending)** and live-validated: (#1) agent stated the owner's name "Nikita" instead of the booking name "Victoria" — root cause: `allowed_facts` is a profile-key whitelist, not a value carrier, so the booking name was dropped before the prompt. Fixed with a new `StructuredGoal.call_facts` channel (NLP → bot card → `DETAILS FOR THIS CALL` prompt block → few-shot rewrite); eval `restaurant/booking_third_party` ×3 says Victoria, never Nikita. (#3) agent never called `end_call`, run stuck `running` — fixed with a stronger prompt rule + a deterministic in-call backstop (`TerminationGuard` duration/turn caps) that guarantees a hangup + terminal status regardless of the LLM. 150 tests pass, ruff clean. Prior context: D-12/D-13 scenario routing + eval harness shipped on `main`. **Still open:** voluntary `end_call` unreliable on haiku (backstop covers prod; model-floor reassessment D-11); role drift at the data stage when a datum is missing (#2); over-claim (#4); STT mishears proper nouns; word-by-word transcript. Dev-stand supervision (D-12 c) still pending. Turn detection still awaiting live audio validation.

## Current Goal

An AI assistant that performs phone-based personal/admin tasks with live user control, approvals, transcripts, summaries, safe data use, and conservative inbound handling. Product goal in `docs/product/personal-ai-assistant-tz.md`. Strategy (D-7): build for self 6-12 months, EU/Spain compliance-first niche, then decide on commercialization.

## Current Decisions

See `DECISIONS.md` for the authoritative log. Most recent: D-11 (claude-haiku-4-5 conversation LLM), D-12 (eval-driven development, scenario-routing wiring, reliability before scale), **D-13 (scenario routing wired into intake; eval harness architecture; eval_role_drift retired)**.

## Tech Status

Core stack accepted 2026-06-11 (D-5..D-9): Pipecat voice worker (Twilio + Deepgram + swappable LLM + Cartesia), FastAPI api, aiogram bot (separate process), minimal Next.js web, Postgres (Neon), Upstash Redis, uv workspace. Policy engine v1 (`packages/policy`) is rules-as-data with a code hard floor and autonomy levels 0-3. Eval harness (`packages/evals`) added with 6 case cards across 5 scenarios. 136 tests pass; ruff clean.

## How To Resume

For the next session, read:

1. `AGENTS.md`
2. This file
3. `DECISIONS.md` (focus D-11, D-12, **D-13**)
4. The relevant epic: `docs/epics/EPIC-002-outbound-calls.md` and `EPIC-003-policy-approvals.md`

## Immediate Next Steps

1. **Merge D-14**: open/merge the PR for `feature/call-data-and-termination` (call_facts + termination backstop). Branch is green (150 tests, ruff clean) and live-validated.
2. **Reliability/supervision** (D-12 c): process supervision + reconnect for api/bot; plan a move off the Cloudflare quick tunnel. (Real cause the test-call run was left `running` was likely worker stop, not just the missing `end_call`.)
3. **Role drift at the data stage** (#2): the few-shot fixes names; generalise it so the agent acknowledges *missing* data (e.g. party size) instead of asking the callee. Measure with `booking_third_party`/`booking_basic` role axis.
4. **Voluntary `end_call` / model floor** (D-11): decide whether haiku's low voluntary `end_call` rate warrants a model-floor change or the backstop is sufficient.
5. **Polish from the real call**: anti-over-claim prompt wording (#4); aggregate transcript to per-utterance + real `ts_ms`; Deepgram keyterm hints from `target_name`/`call_facts` (STT mishears). Plus the standing `fact_key` gap in `tools.py` and the two conservative-refusal eval cases.
6. **(needs a phone)** re-run the Pizza Parking task to confirm the fixes live; live validation of turn detection + role in full audio; then EPIC-003 phase D, EPIC-002 D1 real booking, EPIC-003 C2/C3.

## Operational Notes

- Run the stack locally: `uv run assistant-api`, `uv run assistant-bot`, `uv run assistant-worker` (worker also needs the Cloudflare tunnel + Twilio for real calls). Only ONE Telegram poller at a time (a second `assistant-bot` causes Telegram 409 and "not reacting").
- Run evals: `uv run python -m assistant_evals run --scenario doctor --runs 3` (from repo root). Results in `evals-results/` (gitignored).
- `.env` (not in git) holds tokens; `LLM_BASE_URL=https://api.anthropic.com/v1/`, `LLM_MODEL=claude-haiku-4-5`. Local process/tunnel logs match `*-session.log` (gitignored).
- Validation: `uv run pytest -q` (136), `uv run ruff check .`.
