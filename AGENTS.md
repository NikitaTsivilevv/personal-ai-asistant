# AGENTS.md - Personal AI Assistant

## Project Identity

**Name:** Personal AI Assistant for phone tasks
**Phase:** Documentation/bootstrap for MVP
**Date initialized:** 2026-06-10
**Primary owner:** Nikita
**Working style:** commercial-ready MVP-light process with AI agents

This project is a personal MVP intended to grow into a commercial product. Keep the process disciplined enough for future scale, but do not add enterprise bureaucracy before the product exists.

## Source Of Truth

| Domain | Source |
|---|---|
| Product requirements | `docs/product/personal-ai-assistant-tz.md` |
| Current project status | `PROJECT_CONTEXT.md` |
| Architecture/product decisions | `DECISIONS.md` |
| Long-lived workstreams | `docs/epics/EPIC-*.md` |
| Feature specs | `docs/superpowers/specs/` |
| Implementation plans | `docs/superpowers/plans/` |
| Session handovers | `docs/superpowers/handovers/` |

Do not treat chat history as durable project memory. If a decision matters, put it in the docs.

## Context Loading Rule

For a normal task, read only:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. One relevant epic from `docs/epics/`
4. The relevant spec/plan if one exists

Read the full product TZ, old handovers, research notes, or archived decisions only when needed. This keeps agent context and token usage under control.

## Planned Monorepo Layout

```text
apps/
  web/            # Dashboard / web UI
  api/            # HTTP API, auth, tasks, approvals, webhooks
  voice-worker/   # Long-lived realtime phone sessions
packages/
  shared/         # Shared types/contracts/utilities
  database/       # Schema, migrations, DB access helpers
  policy/         # Policy engine / approval rules
docs/
  product/
  epics/
  superpowers/
    specs/
    plans/
    handovers/
  research/
```

No application stack has been finalized yet. The TZ suggests possible technologies and providers, but provider/model/pricing decisions must be revalidated before implementation.

## Default Workflow

- Inspect docs and current files before making claims.
- Keep changes scoped to the relevant epic/spec.
- For non-trivial features, write or update a spec before implementation.
- For implementation work, create a task-by-task plan before coding.
- For architecture, data, provider, privacy, compliance, or deployment choices, append `DECISIONS.md` in the same session.
- Keep `PROJECT_CONTEXT.md` short and current.
- Update the relevant epic status when work begins, ships, blocks, or changes scope.
- End meaningful sessions with the `personal-ai-session-closeout` workflow.

## Documentation Standards

- `DECISIONS.md` is append-only. Supersede old decisions instead of deleting them.
- Epic files are long-lived containers; specs/plans are per-feature execution artifacts.
- Handovers are concise resume documents, not chat dumps.
- `docs/product/open-questions.md` tracks unresolved product/compliance/provider questions.
- `docs/product/risks.md` tracks material risks and mitigations.
- `docs/product/glossary.md` defines domain terms used in code and docs.

## Safety Rules

- Never commit secrets, phone numbers, API keys, webhook URLs, database URLs, or personal identity documents.
- Treat DNI, insurance IDs, medical details, addresses, recordings, transcripts, and contact data as sensitive.
- The assistant must disclose that it is an AI assistant when calling.
- Financial, legal, medical, or contract-changing actions require explicit approval unless a future decision narrows that rule.
- Before real production use in Spain/EU, legal/compliance review is required for GDPR, call recording, AI disclosure, and telephony provider terms.

## Validation

Validation commands are not established yet. Once apps are scaffolded, document exact commands here:

```text
apps/web: not established yet
apps/api: not established yet
apps/voice-worker: not established yet
```

Until then, documentation changes should at least be checked for internal consistency and broken references.
