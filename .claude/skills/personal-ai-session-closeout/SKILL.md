---
name: personal-ai-session-closeout
description: Close a Personal AI Assistant project session by preserving state in durable docs. Use when the user says to close/save/snapshot/handover the session, after specs or plans are written or executed, after architecture/provider/privacy/compliance decisions, after meaningful implementation work, or when work is paused for later.
---

# Personal AI Session Closeout

Use this workflow to make sure a new Claude Code or Codex session can resume the Personal AI Assistant project without relying on chat history.

## Workflow

1. Inventory what changed this session: decisions, specs/plans, epics, files/code, validations, paused work, open questions, and risks.
2. Append `DECISIONS.md` for meaningful product, architecture, data, provider, privacy, compliance, deployment, or workflow decisions.
3. Refresh `PROJECT_CONTEXT.md` with current status and how to resume. Keep it short.
4. Update affected `docs/epics/EPIC-*.md` files with status, scope, dependencies, acceptance criteria, and links.
5. Update `docs/product/open-questions.md` and `docs/product/risks.md` when new questions or risks appeared.
6. Write `docs/superpowers/handovers/HANDOVER-YYYY-MM-DD-<topic>.md` in Russian unless the user asks otherwise.
7. Check touched docs for contradictions, broken references, missing dates, and accidental placeholders.
8. Report decisions added, docs updated, handover path, and anything not done.

The handover should include: where we left off, what changed, decisions added, files/docs updated, validation run, open questions, risks, immediate next steps, and what to read next session.

