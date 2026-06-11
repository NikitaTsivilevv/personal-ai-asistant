# Plan: Stage 2 - Outbound Calls

**Spec:** `docs/superpowers/specs/2026-06-11-stage2-outbound-calls.md`
**Epic:** EPIC-002 | **Status:** Phases A/B/C done (A live-verified 2026-06-11 evening: real hello-world call over Twilio + Cloudflare Tunnel completed with transcript and summary). Phase D pending.

## Phase A - Providers and hello-world call

- [x] A1. Recheck pricing/models (Deepgram, Cartesia, LLM, Twilio ES); record results in `docs/research/`; append a decision if model choices change. *(`docs/research/2026-06-11-provider-pricing.md`: ~$0.04/min landline, within D-5 envelope; no model changes.)*
- [x] A2. Twilio account, Spanish number, outbound calling enabled; webhook endpoints in FastAPI.
- [x] A3. Pipecat hello-world: worker dials a test phone, plays TTS greeting, transcribes replies to logs. (Dev via Cloudflare Tunnel.) *(Live call to owner's phone 2026-06-11: RU disclosure spoken first, Cartesia TTFB 0.17s, run completed with LLM summary. Fixed missing `return app` in `call/server.py` found during bring-up.)*

**Checkpoint:** you can talk to a dumb agent on a real phone. ✓ (2026-06-11)

## Phase B - Real agent loop

- [x] B1. Agent core: system prompt assembly from structured_goal/profile_facts, conversation loop, ES/EN/RU. *(`call/agent.py`; profile_facts loading from DB lands with EPIC-005, structure ready.)*
- [x] B2. Mandatory disclosure as hardcoded first utterance (TTSSpeakFrame, not LLM-generated); call state machine; no-answer/voicemail/busy branches. *(`call/state.py`; busy-vs-no-answer detection from Twilio callbacks is a live-session TODO - worker currently times out as no_answer.)*
- [x] B3. Tool calls (`request_approval`, `end_call`, `log_fact`, `propose_summary`) wired through `packages/policy.evaluate()`. *(`call/tools.py` + ControlRouter for mid-call whisper/hangup.)*
- [x] B4. Event streaming: transcript segments + state changes through the Stage-1 internal event API (contract unchanged). *(Frame observer; pipecat 1.3 removed TranscriptProcessor.)*

**Checkpoint:** scripted test call passes with approval pause/resume. *(Approval pause/resume verified via tests against the real API; scripted VOICE call needs providers.)*

## Phase C - Surfaces and resilience

- [x] C1. Live-call web page: SSE transcript, status, Hang up, Whisper input. *(`apps/web/app/runs/[id]`; CORS added to API.)*
- [x] C2. Post-call summary generation -> task_run + Telegram push. *(`call/summary.py`: LLM + template fallback; Telegram push reuses stage-1 notifier.)*
- [x] C3. Retry/backoff for no-answer/busy; crash recovery via API stale-run sweeper (tested); live kill-worker-mid-call test pending providers.
- [x] C4. Per-turn latency metrics stored (groundwork for EPIC-006). *(TTFB per stage from pipecat MetricsFrame; attached to run_completed/failed payload -> audit_log.)*

## Phase D - Real-world validation

- [ ] D1. Real restaurant booking end-to-end; capture transcript and failure notes in `docs/research/`.
- [ ] D2. Verification pass vs acceptance criteria; update EPIC-002; session closeout.

## Risks

- Spanish IVR menus / hold music may block calls: if hit, add simple DTMF navigation tool; full hold detection stays in EPIC-006.
- Latency >1.5s makes conversation unnatural: tune streaming TTS first, then LLM choice.
