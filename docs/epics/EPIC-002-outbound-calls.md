# EPIC-002 - Outbound Calls

**Status:** First **real third-party** outbound call placed 2026-06-12 (run `84c4c3c6`, Pizza Parking restaurant; transcript in Neon `transcript_segments`). Full loop works end-to-end. The call surfaced two defects, both now **fixed (D-14, merged to `main` via PR #12) and live-validated via the eval harness**: (1) **wrong booking name** — agent said "a nombre de Nikita" (owner) instead of "Victoria" (task) because `allowed_facts` is a profile-key whitelist, not a value carrier, so the booking name was dropped before the prompt; fixed with the new `call_facts` channel + `DETAILS FOR THIS CALL` prompt block + few-shot rewrite (`restaurant/booking_third_party` eval ×3: states Victoria, never Nikita). (2) **call never terminated** — agent said goodbye but didn't call `end_call`, leaving the run `running`; fixed with a stronger prompt rule + a deterministic in-call backstop (`TerminationGuard`: duration/turn caps force a hangup regardless of the LLM). Earlier 2026-06-11 work (PR #7) remains: turn detection (VAD/smart-turn wired onto the user aggregator after the `vad_analyzer=` no-op fix) and role-drift few-shot. **Still open:** voluntary `end_call` is unreliable on haiku (live `--runs 5`: 2–5/5 by scenario) — backstop covers production, model-floor reassessment open (D-11); role drift at the data/wrap-up stage when the agent lacks a datum (asks the callee instead of acknowledging) — risks.md; result over-claim, STT mishearing, word-by-word transcript granularity — risks.md. Live validation of turn detection in full audio still pending a phone session. Older TODOs stand: busy-vs-no-answer routing, kill-worker-mid-call recovery, Twilio 400 error bodies not logged. **Audit 2026-06-14 (D-15):** the remaining open items are reframed as symptoms of two root causes (conversation LLM below the reliability floor + a monolithic single-prompt agent / context rot) plus an audio-blind eval. Chosen direction: re-platform the dialog onto **Pipecat Flows** (per-node scoped tools), raise the model floor (**Gemini 2.5 Flash / GPT-4.1**), keep+strengthen the deterministic backstop (forced tool_choice), ground result-claims in tool results, add **Nova-3 keyterm** STT and an **audio eval tier** — execution via brainstorm → spec → plan; the re-platform may become its own epic. The current monolithic prompt + `call_facts` + role few-shot are interim until then.
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

