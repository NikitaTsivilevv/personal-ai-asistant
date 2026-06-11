# Spec: Stage 4 - Inbound Calls (EPIC-004)

**Date:** 2026-06-11
**Status:** Draft
**Depends on:** Stages 2-3 (worker, policy engine)

## 1. Goal

The assistant answers calls to its own number, screens conservatively, transfers important calls to the user, and sends a Telegram summary after every call.

## 2. Scope

In scope:

- Number strategy for MVP: the assistant's existing Twilio number doubles as the inbound number; user shares it selectively. Personal-number forwarding deferred (open question stays open).
- Inbound webhook -> caller ID lookup against `contacts` -> route:
  - known contact with a stored scenario -> apply scenario;
  - known contact, no scenario -> polite screening with name context;
  - unknown -> strict screening: "who is calling and regarding what"; zero personal facts disclosed (hard policy default for inbound);
  - spam/robot heuristics (silence, synthetic voice, robocall patterns) -> polite hang-up, logged.
- Transfer to user: assistant offers/decides per rules, dials the user's phone and bridges; if user unavailable -> takes a message.
- Live notification: Telegram message at call start ("Assistant is on a call with X about Y") with a link to the live page; user can Take over / Transfer / Hang up from there.
- Post-call summary to Telegram for every inbound call; `calls` records get `direction` field.
- Inbound policy profile in `packages/policy`: inbound defaults stricter than outbound; disclosure of being an AI assistant on answer.

Out of scope: voicemail transcription products, multi-number management, do-not-disturb schedules (later), forwarding from personal number (revisit after MVP usage).

## 3. Design Notes

- Inbound reuses the same worker, pipeline, and event contract; only the entry path (Twilio inbound webhook -> worker claims a `task_run` of synthetic task type `inbound_call`) differs.
- Screening transcript is the product: summary template = who, why, urgency, requested action, suggested next step.
- Important-call detection v1 = rule list (keywords, known-contact priority flags), not ML.

## 4. Acceptance Criteria

1. Call from an unknown number gets screened; no personal facts revealed; summary lands in Telegram.
2. Call from a known contact maps to its scenario.
3. An "important" call is bridged to the user's phone; failed bridge -> message taken.
4. Spam test call is terminated and logged.
5. Every inbound call produces a task_run trace identical in shape to outbound.
