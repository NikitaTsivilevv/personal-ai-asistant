# Plan: Stage 3 - Policy Engine And Approvals

**Spec:** `docs/superpowers/specs/2026-06-11-stage3-policy-approvals.md`
**Epic:** EPIC-003 | **Status:** Phases A + B1 implemented 2026-06-11 (PR #3); B2, C, D pending

## Phase A - Engine core

- [x] A1. Action taxonomy + rule schema in `packages/shared`; rule files per scenario in `packages/policy/rules/`. *(`assistant_shared/policy.py`; JSON profiles in `assistant_policy/rules/` - generic, insurance, doctor, restaurant, info_gathering. `StructuredGoal.scenario` added.)*
- [x] A2. Engine v1 with full matrix unit tests; level-3 hard floor enforced in code, not rules. *(Hard floor: agree_payment/accept_terms/say_sensitive + high-sensitivity disclosures never `allow`. Decisions carry rule_id + inputs hash.)*
- [x] A3. Wire engine into the worker's tool-call path (replace stub); deny phrases; audit_log entries with rule ids. *(`policy_decision` run event -> audit_log with actor=policy; deny returns callee-facing phrase ES/EN/RU.)*

**Checkpoint:** matrix tests green; simulated calls hit allow/approve/deny correctly. ✓ (73 tests)

## Phase B - Approvals hardening

- [x] B1. Approval expiry + in-call wait phrases + graceful wrap-up on expiry/reject. *(Default 120s; `approval_expired` event marks the row expired and resumes the run; agent gets a wrap-up phrase + instruction to end_call politely.)*
- [ ] B2. profile_facts `allowed_scenarios` + `disclose_fact` checks; Telegram command to manage facts. *(Engine-side fact allowlist check is in (code-fact-not-allowed); DB/bot wiring pending.)*

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
