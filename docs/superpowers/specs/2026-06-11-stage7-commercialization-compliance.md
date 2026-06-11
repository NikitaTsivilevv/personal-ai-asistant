# Spec: Stage 7 - Commercialization And Compliance (EPIC-007)

**Date:** 2026-06-11
**Status:** Draft (mostly research/documentation work, partially parallel to earlier stages)
**Depends on:** Real usage data from stages 2-6; market validation summary of 2026-06-11

## 1. Goal

Two deliverables: (a) compliance posture good enough for safe *personal* use in Spain now, and (b) an evidence-based go/no-go package for commercialization after 6-12 months of real use.

## 2. Context (from 2026-06-11 validation)

The commercial niche is EU/Spain compliance-first calling, not competing with US platforms (Vapi/Retell). EU AI Act Article 50 (AI disclosure) applies from August 2026; AEPD has issued guidance on AI voice transcription (Jan/Apr 2026). Likely commercial forms, in order of realism: small business in Spain (bookings, confirmations, inbound screening), B2B2C embedding (brokers, gestorias, clinics), pure B2C subscription (weakest economics - low call frequency; cf. Mitra's pivot to SMB, Google Duplex history).

## 3. Scope

Track A - compliance for personal use (do early, alongside stages 2-4):

- AI disclosure policy doc: exact wording ES/EN/RU, when repeated (transfers, long calls), non-audio alternative consideration (Art. 50 reads).
- Recording decision: MVP keeps recording OFF, transcript-only; document AEPD position and what consent flow would be required to enable it.
- Data inventory: sensitive categories held (DNI, medical, insurance), where stored, encryption status, retention.
- Retention/deletion policy: defaults (e.g., transcripts 12 months, then summarized; facts until deleted) + `/forget` deletion command actually implemented.
- Provider terms review: Twilio/Deepgram/Cartesia/LLM ToS for AI-calling use and EU data processing; record DPA availability.

Track B - commercialization readiness (after usage data exists):

- Usage evidence pack: success rate per scenario, cost per completed task, failure taxonomy, minutes/month - auto-derived from EPIC-006 data.
- Niche validation: 5-10 interviews with Spanish SMBs (or one pilot user); willingness-to-pay signal.
- Commercial readiness checklist: multi-tenant auth/billing scope, GDPR processor role change (we become processor for customers' callees), AI Act risk classification, insurance, terms of service - each item sized, not solved.
- Go/no-go memo template with decision criteria set *before* looking at the data.

Out of scope: legal advice in the repo (external lawyer review is a checklist item), certifications, building any multi-tenant features (only scoping).

## 4. Acceptance Criteria

1. Disclosure policy and retention policy docs exist in `docs/research/compliance/` and are implemented in the worker (disclosure) and DB jobs (retention).
2. `/forget` deletes a fact/contact/task data and is audit-logged.
3. Data inventory current as of each closeout touching schema.
4. After 6 months of usage: evidence pack auto-generated; go/no-go memo written against pre-set criteria.
