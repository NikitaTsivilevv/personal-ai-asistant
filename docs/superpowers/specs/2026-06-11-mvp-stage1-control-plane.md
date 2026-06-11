# Spec: MVP Stage 1 - Control Plane

**Date:** 2026-06-11
**Status:** Draft for review
**Epic:** EPIC-001 (Control Plane)
**Depends on decisions:** D-2 (monorepo), D-5 (Pipecat voice stack), D-6 (Telegram + minimal web), D-7 (light multi-tenant groundwork), D-8 (Python services, TS web)

## 1. Goal

Build the control plane: the user can create a phone task in Telegram, the system persists and queues it, exposes its lifecycle, and supports approval requests/responses - all **without real phone calls yet**. The voice worker (EPIC-002) will plug into this skeleton.

## 2. Scope

In scope:

- Monorepo scaffolding (`apps/api`, `apps/voice-worker` stub, `apps/web` stub, `packages/shared`, `packages/database`, `packages/policy` stub).
- Postgres schema v1 and migrations.
- FastAPI service: tasks, task_runs, approvals, audit log, health.
- Telegram bot (aiogram): create task, list tasks, receive status updates, approve/reject.
- Queue dispatch via Upstash Redis (task created -> job enqueued -> picked up by a stub worker that simulates a call run).
- Single-user auth (static token / Telegram user ID allowlist), but `user_id` on all owned tables (D-7).

Out of scope:

- Real telephony, STT/LLM/TTS (EPIC-002).
- Live transcript web page (built in EPIC-002 when there is something live to show; only a stub route now).
- Calendar/contacts integrations (EPIC-005).
- Inbound calls (EPIC-004).

## 3. Data Model v1

All owned tables carry `user_id` (D-7). Timestamps `created_at`/`updated_at` everywhere.

- `users`: id, telegram_user_id, display_name, locale.
- `tasks`: id, user_id, title, instructions (raw user text), structured_goal (jsonb: objective, constraints, allowed_facts, autonomy_level 0-3), target_phone, target_name, status (`draft|ready|queued|running|waiting_approval|done|failed|cancelled`), language_pref.
- `task_runs`: id, task_id, attempt_no, status (`queued|running|waiting_approval|completed|failed|aborted`), started_at, ended_at, result_summary, failure_reason, estimated_cost_cents.
- `approvals`: id, task_run_id, kind (`disclosure|payment|cancellation|sensitive_data|other`), question, context (jsonb), status (`pending|approved|rejected|expired`), requested_at, resolved_at, resolved_via (`telegram|web`).
- `transcript_segments`: id, task_run_id, seq, speaker (`assistant|callee|system`), text, ts_ms. (Schema now, populated in EPIC-002.)
- `contacts`: id, user_id, name, phone, org_flag, notes.
- `profile_facts`: id, user_id, key, value, sensitivity (`low|medium|high`), allowed_by_default (bool).
- `audit_log`: id, user_id, task_run_id (nullable), actor (`user|assistant|policy|system`), event_type, payload (jsonb), created_at.

Open (carried in open-questions.md): field-level encryption for high-sensitivity profile_facts; recordings retention.

## 4. API Surface (FastAPI)

- `POST /tasks` - create from structured payload.
- `GET /tasks`, `GET /tasks/{id}` (with runs and approvals).
- `POST /tasks/{id}/queue`, `POST /tasks/{id}/cancel`.
- `POST /approvals/{id}/resolve` (approve/reject, records resolved_via).
- `GET /runs/{id}/events` - SSE stream of run events (status, transcript segments later); the web page and bot updates both consume run events.
- `GET /health`.

Internal (worker-facing, token-authed): `POST /internal/runs/{id}/events` for the worker to push status/transcript/approval-request events.

## 5. Telegram Bot Flows

- `/new` - guided task creation: free-text instruction -> LLM normalization into structured_goal -> confirmation message showing objective/constraints/autonomy level -> user confirms or edits.
- `/tasks` - list with statuses.
- Approval push: when an approval is created, the bot sends a message with inline Approve/Reject buttons; resolution hits the same `POST /approvals/{id}/resolve`.
- Run completion push: summary message (stubbed summary in stage 1).

## 6. Queue and Stub Worker

- Task queued -> Redis stream/list entry -> `apps/voice-worker` stub consumes it, walks a fake call lifecycle (running -> mid-run approval request -> completed with fake summary), pushing events through the internal API. This proves the whole control loop end-to-end before any telephony exists.

## 7. Policy Engine (stub boundary)

`packages/policy` exposes one function used by the worker:
`evaluate(action, task_context) -> allow | require_approval(kind, question) | deny(reason)`.
Stage 1 ships a rule table keyed by autonomy level (TZ section 4). Real rules grow in EPIC-003.

## 8. Non-functional

- Every state change writes an `audit_log` row.
- All money-relevant fields in integer cents.
- Config via env; no secrets in repo (AGENTS.md safety rules).
- Free-tier targets: Neon/Supabase Postgres, Upstash Redis, Vercel for web stub; API + worker run locally/VPS.

## 9. Acceptance Criteria

1. `/new` in Telegram creates a persisted task with structured_goal.
2. Queuing a task produces a task_run consumed by the stub worker.
3. Mid-run approval appears in Telegram; Approve/Reject changes run flow.
4. Run completion sends a summary message; task status is `done`.
5. Every transition above is visible in `audit_log`.
6. `GET /runs/{id}/events` streams the same events the bot received.
