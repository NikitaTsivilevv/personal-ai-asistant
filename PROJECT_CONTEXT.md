# PROJECT_CONTEXT.md - Personal AI Assistant

**Last refreshed:** 2026-06-11 (late session)
**Status:** PRs #1-#5 merged to `main`. Stage 1 live-verified server-side (e2e on real Postgres + Upstash: queue -> simulate -> approval -> done). Stage 2: real hello-world call succeeded (Twilio -> Cloudflare Tunnel -> Pipecat -> Deepgram/Cartesia/gpt-4o-mini, RU disclosure, transcript + summary); phase D (real booking) pending. Stage 3 (EPIC-003): policy engine v1 (rules-as-data, hard floor in code, D-10), policy_decision audit, approval expiry 120s, profile facts with allowed_scenarios (/facts API + bot commands), pause automation - phases A/B/C1 done; C2 transfer, C3 take-over, D live scenarios pending (need live calls). 81 tests, ruff clean. Provider pricing verified ~$0.04/min landline (docs/research/2026-06-11-provider-pricing.md). Tails: stage-1 phone check from Telegram, .env DATABASE_URL still has postgresql:// scheme (works only via env override; replace with postgresql+asyncpg://), quick-tunnel URL is ephemeral.

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
3. `DECISIONS.md` (D-9 stage-1 choices, D-10 policy engine)
4. `docs/superpowers/handovers/HANDOVER-2026-06-11-stage2-live-stage3-policy.md`
5. The relevant epic in `docs/epics/`

Immediate next steps (a live session with Nikita on the phone):

1. Prep: fix `DATABASE_URL` scheme in `.env` (`postgresql+asyncpg://`); start cloudflared + update `PUBLIC_WS_URL` if the quick-tunnel URL changed; start api/bot/worker; fill profile facts via bot (`/fact_add`).
2. Stage-1 phone check (EPIC-001 acceptance 1-4): `/new` in Telegram, Approve and Reject runs, summary push, live web page.
3. EPIC-003 phase D live: doctor/insurance/restaurant scenario calls to own phone - verify deny phrase, sensitive-data approval, approval expiry wrap-up, pause/resume, whisper.
4. EPIC-002 phase D1: real restaurant booking; capture transcript + failure notes in `docs/research/`; busy-vs-no-answer routing from Twilio callbacks.
5. Then EPIC-003 C2 (Transfer to me - Twilio bridge) and C3 (Take over - WebRTC), designed and tested live.

