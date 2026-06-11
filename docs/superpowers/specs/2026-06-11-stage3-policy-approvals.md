# Spec: Stage 3 - Policy Engine And Approvals (EPIC-003)

**Date:** 2026-06-11
**Status:** Draft
**Depends on:** Stage 2 working calls; D-7 (compliance-first as core feature)

## 1. Goal

Turn the Stage-1 policy stub into a real engine that decides, for every assistant utterance-intent and tool call, whether it is allowed, needs approval, or is denied - per scenario and autonomy level. Add full in-call human control.

## 2. Scope

In scope:

- `packages/policy` v1: declarative rule set (YAML/JSON in repo), evaluated as `evaluate(action, task_context) -> allow | require_approval | deny`.
- Action taxonomy: `disclose_fact(key)`, `commit_booking`, `commit_change`, `commit_cancellation`, `agree_payment`, `share_contact`, `accept_terms`, `end_call`, `transfer`, plus free-form `say_sensitive`.
- Autonomy levels 0-3 mapped to the taxonomy (TZ §4): level 0 info-only; level 1 booking within constraints; level 2 changes/cancellations require approval; level 3 financial/legal/medical always require approval (hard floor, not configurable down - D-7/AGENTS safety rule).
- Per-scenario profiles: insurance, doctor, restaurant, info-gathering - each with default allowed facts and approval triggers (TZ §5).
- Fact access control: profile_facts get `allowed_scenarios`; engine checks before `disclose_fact`.
- Approval lifecycle hardening: expiry (configurable, default 2 min in-call), expiry behavior = safe phrase + graceful wrap-up; "callee waiting" UX phrases.
- In-call controls completed on web page: Take over (user speaks via browser mic - WebRTC leg into the call), Transfer to me (dial user's phone and bridge), Pause automation.
- Every policy decision -> audit_log with rule id, inputs hash, outcome.

Out of scope: policy authoring UI; legal review itself (EPIC-007); inbound-specific rules (EPIC-004).

## 3. Design Notes

- Rules are data, not code: each rule = match (scenario, action, autonomy, fact sensitivity) -> outcome + approval kind + question template. Engine is ~200 lines; tests enumerate the whole matrix.
- The LLM never decides policy; it proposes actions, the engine disposes. Prompt reminds the model to propose rather than act.
- Deny responses include a callee-facing phrase ("I'm not authorized to do that, I'll pass it to Nikita").

## 4. Acceptance Criteria

1. Matrix test: every (scenario x action x autonomy level) combination has a deterministic outcome; level-3 actions can never resolve to `allow`.
2. Insurance scenario live test: assistant shares policy number (allowed), refuses to close claim, requests approval for a paid service.
3. Approval expiry on a live call leads to graceful "I'll get back to you" wrap-up, not a hang.
4. Take over and Transfer to me work on a real call.
5. Every decision visible in audit_log with rule id.
