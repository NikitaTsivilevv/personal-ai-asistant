# Plan: Stage 3 - Policy Engine And Approvals

**Spec:** `docs/superpowers/specs/2026-06-11-stage3-policy-approvals.md`
**Epic:** EPIC-003 | **Status:** Draft

## Phase A - Engine core

- [ ] A1. Action taxonomy + rule schema in `packages/shared`; rule files per scenario in `packages/policy/rules/`.
- [ ] A2. Engine v1 with full matrix unit tests; level-3 hard floor enforced in code, not rules.
- [ ] A3. Wire engine into the worker's tool-call path (replace stub); deny phrases; audit_log entries with rule ids.

**Checkpoint:** matrix tests green; simulated calls hit allow/approve/deny correctly.

## Phase B - Approvals hardening

- [ ] B1. Approval expiry + in-call wait phrases + graceful wrap-up on expiry/reject.
- [ ] B2. profile_facts `allowed_scenarios` + `disclose_fact` checks; Telegram command to manage facts.

## Phase C - In-call human control

- [ ] C1. Pause automation + Whisper polish (queue whispers, apply at next turn).
- [ ] C2. Transfer to me: bridge user's phone into the call via Twilio.
- [ ] C3. Take over: browser-mic WebRTC leg; assistant goes silent, keeps transcribing.

**Checkpoint:** all five control actions usable on a live call.

## Phase D - Scenario validation

- [ ] D1. Live scenario tests: insurance (level 2-3 boundaries), doctor (sensitive-data approval), restaurant (level 1 no-approval path).
- [ ] D2. Verification vs acceptance criteria; update EPIC-003; closeout.

## Risks

- Take over (WebRTC) is the most complex item; if it drags, ship Transfer-to-me first and defer Take over - transfer covers the safety need.
- Over-strict rules make the assistant useless: track deny/approval frequency in audit_log and tune.
