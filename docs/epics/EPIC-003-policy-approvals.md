# EPIC-003 - Policy And Approvals

**Status:** In progress (2026-06-11): engine v1 + rule files + worker wiring + approval expiry + profile facts management + pause automation shipped (plan phases A, B, C1; PRs #3-#5); C2 Transfer-to-me, C3 Take-over, and live scenario validation (D) pending. Live session 2026-06-11 night: profile facts seeded (nie=high/default, car plate=medium/insurance, name lowered to low); found that high-sensitivity fact values sat in the prompt unmarked, so the agent could say them without approval - mitigated with a `[SENSITIVE]` prompt marker + rule requiring `request_approval(share_sensitive_data)` (prompt-level only; structural value withholding until approval is backlog). Scenario D runs were blocked on EPIC-002 conversation-quality bugs (turn detection, role drift), now fixed in code (PR #7) and awaiting live validation. **Gap found 2026-06-11 (D-12): the scenario profiles are dormant** - intake (`apps/bot/.../normalize.py`) never sets `structured_goal.scenario`, so every task evaluates on the `generic` profile and the doctor/insurance/restaurant rules + scenario-scoped facts never activate. Wiring scenario detection into intake is the unblocking step before phase D meaningfully exercises the profiles.
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
