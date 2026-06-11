# Spec: Stage 5 - Integrations And Memory (EPIC-005)

**Date:** 2026-06-11
**Status:** Draft
**Depends on:** Stage 3 policy engine (tool access must be policy-gated)

## 1. Goal

Give the assistant controlled, audited access to calendar, contacts, documents, and user facts so calls can produce real-world side effects (e.g., a doctor appointment lands in the calendar).

## 2. Scope

In scope:

- Calendar: Google Calendar first (user confirmed Gmail usage); tools `calendar.find_slots`, `calendar.create_event`, `calendar.move_event` (move/cancel behind approval per policy). Manual fallback: assistant proposes, user confirms in Telegram.
- Contacts: CRUD via Telegram commands + auto-suggest ("save this number as X?") after calls.
- Profile facts v2: per-fact `sensitivity` + `allowed_scenarios` (from Stage 3); per-task consent prompts for high-sensitivity facts (DNI, policy numbers, DOB); field-level encryption at rest for `high` sensitivity.
- Documents: object storage (Cloudflare R2) for attachments the user uploads to a task (e.g., insurance letter PDF); text extracted and made available to the agent for that task only.
- Semantic memory (pgvector): post-call facts/learnings embedded and retrievable for future task planning ("last time the insurer asked for X"). Retrieval only at planning time, not mid-call, to protect latency.
- Tool access boundaries: every tool call passes `policy.evaluate()`; tool grants are per-task, recorded in audit_log.

Out of scope: email automation, browser automation, Apple/Outlook calendars, document OCR pipelines beyond basic text extraction.

## 3. Open questions resolved here (update open-questions.md when implemented)

- Calendar first = Google Calendar.
- Contacts = manual entry + post-call suggestions (no bulk import for MVP).
- High-sensitivity facts encrypted field-level from day one.

## 4. Acceptance Criteria

1. Doctor scenario end-to-end: call books appointment -> approval -> event in Google Calendar.
2. High-sensitivity fact used in a call only after per-task consent; stored encrypted.
3. Uploaded document content available to the agent for its task and inaccessible to other tasks.
4. Post-call memory retrievable in a later task's plan ("known info" section).
5. All tool access visible in audit_log.
