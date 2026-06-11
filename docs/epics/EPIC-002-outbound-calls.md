# EPIC-002 - Outbound Calls

**Status:** Spec and plan drafted (2026-06-11), implementation not started
**Owner:** Nikita
**Goal:** Enable the assistant to place outbound calls, converse safely, stream transcript/events, and produce a summary.

## Scope

- Telephony integration
- Voice worker
- STT / LLM / TTS loop
- Call state machine
- Live transcript events
- Summary after call
- Retry and failed-call handling

## Out Of Scope

- Mass outbound calling
- Production-grade provider fallback
- Full compliance automation

## Dependencies

- EPIC-001 control plane
- Provider decisions for telephony, STT, LLM, and TTS
- Policy and approval hooks for sensitive actions

## Acceptance Criteria

- A task can initiate a real or sandbox outbound call.
- The assistant identifies itself as an AI assistant.
- Transcript segments are stored and streamed.
- Final summary and next steps are stored.
- Failed calls leave recoverable task_run state.

## Links

- Product TZ: `docs/product/personal-ai-assistant-tz.md`
- Spec: `docs/superpowers/specs/2026-06-11-stage2-outbound-calls.md`
- Plan: `docs/superpowers/plans/2026-06-11-stage2-outbound-calls-plan.md`

