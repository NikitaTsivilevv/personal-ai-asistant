# Plan: Stage 7 - Commercialization And Compliance

**Spec:** `docs/superpowers/specs/2026-06-11-stage7-commercialization-compliance.md`
**Epic:** EPIC-007 | **Status:** Draft

Track A runs alongside stages 2-4; Track B starts only after months of real usage.

## Track A - Compliance for personal use

- [ ] A1. Disclosure policy doc (ES/EN/RU wording, repetition rules) -> implemented as the hardcoded disclosure in the worker (Stage 2 B2 consumes this).
- [ ] A2. Recording decision doc: AEPD position, consent flow design for the future; confirm recording stays OFF in config.
- [ ] A3. Data inventory + retention/deletion policy docs in `docs/research/compliance/`.
- [ ] A4. `/forget` command + retention jobs (transcript aging, fact deletion).
- [ ] A5. Provider ToS/DPA review notes for Twilio, Deepgram, Cartesia, LLM provider.

**Checkpoint:** safe-personal-use posture documented and enforced in code.

## Track B - Commercialization evidence (T+6 months of usage)

- [ ] B1. Define go/no-go criteria BEFORE analyzing data (e.g., >70% task success, <2 EUR per completed task, >=20 useful calls/month).
- [ ] B2. Evidence pack generator from EPIC-006 data (success rate, cost/task, failure taxonomy).
- [ ] B3. Niche validation: interviews/pilot with Spanish SMB or B2B2C candidate; notes in docs/research.
- [ ] B4. Commercial readiness checklist (auth/billing scope, processor-role GDPR shift, AI Act classification, ToS, lawyer review) - sized estimates only.
- [ ] B5. Go/no-go memo; decision recorded in DECISIONS.md.

## Risks

- Compliance docs rot: tie A3 inventory updates to the session-closeout checklist.
- Confirmation bias at go/no-go: criteria fixed in B1 before B2 data is examined.
