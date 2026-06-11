---
name: personal-ai-session-closeout
description: Close a Personal AI Assistant project session by preserving state in durable docs. Use when the user says to close/save/snapshot/handover the session, after specs or plans are written or executed, after architecture/provider/privacy/compliance decisions, after meaningful implementation work, or when work is paused for later.
---

# Personal AI Session Closeout

Use this workflow to make sure a new Claude Code or Codex session can resume the Personal AI Assistant project without relying on chat history.

Do not manufacture process for tiny edits. Use this only after meaningful work or when the user asks to save project state.

## Workflow

### 1. Inventory The Session

Before editing docs, list what changed:

- Decisions made
- Specs/plans created or executed
- Epics changed
- Files/code changed
- Tests or validations run
- Work paused or blocked
- Open questions and risks discovered

State the inventory to the user if there is any uncertainty.

### 2. Update Decisions

Append `DECISIONS.md` for meaningful product, architecture, data, provider, privacy, compliance, deployment, or workflow decisions.

Use the existing D-entry format. Do not delete or rewrite old decisions except to mark them superseded.

### 3. Update Current Context

Refresh `PROJECT_CONTEXT.md`:

- `Last refreshed`
- Current status
- Current decisions
- Active epics
- Tech status
- How to resume

Keep it short. It is a cold-start briefing, not a complete history.

### 4. Update Epics

For every affected `docs/epics/EPIC-*.md`, update:

- Status
- Scope changes
- Dependencies
- Acceptance criteria if changed
- Links to new specs, plans, decisions, or handovers

### 5. Update Questions And Risks

Update:

- `docs/product/open-questions.md`
- `docs/product/risks.md`

Only add real unresolved questions or material risks.

### 6. Write Handover

Create:

```text
docs/superpowers/handovers/HANDOVER-YYYY-MM-DD-<topic>.md
```

Use Russian unless the user asks otherwise.

Include:

- One-sentence where-we-left-off
- What changed
- Decisions added
- Files/docs updated
- Validation run
- Open questions
- Risks
- Immediate next steps
- What to read next session

### 7. Consistency Check

Read the touched docs and check:

- No contradictory status
- New D-entries are referenced correctly
- Epic links point to existing files
- No unresolved placeholder markers unless intentionally tracked in open questions
- Dates use absolute `YYYY-MM-DD`

### 8. Report

Tell the user:

- Decisions added
- Docs updated
- Handover path
- Anything not done, such as tests not run or no git repo available
