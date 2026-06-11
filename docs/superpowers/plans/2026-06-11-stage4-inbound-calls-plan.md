# Plan: Stage 4 - Inbound Calls

**Spec:** `docs/superpowers/specs/2026-06-11-stage4-inbound-calls.md`
**Epic:** EPIC-004 | **Status:** Draft

## Phase A - Inbound path

- [ ] A1. Twilio inbound webhook -> synthetic `inbound_call` task_run -> worker answers; AI disclosure on answer; `direction` on calls.
- [ ] A2. Caller ID lookup against contacts; routing table (known+scenario / known / unknown / spam).

**Checkpoint:** assistant answers a call to its number and screens an unknown caller.

## Phase B - Policy and screening

- [ ] B1. Inbound policy profile: zero-disclosure default, screening question set, message-taking flow.
- [ ] B2. Spam heuristics + polite hang-up; logging.
- [ ] B3. Summary template (who/why/urgency/action) -> Telegram push after every call.

## Phase C - Transfer and live control

- [ ] C1. Bridge-to-user transfer with fallback to message-taking.
- [ ] C2. Call-start Telegram notification with live-page link; verify Take over/Hang up work for inbound.
- [ ] C3. Important-call rule list (contact priority flags, keywords).

## Phase D - Validation

- [ ] D1. Test matrix: unknown, known-with-scenario, important-transfer, spam.
- [ ] D2. Verification vs acceptance criteria; update EPIC-004; closeout.

## Risks

- Screening quality in fast colloquial Spanish: collect failed screenings in docs/research and tune prompts.
- Number strategy may prove wrong (people calling the personal number bypass the assistant): keep the forwarding open question alive after real usage.
