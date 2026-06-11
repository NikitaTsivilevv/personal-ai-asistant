# EPIC-001 - Control Plane

**Status:** Implemented except live Telegram/web verification (2026-06-11). Monorepo scaffolded; schema v1 + migrations; task/approval/event API with SSE; Redis queue + stub worker + policy stub; aiogram bot and web SSE stub written. 26 automated tests pass. Remaining: register Telegram bot / provision Neon+Upstash, then verify acceptance criteria 1-4 from a phone (criteria 5-6 verified by tests).
**Owner:** Nikita
**Goal:** Build the basic web/API layer for creating tasks, tracking runs, managing approvals, and viewing results.

## Scope

- Dashboard or MVP control UI
- Auth
- Task creation and task list
- Task run lifecycle
- Queue/job dispatch
- Basic approval requests and responses
- Summary/transcript display placeholders

## Out Of Scope

- Real phone calls
- Full voice worker
- Inbound calls
- Commercial compliance workflows

## Dependencies

- Initial stack decision
- Database/schema foundation

## Acceptance Criteria

- User can create a phone task.
- System can persist task and task_run records.
- User can view task/run status.
- User can approve or reject a pending approval.
- API and UI have basic validation and audit events.

## Links

- Product TZ: `docs/product/personal-ai-assistant-tz.md`
- Spec: `docs/superpowers/specs/2026-06-11-mvp-stage1-control-plane.md`
- Plan: `docs/superpowers/plans/2026-06-11-mvp-stage1-control-plane-plan.md`
- Decisions: D-1, D-2, D-3, D-5, D-6, D-7, D-8

