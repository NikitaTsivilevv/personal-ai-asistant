# EPIC-002 - Outbound Calls

**Status:** Multi-turn live conversations work (2026-06-11 night session): 4 live calls to owner's phone; full loop verified (Twilio paid account, Cloudflare quick tunnel, Deepgram STT, claude-haiku-4-5 via OpenAI-compat per D-11, Cartesia TTS; LLM TTFB 0.6-0.7 s warm). Both blocking quality bugs are **fixed in code (PR #7), awaiting live validation**: (1) turn detection - root cause was `vad_analyzer=` being a silent no-op on `FastAPIWebsocketParams` in pipecat 1.3, so VAD was never wired; now tuned `VADParams` + `LocalSmartTurnAnalyzerV3` attach onto the user aggregator (`build_vad_analyzer`/`build_turn_analyzer` in `pipeline.py`); (2) role drift - language-aware `ROLE_FEWSHOT` in `agent.py`; offline A/B (`scripts/eval_role_drift.py`) shows haiku holds the caller role 3/3. Next live step: one call to confirm short replies + speech-over-disclosure register and the role holds in full multi-turn context, then phase D. Older TODOs stand: busy-vs-no-answer routing, kill-worker-mid-call recovery, Twilio 400 error bodies not logged.
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

