# PROJECT_CONTEXT.md - Personal AI Assistant

**Last refreshed:** 2026-06-11
**Status:** Idea and stack validated; core stack decisions accepted (D-5..D-8). Draft specs and plans exist for all seven epics (2026-06-11). No application code has been scaffolded yet. Next: implement Stage 1 (EPIC-001) plan, Phase A.

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
3. `DECISIONS.md`
4. The relevant epic in `docs/epics/`

Then either write the first spec/plan or scaffold the monorepo apps after the user confirms the initial implementation scope.

