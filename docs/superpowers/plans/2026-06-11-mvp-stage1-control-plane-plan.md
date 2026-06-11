# Plan: MVP Stage 1 - Control Plane

**Date:** 2026-06-11
**Spec:** `docs/superpowers/specs/2026-06-11-mvp-stage1-control-plane.md`
**Epic:** EPIC-001
**Status:** Draft for review

Each task is sized for one focused agent session. Order matters; checkpoints are commit points.

## Phase A - Scaffolding

- [ ] A1. Scaffold monorepo: `apps/api` (FastAPI + uv/poetry), `apps/voice-worker` (Python stub), `apps/web` (Next.js stub), `packages/shared` (Pydantic schemas), `packages/database` (SQLAlchemy/Alembic), `packages/policy` (stub). Add root README run instructions and update AGENTS.md validation commands.
- [ ] A2. Provision dev infra: Neon/Supabase Postgres, Upstash Redis; `.env.example`; config loading in api/worker.

**Checkpoint:** `api` starts, `GET /health` green, migrations run empty.

## Phase B - Data and API core

- [ ] B1. Schema v1 migrations: users, tasks, task_runs, approvals, transcript_segments, contacts, profile_facts, audit_log (spec §3).
- [ ] B2. Task endpoints (`POST/GET /tasks`, queue, cancel) + audit_log writes + tests.
- [ ] B3. Approvals endpoint + run events: internal event ingestion (`POST /internal/runs/{id}/events`) and public SSE (`GET /runs/{id}/events`) + tests.

**Checkpoint:** full task lifecycle drivable via HTTP only (curl), audit trail complete.

## Phase C - Queue and stub worker

- [ ] C1. Redis queue dispatch on task queue; worker stub consumes, simulates lifecycle: running -> approval request -> wait -> completed/failed, pushing events via internal API.
- [ ] C2. Policy stub in `packages/policy`: `evaluate()` with autonomy-level rule table (TZ §4); worker calls it before the simulated sensitive action.

**Checkpoint:** end-to-end run via API: queue -> approval pause -> resolve -> done.

## Phase D - Telegram bot

- [ ] D1. aiogram bot skeleton: auth by Telegram user ID allowlist; `/tasks` list.
- [ ] D2. `/new` flow with LLM normalization of free text into structured_goal + confirmation/edit loop.
- [ ] D3. Push notifications: approval messages with inline Approve/Reject buttons, run-completion summaries (consumes run events).

**Checkpoint:** acceptance criteria 1-5 of the spec pass from a phone.

## Phase E - Wrap-up

- [ ] E1. Web stub route rendering SSE events as a raw live feed (placeholder for EPIC-002 live page).
- [ ] E2. Verification pass: run all acceptance criteria, fix gaps, update EPIC-001 status, append decisions if any emerged, write handover (session closeout).

## Risks / Notes

- LLM normalization (D2) is the only AI dependency in stage 1; if it stalls, fall back to a structured form-style dialog in the bot and defer normalization.
- Keep the worker's event contract (event types, payloads) in `packages/shared` - EPIC-002's real Pipecat worker must reuse it unchanged.
- Before starting EPIC-002, recheck Deepgram/Cartesia/LLM model pricing (open-questions.md).
