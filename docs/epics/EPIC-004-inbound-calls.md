# EPIC-004 - Inbound Calls

**Status:** Spec and plan drafted (2026-06-11), implementation not started
**Owner:** Nikita
**Goal:** Let the assistant answer or screen inbound calls conservatively and summarize them for the user.

## Scope

- Dedicated number or forwarding flow
- Caller identification
- Unknown caller screening
- Spam/robot handling
- Transfer to user
- Post-call summary

## Out Of Scope

- Full personal assistant autonomy for unknown callers
- Disclosure of personal data before caller/context is established

## Dependencies

- Telephony integration
- Voice worker
- Policy engine
- Contact model

## Acceptance Criteria

- Assistant can answer inbound calls in a conservative mode.
- Known callers can map to scenarios.
- Unknown callers are screened without revealing sensitive facts.
- Important calls can be transferred to the user.
- Summary is stored after the call.

## Links

- Product TZ: `docs/product/personal-ai-assistant-tz.md`
- Open questions: `docs/product/open-questions.md`
- Spec: `docs/superpowers/specs/2026-06-11-stage4-inbound-calls.md`
- Plan: `docs/superpowers/plans/2026-06-11-stage4-inbound-calls-plan.md`
