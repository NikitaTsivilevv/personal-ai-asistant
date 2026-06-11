# Plan: Stage 2 - Outbound Calls

**Spec:** `docs/superpowers/specs/2026-06-11-stage2-outbound-calls.md`
**Epic:** EPIC-002 | **Status:** Draft

## Phase A - Providers and hello-world call

- [ ] A1. Recheck pricing/models (Deepgram, Cartesia, LLM, Twilio ES); record results in `docs/research/`; append a decision if model choices change.
- [ ] A2. Twilio account, Spanish number, outbound calling enabled; webhook endpoints in FastAPI.
- [ ] A3. Pipecat hello-world: worker dials a test phone, plays TTS greeting, transcribes replies to logs. (Dev via Cloudflare Tunnel.)

**Checkpoint:** you can talk to a dumb agent on a real phone.

## Phase B - Real agent loop

- [ ] B1. Agent core: system prompt assembly from structured_goal/profile_facts, conversation loop, ES/EN/RU.
- [ ] B2. Mandatory disclosure as hardcoded first utterance; call state machine; no-answer/voicemail/busy branches.
- [ ] B3. Tool calls (`request_approval`, `end_call`, `log_fact`, `propose_summary`) wired through `packages/policy.evaluate()`.
- [ ] B4. Event streaming: transcript segments + state changes through the Stage-1 internal event API (contract unchanged).

**Checkpoint:** scripted test call passes with approval pause/resume.

## Phase C - Surfaces and resilience

- [ ] C1. Live-call web page: SSE transcript, status, Hang up, Whisper input.
- [ ] C2. Post-call summary generation -> task_run + Telegram push.
- [ ] C3. Retry/backoff for no-answer/busy; crash-recovery test (kill worker mid-call, verify state).
- [ ] C4. Per-turn latency metrics stored (groundwork for EPIC-006).

## Phase D - Real-world validation

- [ ] D1. Real restaurant booking end-to-end; capture transcript and failure notes in `docs/research/`.
- [ ] D2. Verification pass vs acceptance criteria; update EPIC-002; session closeout.

## Risks

- Spanish IVR menus / hold music may block calls: if hit, add simple DTMF navigation tool; full hold detection stays in EPIC-006.
- Latency >1.5s makes conversation unnatural: tune streaming TTS first, then LLM choice.
