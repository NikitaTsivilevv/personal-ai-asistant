# EPIC-003 - Policy And Approvals

**Status:** In progress (2026-06-12): engine v1 + rule files + worker wiring + approval expiry + profile facts management + pause automation shipped (plan phases A, B, C1; PRs #3-#5); C2 Transfer-to-me, C3 Take-over, and live scenario validation (D) pending. Live session 2026-06-11 night: profile facts seeded (nie=high/default, car plate=medium/insurance, name lowered to low); found that high-sensitivity fact values sat in the prompt unmarked, so the agent could say them without approval - mitigated with a `[SENSITIVE]` prompt marker + rule requiring `request_approval(share_sensitive_data)` (prompt-level only; structural value withholding until approval is backlog). Scenario D runs were blocked on EPIC-002 conversation-quality bugs (turn detection, role drift), now fixed in code (PR #7) and awaiting live validation. **Scenario profiles NO LONGER dormant (2026-06-12, D-13):** intake (`apps/bot/.../normalize.py`) now extracts `scenario` from NLP result (unknown → generic + warning); bot confirm card shows scenario with one-tap correction ("Сменить сценарий" button); doctor/insurance/restaurant rules + scenario-scoped facts now activate on real tasks. Offline eval harness (`packages/evals`) now exercises policy branches including approval expiry across 5 scenarios — intermittent DNI disclosure without `request_approval` and payment over-commit caught by policy axis in smoke run. Live phase D still pending phone. **Known issues:** (1) `tools.py` builds `ActionRequest` without `fact_key`, so the engine's fact-access deny branch is unreachable from the worker in production — must be fixed before fact-gated rules are relied on in live calls; (2) `insurance/cancel_denied` and `generic/approval_expiry` case-design precondition: a conservative agent that refuses verbally (never triggers the policy engine) produces a "missing expected decision" policy fail — needs multi-run confirmation and possible case retuning before treating as a real failure.
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
