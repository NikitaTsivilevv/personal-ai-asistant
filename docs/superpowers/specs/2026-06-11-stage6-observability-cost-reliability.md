# Spec: Stage 6 - Observability, Cost, Reliability (EPIC-006)

**Date:** 2026-06-11
**Status:** Draft
**Depends on:** Stage 2+ (real calls produce the data this stage organizes)

## 1. Goal

Make every call traceable end-to-end, cost-transparent, and resilient: worker crashes don't lose state, hold music doesn't burn money, and failures alert the user.

## 2. Scope

In scope:

- Tracing: one trace id per task_run linking task -> call -> transcript -> policy decisions -> approvals -> summary; queryable via API; rendered on the call detail page.
- Cost tracking: per-call cost assembled from provider usage (Twilio minutes, Deepgram seconds, LLM tokens, TTS characters); estimated live cost on the live page; actual cost stored on task_run; monthly rollup command in Telegram (`/costs`).
- Hold/silence handling: detect hold music/long silence (energy + classifier heuristics); suspend LLM/TTS during hold; cheap periodic "are they back?" checks; resume on speech. This is the main variable-cost lever (TZ §15).
- Reliability: worker heartbeats; orphaned-run reaper (running but no heartbeat -> failed with partial state); idempotent event ingestion; Twilio status callbacks reconciled against worker state.
- Monitoring: Sentry (api + worker), healthchecks (uptime ping), Telegram alerts for worker-down and failed runs.
- Provider fallback v1: config-driven secondary STT and TTS; automatic switch on provider 5xx/timeouts mid-call.
- Per-turn latency metrics (collected since Stage 2) surfaced: p50/p95 per stage on a simple stats endpoint.

Out of scope: multi-region HA, full APM, autoscaling, budget hard-caps (alerting only for MVP).

## 3. Acceptance Criteria

1. Any past call reconstructable from its trace alone (no log spelunking).
2. `/costs` shows month-to-date split by provider; per-call actual cost within ~15% of provider invoices.
3. Simulated hold (2 min of music) cuts LLM/TTS spend to near zero during the hold and resumes correctly.
4. Killed worker -> run marked failed within 60s, partial transcript intact, Telegram alert sent.
5. Forced Deepgram failure mid-call -> fallback STT takes over without dropping the call.
