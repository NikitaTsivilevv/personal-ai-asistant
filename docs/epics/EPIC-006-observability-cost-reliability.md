# EPIC-006 - Observability, Cost, And Reliability

**Status:** Spec and plan drafted (2026-06-11), implementation not started
**Owner:** Nikita
**Goal:** Make calls traceable, recoverable, and cost-aware.

## Scope

- Technical logs
- Audit logs
- Call traces
- Cost estimates and actual cost tracking
- Health checks
- Voice worker recovery
- Hold/silence detection
- Monitoring and alerts

## Out Of Scope

- Enterprise observability platform
- Multi-region HA

## Dependencies

- Task/call data model
- Voice worker architecture
- Provider cost model

## Acceptance Criteria

- Each call has a trace: task -> run -> call -> transcript -> approvals -> summary.
- Estimated cost is visible during or after calls.
- Worker failures do not erase task/call state.
- Hold/silence periods can avoid unnecessary expensive processing.

## Links

- Risks: `docs/product/risks.md`
- Research: `docs/research/`
- Spec: `docs/superpowers/specs/2026-06-11-stage6-observability-cost-reliability.md`
- Plan: `docs/superpowers/plans/2026-06-11-stage6-observability-plan.md`
