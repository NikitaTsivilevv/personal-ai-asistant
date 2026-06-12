# PROJECT_CONTEXT.md - Personal AI Assistant

**Last refreshed:** 2026-06-12 (closeout after PR #10 merge)
**Status:** PRs #1-#10 merged to `main`. **D-12 (a) DONE:** scenario routing live end-to-end — `SCENARIOS` constant consistency-tested, `normalize.py` extracts `scenario` (unknown → generic), bot confirm card shows scenario with one-tap correction. **D-12 (b) DONE:** eval harness (`packages/evals`) shipped and validated against real models — 6 case YAML cards across 5 scenarios, full Pipecat pipeline with text edges, LLM callee simulator, scripted approvals over the real control list, hybrid scoring, CLI with cost cap, JSON artifacts. Live smoke (haiku agent + judge=sonnet): `doctor/role_drift_probe` 3/3 — D-11 A/B caveat (tool-free, single-turn) now closed. `scripts/eval_role_drift.py` retired (absorbed into harness). See D-13. Turn detection + role drift fixes still awaiting live-call validation (phone needed). Dev stand fragility and supervisor work still pending (D-12 c).

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

1. **Reliability/supervision** (D-12 c): process supervision + reconnect for api/bot; plan a move off the Cloudflare quick tunnel.
2. **Few-shot generalisation now measurable** (D-12 d): generalise/scenario-ise the booking-flavoured few-shot using the harness; investigate haiku `end_call`/`propose_summary` omission (dominant reliability gap found in smoke run).
3. **Case-design follow-ups + fact_key gap**: confirm multi-run behavior of `insurance/cancel_denied` and `generic/approval_expiry` conservative-refusal false-fail before retuning; fix `tools.py` `ActionRequest` missing `fact_key` (fact-access deny branch unreachable from worker in production).
4. **(needs a phone)** live validation of turn detection + role-holding in full multi-turn context; then EPIC-003 phase D scenarios, EPIC-002 D1 real booking, EPIC-003 C2 (Transfer-to-me) / C3 (Take-over).

## Operational Notes

- Run the stack locally: `uv run assistant-api`, `uv run assistant-bot`, `uv run assistant-worker` (worker also needs the Cloudflare tunnel + Twilio for real calls). Only ONE Telegram poller at a time (a second `assistant-bot` causes Telegram 409 and "not reacting").
- Run evals: `uv run python -m assistant_evals run --scenario doctor --runs 3` (from repo root). Results in `evals-results/` (gitignored).
- `.env` (not in git) holds tokens; `LLM_BASE_URL=https://api.anthropic.com/v1/`, `LLM_MODEL=claude-haiku-4-5`. Local process/tunnel logs match `*-session.log` (gitignored).
- Validation: `uv run pytest -q` (136), `uv run ruff check .`.
