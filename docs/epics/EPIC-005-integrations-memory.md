# EPIC-005 - Integrations And Memory

**Status:** Spec and plan drafted (2026-06-11), implementation not started
**Owner:** Nikita
**Goal:** Give the assistant controlled access to calendar, contacts, documents, and allowed user facts.

## Scope

- Contacts
- Calendar integration or manual calendar entries
- Profile facts
- Documents and attachments
- Optional semantic memory
- Tool access boundaries

## Out Of Scope

- Broad email/browser automation before policy boundaries exist
- Unreviewed storage of highly sensitive documents

## Dependencies

- Policy engine
- Data model
- Privacy/security decisions

## Acceptance Criteria

- Profile facts are stored with purpose and sensitivity.
- Assistant can use only facts allowed for the current task.
- Calendar/contact access is auditable.
- Sensitive data handling rules are documented before implementation.

## Links

- Glossary: `docs/product/glossary.md`
- Open questions: `docs/product/open-questions.md`
- Risks: `docs/product/risks.md`
- Spec: `docs/superpowers/specs/2026-06-11-stage5-integrations-memory.md`
- Plan: `docs/superpowers/plans/2026-06-11-stage5-integrations-memory-plan.md`
