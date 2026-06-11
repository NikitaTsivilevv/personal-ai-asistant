# PROJECT_CONTEXT.md - Personal AI Assistant

**Last refreshed:** 2026-06-11 (night live session)
**Status:** PRs #1-#5 merged to `main`; uncommitted working-tree changes from the night session (queue ConnectionError resilience, inbound audio probe, prompt role/sensitive-fact fixes - 85 tests, ruff clean; commit next session). Live multi-turn calls work end-to-end: Twilio (paid account now, D1 unblocked) -> Cloudflare quick tunnel -> Pipecat -> Deepgram -> claude-haiku-4-5 via Anthropic OpenAI-compat endpoint (D-11; OpenAI key out of quota) -> Cartesia. Two blocking conversation-quality bugs found live (see EPIC-002): early/short callee utterances lost by turn detection (~33 s to first registered turn), and residual role confusion on haiku mid-call. EPIC-003 D live scenarios blocked on those; facts seeded in live DB; high-fact prompt leak mitigated at prompt level. Stage-1 formal phone acceptance still not done (calls happened, but no clean /new -> Approve -> Reject pass). `.env` repaired (asyncpg scheme, STALE_RUN_TIMEOUT_S=300). Local network blips kill api process and quick-tunnel registration - resilience is worker-only so far.

## Current Goal

Set up an agent-friendly development and documentation system for a personal AI assistant MVP that can later become commercial.

The product goal is defined in `docs/product/personal-ai-assistant-tz.md`: an AI assistant that can perform phone-based personal/admin tasks, with live user control, approvals, transcripts, summaries, safe data use, and conservative inbound-call handling.

## Current Decisions

- Use a monorepo for the MVP.
- Use an epic-driven documentation system.
- Use commercial-ready but MVP-light process discipline.
- Use a project-specific closeout skill named `personal-ai-session-closeout`.

See `DECISIONS.md` for the authoritative decision log.

## Current Docs

- `AGENTS.md` - rules for AI agents and contributors.
- `CLAUDE.md` - Claude Code entry point.
- `DECISIONS.md` - architecture/product decision log.
- `docs/product/personal-ai-assistant-tz.md` - current technical requirements.
- `docs/product/glossary.md` - shared terminology.
- `docs/product/open-questions.md` - unresolved questions from the TZ.
- `docs/product/risks.md` - material product/engineering risks.
- `docs/epics/` - long-lived workstreams.
- `docs/superpowers/specs/` - feature specs.
- `docs/superpowers/plans/` - implementation plans.
- `docs/superpowers/handovers/` - session handovers.

## Planned Product Areas

1. Control plane: dashboard, auth, tasks, queue, approvals.
2. Outbound calls: telephony, voice worker, STT/LLM/TTS, transcript, summary.
3. Policy and approvals: permission levels, sensitive actions, audit trail.
4. Inbound calls: screening, summary, transfer.
5. Integrations and memory: calendar, contacts, profile facts, documents.
6. Observability, cost, reliability: traces, costs, monitoring, recovery.
7. Commercialization and compliance: GDPR, call recording, AI disclosure, terms.

## Tech Status

Core stack accepted on 2026-06-11 (see DECISIONS.md D-5..D-8):

- Voice worker: Pipecat (Python) on a small VPS; Twilio + Deepgram + swappable LLM + Cartesia
- API: FastAPI (Python); Telegram bot via aiogram
- Web: minimal Next.js live-call page (Vercel)
- DB: Postgres (Neon/Supabase free tier), pgvector later
- Queue/cache: Upstash Redis
- Interfaces: Telegram (tasks/approvals/summaries) + minimal web page (live call control)
- Architecture: single-user MVP with light multi-tenant groundwork (user_id everywhere, compliance-first)

Validation summary (2026-06-11): stack confirmed current; commercial niche identified as
EU/Spain compliance-first calling (EU AI Act Art. 50 from Aug 2026), not competing with
US voice platforms. Strategy: build for self, 6-12 months of real use, then decide.

## How To Resume

For the next session, read:

1. `AGENTS.md`
2. This file
3. `DECISIONS.md` (D-10 policy engine, D-11 LLM provider swap)
4. `docs/superpowers/handovers/HANDOVER-2026-06-11-live-call-quality.md`
5. `docs/epics/EPIC-002-outbound-calls.md` (conversation-quality bugs block everything else)

Immediate next steps:

1. Commit the night-session working-tree changes (queue resilience, audio probe, prompt fixes) as a PR.
2. Fix conversation quality (EPIC-002, no phone needed to start): turn-detection losing early/short callee utterances (pipecat VAD/smart-turn config), then role drift (prompt few-shot and/or stronger model per D-11 follow-up; compare claude-sonnet-4-6).
3. Re-run the live loop: stage-1 formal acceptance (/new -> Approve -> Reject -> summary push), then EPIC-003 D scenarios (doctor approval on nie, insurance deny, restaurant no-approvals, expiry, pause/whisper).
4. EPIC-002 D1 real restaurant booking (Twilio is paid now); transcript + notes to `docs/research/`.
5. Then EPIC-003 C2 (Transfer to me) and C3 (Take over).

