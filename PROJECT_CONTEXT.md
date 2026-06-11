# PROJECT_CONTEXT.md - Personal AI Assistant

**Last refreshed:** 2026-06-11 (assessment + closeout session)
**Status:** PRs #1-#8 merged to `main`. The two live-call quality bugs are **fixed in code (PR #7), awaiting live validation**: turn detection (root cause: `vad_analyzer=` was a silent no-op on `FastAPIWebsocketParams` in pipecat 1.3 - VAD is now tuned and wired onto the user aggregator, plus `LocalSmartTurnAnalyzerV3`) and haiku role drift (language-aware few-shot; offline A/B in `scripts/eval_role_drift.py` shows haiku holds the caller role 3/3, so D-11 stays on `claude-haiku-4-5`). A session-end code assessment produced D-12 (next workstream) and surfaced that **the scenario system is built but not wired into intake** (`normalize.py` never sets `structured_goal.scenario`, so everything runs the `generic` policy profile). The dev stand stayed fragile: api+bot were found dead this session ("bot not reacting") and hand-restarted; they currently run in the closeout session's background, not under a supervisor. No phone available at closeout, so live work is deferred.

## Current Goal

An AI assistant that performs phone-based personal/admin tasks with live user control, approvals, transcripts, summaries, safe data use, and conservative inbound handling. Product goal in `docs/product/personal-ai-assistant-tz.md`. Strategy (D-7): build for self 6-12 months, EU/Spain compliance-first niche, then decide on commercialization.

## Current Decisions

See `DECISIONS.md` for the authoritative log. Most recent: D-10 (policy engine v1), D-11 (claude-haiku-4-5 conversation LLM; A/B follow-up keeps it), **D-12 (next workstream: eval-driven development, scenario-routing wiring, reliability before scale)**.

## Tech Status

Core stack accepted 2026-06-11 (D-5..D-9): Pipecat voice worker (Twilio + Deepgram + swappable LLM + Cartesia), FastAPI api, aiogram bot (separate process), minimal Next.js web, Postgres (Neon), Upstash Redis, uv workspace. Policy engine v1 (`packages/policy`) is rules-as-data with a code hard floor and autonomy levels 0-3. 90 tests pass; ruff clean.

## How To Resume

For the next session, read:

1. `AGENTS.md`
2. This file
3. `DECISIONS.md` (focus D-10, D-11, **D-12**)
4. `docs/superpowers/handovers/HANDOVER-2026-06-11-assessment-and-roadmap.md`
5. The relevant epic: `docs/epics/EPIC-002-outbound-calls.md` and `EPIC-003-policy-approvals.md`

## Immediate Next Steps (D-12 order: offline-doable first, no phone needed)

1. **Wire scenario detection into intake** so the existing policy profiles + scenario-scoped facts activate: `normalize.py` extracts `scenario`, `handlers.confirm_task` passes it into `StructuredGoal`. Small, high-value, unblocks dormant infrastructure.
2. **Build an offline eval harness with an LLM "callee simulator"** across the five scenarios (generic/doctor/insurance/restaurant/info_gathering), asserting task success, policy correctness, role-holding, latency, cost. Generalises `scripts/eval_role_drift.py`. Highest-leverage best-practice move; makes every prompt/model/scenario change measurable.
3. **Reliability:** process supervision + reconnect for api/bot (the fragility hit this session); plan a move off the Cloudflare quick tunnel.
4. **Generalise/scenario-ise the booking-flavoured few-shot** once eval can measure the trade-off.
5. **(needs a phone)** live validation of turn detection + role-holding in full multi-turn context; then EPIC-003 phase D scenarios, EPIC-002 D1 real booking, EPIC-003 C2 (Transfer-to-me) / C3 (Take-over).

## Operational Notes

- Run the stack locally: `uv run assistant-api`, `uv run assistant-bot`, `uv run assistant-worker` (worker also needs the Cloudflare tunnel + Twilio for real calls). Only ONE Telegram poller at a time (a second `assistant-bot` causes Telegram 409 and "not reacting").
- `.env` (not in git) holds tokens; `LLM_BASE_URL=https://api.anthropic.com/v1/`, `LLM_MODEL=claude-haiku-4-5`. Local process/tunnel logs match `*-session.log` (gitignored).
- Validation: `uv run pytest -q` (90), `uv run ruff check .`.
