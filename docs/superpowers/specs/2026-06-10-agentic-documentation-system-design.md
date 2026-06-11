# Agentic Documentation System Design

**Date:** 2026-06-10
**Status:** Approved and scaffolded
**Project:** Personal AI Assistant

## Context

The project is a personal MVP intended to become commercial later. Development will use Claude Code and Codex, so project state must survive context resets, tool switches, and long gaps between sessions.

The reference project (`C:\Leads4Deals\Lead system project`) uses `AGENTS.md`, `CLAUDE.md`, `PROJECT_CONTEXT.md`, `DECISION.md`, superpowers specs/plans, and handovers. That model works, but the new project should avoid loading the whole history into every agent session.

## Decision

Use an epic-driven documentation system with hot, warm, and cold context layers.

Hot context:

- `AGENTS.md`
- `CLAUDE.md`

Warm context:

- `PROJECT_CONTEXT.md`
- `DECISIONS.md`
- one relevant `docs/epics/EPIC-*.md`
- relevant spec/plan

Cold context:

- full product TZ
- old handovers
- provider research
- pricing notes
- compliance notes

The default context rule is: a normal agent task should read `AGENTS.md`, `PROJECT_CONTEXT.md`, one relevant epic, and the relevant spec/plan. It should not load the entire project history unless needed.

## Documentation Structure

```text
AGENTS.md
CLAUDE.md
PROJECT_CONTEXT.md
DECISIONS.md
README.md
docs/
  product/
    personal-ai-assistant-tz.md
    glossary.md
    open-questions.md
    risks.md
  epics/
    EPIC-001-control-plane.md
    EPIC-002-outbound-calls.md
    EPIC-003-policy-approvals.md
    EPIC-004-inbound-calls.md
    EPIC-005-integrations-memory.md
    EPIC-006-observability-cost-reliability.md
    EPIC-007-commercialization-compliance.md
  superpowers/
    specs/
    plans/
    handovers/
  research/
    providers/
    pricing/
    compliance/
apps/
  web/
  api/
  voice-worker/
packages/
  shared/
  database/
  policy/
```

## Closeout Workflow

Create a project-specific skill named `personal-ai-session-closeout`, not `project-snapshot`, to avoid conflict with the existing global skill used by another project.

The closeout workflow updates:

- `DECISIONS.md`
- `PROJECT_CONTEXT.md`
- affected epic files
- `docs/product/open-questions.md`
- `docs/product/risks.md`
- a new `docs/superpowers/handovers/HANDOVER-YYYY-MM-DD-<topic>.md`

Closeout is required after meaningful sessions: specs/plans, implementation, architecture decisions, provider/security/privacy/compliance decisions, or paused work. It is optional for tiny edits.

## Rationale

This balances MVP speed with commercial-readiness. Epics keep long-lived product context stable, while specs/plans remain small and feature-specific. The closeout workflow prevents important state from being trapped in chat history.

## Consequences

- Documentation must be maintained as part of development, not after the fact.
- Agents have a clear context-loading path, reducing token waste.
- Future commercialization work has places to track compliance, risks, and decisions early.
- The repo is ready for product scaffolding, but the application stack is still undecided.

