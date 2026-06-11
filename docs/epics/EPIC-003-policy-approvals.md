# EPIC-003 - Policy And Approvals

**Status:** Spec and plan drafted (2026-06-11), implementation not started
**Owner:** Nikita
**Goal:** Define and enforce what the assistant may say or do without user confirmation.

## Scope

- Autonomy levels
- Policy engine package
- Per-scenario approval rules
- Approval lifecycle
- Sensitive fact access rules
- Audit log for decisions

## Out Of Scope

- Full legal/compliance review
- Complex enterprise policy authoring UI

## Dependencies

- Initial scenario definitions
- Profile facts model
- Control plane approval API

## Acceptance Criteria

- Every proposed sensitive action is allowed, blocked, or escalated.
- Approval decisions are persisted.
- Policy decisions are auditable.
- Financial, legal, medical, and contract-changing actions default to approval-required.

## Links

- Product TZ: `docs/product/personal-ai-assistant-tz.md`
- Open questions: `docs/product/open-questions.md`
- Risks: `docs/product/risks.md`
- Spec: `docs/superpowers/specs/2026-06-11-stage3-policy-approvals.md`
- Plan: `docs/superpowers/plans/2026-06-11-stage3-policy-approvals-plan.md`
