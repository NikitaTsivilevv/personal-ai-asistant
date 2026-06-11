# Plan: Stage 6 - Observability, Cost, Reliability

**Spec:** `docs/superpowers/specs/2026-06-11-stage6-observability-cost-reliability.md`
**Epic:** EPIC-006 | **Status:** Draft

## Phase A - Tracing and cost

- [ ] A1. Trace id through all events; call detail view (web) rendering the full trace.
- [ ] A2. Provider usage capture per call; cost assembly; live estimated cost on live page.
- [ ] A3. `/costs` Telegram rollup; reconcile one month against real invoices.

## Phase B - Reliability

- [ ] B1. Worker heartbeats + orphaned-run reaper + idempotent event ingestion.
- [ ] B2. Sentry + healthchecks + Telegram alerts (worker down, run failed).
- [ ] B3. Twilio status callback reconciliation.

**Checkpoint:** kill-the-worker test passes (acceptance 4).

## Phase C - Cost levers and fallback

- [ ] C1. Hold/silence detection; LLM/TTS suspension and resume.
- [ ] C2. Provider fallback (secondary STT/TTS) with mid-call switch; chaos test.
- [ ] C3. Latency stats endpoint (p50/p95 per stage).

## Phase D - Validation

- [ ] D1. Run all five acceptance tests; update EPIC-006; closeout.

## Risks

- Hold-music detection false positives muting a live human: bias to short suspends with quick resume; log every suspend for review.
- Cost attribution accuracy depends on provider usage APIs; if unavailable, estimate from measured units and flag as estimate.
