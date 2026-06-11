# Plan: Stage 5 - Integrations And Memory

**Spec:** `docs/superpowers/specs/2026-06-11-stage5-integrations-memory.md`
**Epic:** EPIC-005 | **Status:** Draft

## Phase A - Facts and contacts

- [ ] A1. profile_facts v2: sensitivity, allowed_scenarios, field-level encryption for `high`; Telegram management commands; per-task consent flow.
- [ ] A2. Contacts CRUD in Telegram + post-call "save contact?" suggestions.

## Phase B - Calendar

- [ ] B1. Google Calendar OAuth + `find_slots`/`create_event`/`move_event` tools, policy-gated (move/cancel -> approval).
- [ ] B2. Doctor scenario integration: slot preferences in structured_goal -> booking -> calendar event after approval.

**Checkpoint:** acceptance criterion 1 (doctor -> calendar) passes live.

## Phase C - Documents and memory

- [ ] C1. R2 storage + task attachments via Telegram; text extraction; per-task access scoping.
- [ ] C2. pgvector memory: post-call learning extraction, embedding, retrieval into task planning context.

## Phase D - Validation

- [ ] D1. Audit review: every tool call logged; cross-task document isolation test.
- [ ] D2. Verification vs acceptance criteria; update EPIC-005 and open-questions.md; closeout.

## Risks

- Google OAuth verification hurdles for a personal app: use test-mode OAuth (own account only) for MVP.
- Memory retrieval polluting prompts: cap retrieved items, show them in the task confirmation so the user sees what the agent "remembers".
