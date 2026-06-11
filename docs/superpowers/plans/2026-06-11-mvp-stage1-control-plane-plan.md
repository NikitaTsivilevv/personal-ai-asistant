# Plan: MVP Stage 1 - Control Plane

**Date:** 2026-06-11
**Spec:** `docs/superpowers/specs/2026-06-11-mvp-stage1-control-plane.md`
**Epic:** EPIC-001
**Status:** Executed 2026-06-11 (A2 partially: env/config done, no real provisioning; D2/D3 written but unverified live - no Telegram/LLM keys yet)

Each task is sized for one focused agent session. Order matters; checkpoints are commit points.

## Phase A - Scaffolding

- [x] A1. Scaffold monorepo: `apps/api` (FastAPI + uv/poetry), `apps/voice-worker` (Python stub), `apps/web` (Next.js stub), `packages/shared` (Pydantic schemas), `packages/database` (SQLAlchemy/Alembic), `packages/policy` (stub). Add root README run instructions and update AGENTS.md validation commands. *(Also `apps/bot` - see D-9.)*
- [x] A2. Provision dev infra: ~~Neon/Supabase Postgres, Upstash Redis~~ deferred (no registrations yet); `.env.example` with placeholders; config loading in api/worker/bot done.

**Checkpoint:** `api` starts, `GET /health` green, migrations run empty.

## Phase B - Data and API core

- [x] B1. Schema v1 migrations: users, tasks, task_runs, approvals, transcript_segments, contacts, profile_facts, audit_log (spec §3).
- [x] B2. Task endpoints (`POST/GET /tasks`, queue, cancel) + audit_log writes + tests.
- [x] B3. Approvals endpoint + run events: internal event ingestion (`POST /internal/runs/{id}/events`) and public SSE (`GET /runs/{id}/events`) + tests.

**Checkpoint:** full task lifecycle drivable via HTTP only (curl), audit trail complete.

## Phase C - Queue and stub worker

- [x] C1. Redis queue dispatch on task queue; worker stub consumes, simulates lifecycle: running -> approval request -> wait -> completed/failed, pushing events via internal API.
- [x] C2. Policy stub in `packages/policy`: `evaluate()` with autonomy-level rule table (TZ §4); worker calls it before the simulated sensitive action.

**Checkpoint:** end-to-end run via API: queue -> approval pause -> resolve -> done.

## Phase D - Telegram bot

- [x] D1. aiogram bot skeleton: auth by Telegram user ID allowlist; `/tasks` list.
- [x] D2. `/new` flow with LLM normalization of free text into structured_goal + confirmation/edit loop. *(Heuristic fallback active until ANTHROPIC_API_KEY exists.)*
- [x] D3. Push notifications: approval messages with inline Approve/Reject buttons, run-completion summaries (consumes run events).

**Checkpoint:** acceptance criteria 1-5 of the spec pass from a phone. *(NOT yet verified live - blocked on bot token registration. Criteria 2-3, 5-6 covered by automated e2e tests.)*

## Phase E - Wrap-up

- [x] E1. Web stub route rendering SSE events as a raw live feed (placeholder for EPIC-002 live page).
- [x] E2. Verification pass: 26 automated tests + migration up/down + uvicorn /health verified; EPIC-001 status updated; D-9 appended; handover written. Live phone verification deferred to provisioning session.

## Risks / Notes

- LLM normalization (D2) is the only AI dependency in stage 1; if it stalls, fall back to a structured form-style dialog in the bot and defer normalization.
- Keep the worker's event contract (event types, payloads) in `packages/shared` - EPIC-002's real Pipecat worker must reuse it unchanged.
- Before starting EPIC-002, recheck Deepgram/Cartesia/LLM model pricing (open-questions.md).
