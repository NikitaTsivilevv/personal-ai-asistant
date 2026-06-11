# DECISIONS.md - Personal AI Assistant

This file records product and architecture decisions so future agent sessions can recover the reasoning without relying on chat history.

Append new entries. Do not delete old entries. Supersede them explicitly.

Entry format:

- **D-N - Title**
- **Date:** YYYY-MM-DD
- **Status:** Accepted / Superseded by D-X / Rejected
- **Context:** problem or uncertainty
- **Decision:** what was chosen
- **Rationale:** why
- **Consequences:** trade-offs and follow-ups

---

## D-1 - Commercial-ready MVP-light documentation process

- **Date:** 2026-06-10
- **Status:** Accepted
- **Context:** The project is a personal MVP, but the owner intends to commercialize it later. The process must support AI-agent collaboration without overloading early development.
- **Decision:** Use a disciplined documentation system from day one: `AGENTS.md`, `CLAUDE.md`, `PROJECT_CONTEXT.md`, `DECISIONS.md`, product docs, epics, superpowers specs/plans, and handovers.
- **Rationale:** AI agents lose chat context across sessions. Durable, structured docs reduce repeated explanations, preserve architectural reasoning, and keep token usage controlled.
- **Consequences:** Meaningful sessions should update project docs. Lightweight fixes do not need full ceremony, but architecture/product/provider/privacy decisions must be recorded.

## D-2 - Monorepo for the MVP

- **Date:** 2026-06-10
- **Status:** Accepted
- **Context:** The system will likely include a web dashboard, API, voice worker, shared contracts, database schema, and policy engine.
- **Decision:** Start as a monorepo with planned folders `apps/web`, `apps/api`, `apps/voice-worker`, `packages/shared`, `packages/database`, and `packages/policy`.
- **Rationale:** A monorepo makes early AI-agent work easier: fewer repositories to load, easier shared types/contracts, simpler cross-component specs, and one documentation root.
- **Consequences:** Repo boundaries can be split later if deployment, ownership, or scaling needs justify it. Initial docs must avoid assuming one deploy target for all components.

## D-3 - Epic-driven documentation model

- **Date:** 2026-06-10
- **Status:** Accepted
- **Context:** The TZ naturally decomposes into multiple long-lived workstreams: control plane, outbound calls, approvals, inbound calls, integrations, observability, and compliance.
- **Decision:** Use `docs/epics/EPIC-*.md` as long-lived containers for product workstreams. Specs and plans remain per-feature execution artifacts.
- **Rationale:** Epics help agents load one bounded product area instead of the whole project. They also give a stable place to track scope, status, dependencies, acceptance criteria, and links to specs/plans.
- **Consequences:** Epics must be updated during closeout. Stale epic status is worse than no epic status.

## D-4 - Project-specific session closeout skill

- **Date:** 2026-06-10
- **Status:** Accepted
- **Context:** Another project already uses a global `project-snapshot` skill. Reusing that name here could cause confusion or trigger the wrong workflow.
- **Decision:** Create a project-specific closeout workflow named `personal-ai-session-closeout`.
- **Rationale:** The new skill keeps this project's closeout rules separate while preserving the useful pattern: update decisions, context, epics, open questions, risks, and write a handover.
- **Consequences:** End meaningful sessions with this workflow. Do not rename or overwrite the existing global `project-snapshot` skill.

## D-5 - Voice worker built on Pipecat with self-selected providers

- **Date:** 2026-06-11
- **Status:** Accepted
- **Context:** The TZ proposed a fully custom STT/LLM/TTS pipeline. Market research (2026) shows three viable approaches: managed platforms (Vapi/Retell, ~$0.07-0.15/min, vendor lock-in, policy logic constrained to their webhook model), open-source pipeline frameworks (Pipecat v1.0, LiveKit Agents), or a from-scratch pipeline (1-2 months of solved realtime problems).
- **Decision:** Build the voice worker on Pipecat (open source, Python) with Twilio telephony, Deepgram STT, swappable LLM, and Cartesia TTS, deployed as a long-lived process on a small VPS.
- **Rationale:** Pipecat provides turn-taking, VAD, barge-in, and reconnect out of the box while keeping full control of the conversation loop. The policy engine and approvals - the product's core differentiation - embed directly in the pipeline. Per-minute cost stays at provider cost (~$0.04-0.13/min all-in), audio/data flows through our own server (important for the EU/GDPR positioning), and every provider layer is swappable. Managed platforms were rejected for lock-in, margin loss, and US data flow; from-scratch was rejected as months of work on already-solved plumbing with no product advantage.
- **Consequences:** Voice worker is Python. First real call lands later than with a managed platform (~1-2 weeks of integration). Hosting/uptime of the worker is our responsibility. Turn-taking tuning for Spanish call centers (IVR, hold music) is our work.

## D-6 - MVP interface: Telegram bot plus minimal live-call web page

- **Date:** 2026-06-11
- **Status:** Accepted
- **Context:** The TZ left open whether the first interface is a web dashboard, Telegram, or both.
- **Decision:** Ship both, minimally: Telegram bot for task creation, approvals, and post-call summaries; a single minimal web page for live call control (live transcript, Approve/Reject/Take over/Hang up/Whisper).
- **Rationale:** Telegram is the fastest path for asynchronous interactions and push-style approvals. Live in-call control needs a richer realtime surface than Telegram provides. Splitting by interaction mode covers the full TZ control set with minimal UI work.
- **Consequences:** Two thin frontends instead of one full dashboard. The web page stays single-purpose until the MVP proves itself.

## D-7 - Light multi-tenant groundwork, no premature productization

- **Date:** 2026-06-11
- **Status:** Accepted
- **Context:** The project is personal first but intended for possible commercialization. Market research shows the viable commercial niche is EU/Spain compliance-first calling (EU AI Act Article 50 applies from August 2026), not competing with US platforms.
- **Decision:** Build for one user but avoid single-user hardcoding: `user_id` on all owned tables, no global singletons for profile/policy, language kept configurable, AI disclosure and audit log treated as core features rather than compliance afterthoughts. No auth/billing/tenant isolation work beyond that.
- **Rationale:** Near-zero cost now; dramatically cheaper migration later. Compliance-first design (disclosure, approvals, audit) doubles as the commercial differentiator.
- **Consequences:** Slight schema/API verbosity. Real multi-tenancy (auth, billing, isolation) is deferred until commercialization is decided.

## D-8 - Backend language split: Python services, TypeScript web

- **Date:** 2026-06-11
- **Status:** Accepted
- **Context:** D-5 fixes the voice worker to Python (Pipecat). The TZ allowed FastAPI, NestJS, or Hono/Next API routes for the API.
- **Decision:** Python for `apps/api` (FastAPI) and `apps/voice-worker` (Pipecat) and the Telegram bot (aiogram, inside or beside the API); TypeScript/Next.js only for the minimal live-call web page. Shared contracts defined once (Pydantic models + generated OpenAPI types for web).
- **Rationale:** The voice worker is unavoidably Python; keeping API/bot in Python avoids duplicating domain models, policy logic, and DB access across two languages. The web surface is small enough that a TS island is cheap.
- **Consequences:** `packages/shared` holds Pydantic schemas; web types are generated from OpenAPI. Revisit if the web dashboard grows.

## D-9 - Stage 1 implementation choices: uv workspace, separate bot app, Redis lists + pub/sub

- **Date:** 2026-06-11
- **Status:** Accepted
- **Context:** Scaffolding EPIC-001 required concrete choices the specs left open: Python dependency management, where the Telegram bot lives (D-8 said "inside or beside the API"), and the queue/event transport shape on Redis.
- **Decision:**
  - uv workspace monorepo (root `pyproject.toml`, Python 3.12 pinned) with hatchling-built packages; shared dev deps (pytest, ruff, fakeredis, aiosqlite) at the root.
  - Telegram bot is a separate app `apps/bot` (own process), not a module inside `apps/api`.
  - Redis transport: task dispatch via list `queue:task_runs` (LPUSH/BRPOP); per-run control via list `run:{run_id}:control` (approval resolutions, cancellation reach the waiting worker); broadcast via pub/sub channel `events:runs` consumed by SSE endpoints and the bot notifier. Key names and payload models live in `assistant_shared.queue`/`events`.
  - Tests run against in-memory sqlite (StaticPool) + fakeredis; Postgres/Upstash only via env config.
- **Rationale:** uv is the fastest current Python workspace tool and gives one lockfile. A separate bot process keeps long-polling out of the API's lifecycle and lets it restart independently. Lists give at-least-once handoff where exactly one consumer must act (queue, worker unblock); pub/sub is fan-out for observers where missing a message is tolerable. sqlite/fakeredis keep tests free of provisioned infra (no service registrations yet).
- **Consequences:** Queue has no persistence guarantees beyond Redis durability - acceptable for stage 1, revisit (streams/consumer groups) in EPIC-006. Bot deployment is a fourth process. JSON columns use JSONB on Postgres via `with_variant`, so sqlite tests don't exercise JSONB-specific behavior.

