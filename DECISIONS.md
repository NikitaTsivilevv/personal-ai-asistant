# DECISIONS.md - Personal AI Assistant

This file records product and architecture decisions so future agent sessions can recover the reasoning without relying on chat history.

Append new entries. Do not delete old entries. Supersede them explicitly.

Entry format:

- **D-N - Title**
- **Date:** YYYY-MM-DD
- **Status:** Accepted / Superseded by D-X / Rejected
- **Context:** problem or uncertainty
- **Decision:** what was chosen
- **Rationale:** why
- **Consequences:** trade-offs and follow-ups

---

## D-1 - Commercial-ready MVP-light documentation process

- **Date:** 2026-06-10
- **Status:** Accepted
- **Context:** The project is a personal MVP, but the owner intends to commercialize it later. The process must support AI-agent collaboration without overloading early development.
- **Decision:** Use a disciplined documentation system from day one: `AGENTS.md`, `CLAUDE.md`, `PROJECT_CONTEXT.md`, `DECISIONS.md`, product docs, epics, superpowers specs/plans, and handovers.
- **Rationale:** AI agents lose chat context across sessions. Durable, structured docs reduce repeated explanations, preserve architectural reasoning, and keep token usage controlled.
- **Consequences:** Meaningful sessions should update project docs. Lightweight fixes do not need full ceremony, but architecture/product/provider/privacy decisions must be recorded.

## D-2 - Monorepo for the MVP

- **Date:** 2026-06-10
- **Status:** Accepted
- **Context:** The system will likely include a web dashboard, API, voice worker, shared contracts, database schema, and policy engine.
- **Decision:** Start as a monorepo with planned folders `apps/web`, `apps/api`, `apps/voice-worker`, `packages/shared`, `packages/database`, and `packages/policy`.
- **Rationale:** A monorepo makes early AI-agent work easier: fewer repositories to load, easier shared types/contracts, simpler cross-component specs, and one documentation root.
- **Consequences:** Repo boundaries can be split later if deployment, ownership, or scaling needs justify it. Initial docs must avoid assuming one deploy target for all components.

## D-3 - Epic-driven documentation model

- **Date:** 2026-06-10
- **Status:** Accepted
- **Context:** The TZ naturally decomposes into multiple long-lived workstreams: control plane, outbound calls, approvals, inbound calls, integrations, observability, and compliance.
- **Decision:** Use `docs/epics/EPIC-*.md` as long-lived containers for product workstreams. Specs and plans remain per-feature execution artifacts.
- **Rationale:** Epics help agents load one bounded product area instead of the whole project. They also give a stable place to track scope, status, dependencies, acceptance criteria, and links to specs/plans.
- **Consequences:** Epics must be updated during closeout. Stale epic status is worse than no epic status.

## D-4 - Project-specific session closeout skill

- **Date:** 2026-06-10
- **Status:** Accepted
- **Context:** Another project already uses a global `project-snapshot` skill. Reusing that name here could cause confusion or trigger the wrong workflow.
- **Decision:** Create a project-specific closeout workflow named `personal-ai-session-closeout`.
- **Rationale:** The new skill keeps this project's closeout rules separate while preserving the useful pattern: update decisions, context, epics, open questions, risks, and write a handover.
- **Consequences:** End meaningful sessions with this workflow. Do not rename or overwrite the existing global `project-snapshot` skill.

## D-5 - Voice worker built on Pipecat with self-selected providers

- **Date:** 2026-06-11
- **Status:** Accepted
- **Context:** The TZ proposed a fully custom STT/LLM/TTS pipeline. Market research (2026) shows three viable approaches: managed platforms (Vapi/Retell, ~$0.07-0.15/min, vendor lock-in, policy logic constrained to their webhook model), open-source pipeline frameworks (Pipecat v1.0, LiveKit Agents), or a from-scratch pipeline (1-2 months of solved realtime problems).
- **Decision:** Build the voice worker on Pipecat (open source, Python) with Twilio telephony, Deepgram STT, swappable LLM, and Cartesia TTS, deployed as a long-lived process on a small VPS.
- **Rationale:** Pipecat provides turn-taking, VAD, barge-in, and reconnect out of the box while keeping full control of the conversation loop. The policy engine and approvals - the product's core differentiation - embed directly in the pipeline. Per-minute cost stays at provider cost (~$0.04-0.13/min all-in), audio/data flows through our own server (important for the EU/GDPR positioning), and every provider layer is swappable. Managed platforms were rejected for lock-in, margin loss, and US data flow; from-scratch was rejected as months of work on already-solved plumbing with no product advantage.
- **Consequences:** Voice worker is Python. First real call lands later than with a managed platform (~1-2 weeks of integration). Hosting/uptime of the worker is our responsibility. Turn-taking tuning for Spanish call centers (IVR, hold music) is our work.

## D-6 - MVP interface: Telegram bot plus minimal live-call web page

- **Date:** 2026-06-11
- **Status:** Accepted
- **Context:** The TZ left open whether the first interface is a web dashboard, Telegram, or both.
- **Decision:** Ship both, minimally: Telegram bot for task creation, approvals, and post-call summaries; a single minimal web page for live call control (live transcript, Approve/Reject/Take over/Hang up/Whisper).
- **Rationale:** Telegram is the fastest path for asynchronous interactions and push-style approvals. Live in-call control needs a richer realtime surface than Telegram provides. Splitting by interaction mode covers the full TZ control set with minimal UI work.
- **Consequences:** Two thin frontends instead of one full dashboard. The web page stays single-purpose until the MVP proves itself.

## D-7 - Light multi-tenant groundwork, no premature productization

- **Date:** 2026-06-11
- **Status:** Accepted
- **Context:** The project is personal first but intended for possible commercialization. Market research shows the viable commercial niche is EU/Spain compliance-first calling (EU AI Act Article 50 applies from August 2026), not competing with US platforms.
- **Decision:** Build for one user but avoid single-user hardcoding: `user_id` on all owned tables, no global singletons for profile/policy, language kept configurable, AI disclosure and audit log treated as core features rather than compliance afterthoughts. No auth/billing/tenant isolation work beyond that.
- **Rationale:** Near-zero cost now; dramatically cheaper migration later. Compliance-first design (disclosure, approvals, audit) doubles as the commercial differentiator.
- **Consequences:** Slight schema/API verbosity. Real multi-tenancy (auth, billing, isolation) is deferred until commercialization is decided.

## D-8 - Backend language split: Python services, TypeScript web

- **Date:** 2026-06-11
- **Status:** Accepted
- **Context:** D-5 fixes the voice worker to Python (Pipecat). The TZ allowed FastAPI, NestJS, or Hono/Next API routes for the API.
- **Decision:** Python for `apps/api` (FastAPI) and `apps/voice-worker` (Pipecat) and the Telegram bot (aiogram, inside or beside the API); TypeScript/Next.js only for the minimal live-call web page. Shared contracts defined once (Pydantic models + generated OpenAPI types for web).
- **Rationale:** The voice worker is unavoidably Python; keeping API/bot in Python avoids duplicating domain models, policy logic, and DB access across two languages. The web surface is small enough that a TS island is cheap.
- **Consequences:** `packages/shared` holds Pydantic schemas; web types are generated from OpenAPI. Revisit if the web dashboard grows.

## D-9 - Stage 1 implementation choices: uv workspace, separate bot app, Redis lists + pub/sub

- **Date:** 2026-06-11
- **Status:** Accepted
- **Context:** Scaffolding EPIC-001 required concrete choices the specs left open: Python dependency management, where the Telegram bot lives (D-8 said "inside or beside the API"), and the queue/event transport shape on Redis.
- **Decision:**
  - uv workspace monorepo (root `pyproject.toml`, Python 3.12 pinned) with hatchling-built packages; shared dev deps (pytest, ruff, fakeredis, aiosqlite) at the root.
  - Telegram bot is a separate app `apps/bot` (own process), not a module inside `apps/api`.
  - Redis transport: task dispatch via list `queue:task_runs` (LPUSH/BRPOP); per-run control via list `run:{run_id}:control` (approval resolutions, cancellation reach the waiting worker); broadcast via pub/sub channel `events:runs` consumed by SSE endpoints and the bot notifier. Key names and payload models live in `assistant_shared.queue`/`events`.
  - Tests run against in-memory sqlite (StaticPool) + fakeredis; Postgres/Upstash only via env config.
- **Rationale:** uv is the fastest current Python workspace tool and gives one lockfile. A separate bot process keeps long-polling out of the API's lifecycle and lets it restart independently. Lists give at-least-once handoff where exactly one consumer must act (queue, worker unblock); pub/sub is fan-out for observers where missing a message is tolerable. sqlite/fakeredis keep tests free of provisioned infra (no service registrations yet).
- **Consequences:** Queue has no persistence guarantees beyond Redis durability - acceptable for stage 1, revisit (streams/consumer groups) in EPIC-006. Bot deployment is a fourth process. JSON columns use JSONB on Postgres via `with_variant`, so sqlite tests don't exercise JSONB-specific behavior.

## D-10 - Policy engine v1: rules as data, hard floor in code, scenario profiles

- **Date:** 2026-06-11
- **Status:** Accepted
- **Context:** EPIC-003 required turning the stage-1 policy stub into a real engine. Open choices: where rules live, how the financial/legal/medical safety rule is enforced, and how per-scenario behavior is selected.
- **Decision:**
  - Action taxonomy and rule schema live in `assistant_shared.policy`; rules are declarative JSON profiles shipped inside `assistant_policy/rules/` (one file per scenario: generic, insurance, doctor, restaurant, info_gathering), first match wins, generic is the fallback for unknown scenarios.
  - The safety hard floor is enforced in engine code, not rules: `agree_payment`, `accept_terms`, `say_sensitive`, and high-sensitivity disclosures can never resolve to `allow`, regardless of rule content.
  - `structured_goal.scenario` (default "generic") selects the profile. Profile facts carry `allowed_scenarios`; the worker feeds the same scenario-aware fact allowlist to both the agent prompt and the engine.
  - Every decision carries a rule id + inputs hash and is pushed as a `policy_decision` run event, audited with `actor=policy`.
  - In-call approvals expire after 120 s (configurable): the approval row becomes `expired`, the run resumes, the agent speaks a wrap-up phrase instead of hanging.
- **Rationale:** Rules-as-data keeps the engine ~200 lines and the matrix fully testable; a code-level floor means no rule file edit can weaken the AGENTS.md safety rule; rule ids + hashes make the audit trail reproducible (EU positioning per D-7).
- **Consequences:** New scenarios = new JSON file + tests, no engine changes. The LLM-facing tool argument enum is mapped to the taxonomy in the worker; adding actions touches both. JSON profiles ship inside the wheel - rule changes require redeploys until a DB-backed rule store is justified.


## D-11 - Conversation LLM switched to Anthropic claude-haiku-4-5 via OpenAI-compat endpoint

- **Date:** 2026-06-11
- **Status:** Accepted (revisit after live-call quality tuning)
- **Context:** Mid live-session the OpenAI key hit `insufficient_quota` (429), leaving the call agent mute after the scripted disclosure. The worker's conversation LLM is an OpenAI-compatible client with env-configurable `LLM_BASE_URL`/`LLM_MODEL` (D-5 "swappable LLM").
- **Decision:** Point the conversation LLM at Anthropic's OpenAI-compatibility endpoint (`LLM_BASE_URL=https://api.anthropic.com/v1/`, `LLM_MODEL=claude-haiku-4-5`, Anthropic API key). No code changes; the old OpenAI config is kept commented in `.env`.
- **Rationale:** The Anthropic key was already funded and verified working (task normalization + call summaries). Haiku is the latency/cost-appropriate tier for voice turns (observed LLM TTFB 0.6-0.7 s after warmup, 2.2 s first turn). The swap validated the D-5 provider-swap mechanism end-to-end, including tool calling.
- **Consequences:** Live calls revealed residual role confusion on haiku (agent slips into receptionist role at the patient-data stage) despite an explicit role block in the prompt. Open follow-up: tune the prompt further, try a stronger model (claude-sonnet-4-6 or restored gpt-4o-mini) and compare, or keep haiku and add few-shot examples. Cost envelope per D-5 must be rechecked if the model tier changes.
- **Follow-up (2026-06-11, offline A/B):** The few-shot fix shipped in PR #7 (language-aware `ROLE_FEWSHOT` in `agent.py`) was evaluated offline with `scripts/eval_role_drift.py` against the data-stage turn via the Anthropic OpenAI-compat endpoint, 3 runs per model. Using a probe name absent from the few-shot (`Carlos Ruiz`, to rule out echo of the illustrative example), both `claude-haiku-4-5` and `claude-sonnet-4-6` held the caller role 3/3 — each stated the actual ALLOWED FACTS name ("a nombre de Carlos Ruiz") instead of asking the callee. Conclusion: the few-shot is sufficient to hold the role on haiku at this isolated turn, so **no model-tier escalation is needed; D-11 stays on `claude-haiku-4-5`.** Caveat: the harness is tool-free (no function tools registered, unlike the live pipeline) and single-turn, so a live multi-turn call is still required to confirm role-holding in full context (EPIC-002).

## D-12 - Next workstream: eval-driven development, scenario-routing wiring, reliability before scale

- **Date:** 2026-06-11
- **Status:** Accepted (direction; concrete execution to be confirmed via brainstorming next session)
- **Context:** The live pipeline works and the two quality bugs (turn detection, role drift) are fixed in code (PR #7; offline A/B shows haiku holds the role). A session-end assessment of the codebase surfaced three things worth recording: (1) **the scenario system is built but not wired into intake** — `apps/bot/.../normalize.py` (`_SYSTEM_PROMPT`) extracts objective/constraints/allowed_facts/autonomy/phone/name/title but **not** `scenario`, and `handlers.confirm_task` does not pass one, so `structured_goal.scenario` is always `generic`; the doctor/insurance/restaurant rule profiles and scenario-scoped facts (`allowed_scenarios`) therefore lie dormant. (2) **Almost no automated evaluation exists** (a single offline role-drift probe), so prompt/model/scenario changes are made blind. (3) **The dev stand is fragile** — no process supervision; api+bot were found dead this session (Telegram bot "not reacting") and had to be hand-restarted.
- **Decision:** Adopt eval-driven development as the next workstream and sequence offline-doable work ahead of anything needing a phone: (a) wire scenario detection into intake so the existing policy profiles and scenario facts activate; (b) build an **offline evaluation harness with an LLM "callee simulator"** across the five scenarios, asserting task success, policy correctness, role-holding, latency and cost — generalising `scripts/eval_role_drift.py`; (c) add process supervision + reconnect for api/bot; (d) generalise/scenario-ise the booking-flavoured few-shot once eval can measure it. Defer live-only work (turn-detection live validation, EPIC-003 phase D scenarios, EPIC-002 D1 booking, EPIC-003 C2/C3) until a phone is available.
- **Rationale:** The policy engine is the product differentiator but is inert without scenario wiring; an eval harness makes every downstream change measurable and safe and is fully offline; reliability is the real blocker to "real use", not features. This matches voice-AI best practice: eval-driven loops, scenario playbooks, layered guardrails, latency/cost budgets, supervised processes.
- **Consequences:** Next session should brainstorm → spec → plan the eval harness (and/or scenario wiring) before coding. Eval output feeds back into D-11 (model floor) and the policy rules (tuning from simulated + live audit data). A simulated callee approximates, but does not replace, real PSTN audio/behaviour, so live validation stays on the roadmap.

## D-13 - Scenario routing wired into intake; eval harness architecture; eval_role_drift retired

- **Date:** 2026-06-12
- **Status:** Accepted
- **Context:** D-12 identified two offline-doable workstreams: (a) wire scenario detection into bot intake so dormant policy profiles activate, and (b) build an offline eval harness generalising the single `scripts/eval_role_drift.py` probe. Both shipped on branch `feature/scenario-routing-eval-harness` (Tasks 1-13, all reviewed).
- **Decision:**
  - Scenario routing: `assistant_shared.schemas.SCENARIOS` constant (consistency-tested vs policy rule files and vs the Scenario enum); `normalize.py` extracts `scenario` from the NLP result (unknown → generic + warning); bot confirm card shows scenario with one-tap correction ("Сменить сценарий" inline button). `build_call_pipeline` extracted from `run_call_pipeline` for DI.
  - Eval harness architecture (`packages/evals`, package `assistant_evals`): full Pipecat pipeline with text-edge transport (owner choice over a Pipecat-free loop — measurement fidelity: the harness exercises the real tool-calling, policy engine, and approval control list, not a stub); LLM callee simulator with mandatory probes and `[HANGUP]` signal; `FakeRunClient` + scripted `ApprovalResponder` over the real control list (approve/reject/expire); hybrid scoring: policy axis deterministic (incl. `forbid_unexpected_policy` guard and sensitive-leak check), success axis judge-authoritative + clean-termination + deterministic over-claim guards, role axis markers + judge, latency informational (LLM TTFB only), cost from token usage; dialog driver with crash containment; CLI `uv run python -m assistant_evals run` with `--scenario/--case/--model/--sim-model/--judge-model/--runs/--max-cost/--out`; JSON artifacts in `evals-results/` (gitignored). 6 case YAML cards across all 5 scenarios.
  - `scripts/eval_role_drift.py` and `tests/test_eval_role_drift.py` retired; absorbed by `packages/evals/cases/doctor/role_drift_probe.yaml` (verified live 3/3, see Consequences).
- **Rationale:** Text edges keep the harness fully offline while exercising the real pipeline graph; a Pipecat-free loop would require duplicating tool-dispatch and policy wiring. LLM callee simulator is cheaper and faster than a human-in-the-loop harness and covers all five scenario profiles. Scripted approvals over the real control list ensure policy tests are not mocked away. Retiring `eval_role_drift.py` removes a one-off script now superseded by a case that runs in full multi-turn, tool-enabled context.
- **Consequences:**
  - Live smoke (2026-06-12, agent=claude-haiku-4-5, sim=claude-haiku-4-5, judge=claude-sonnet-4-6): `doctor/role_drift_probe` PASSED 3/3 all axes — closes the D-11 A/B caveat (role-holding confirmed in full tool-enabled multi-turn context, not just an isolated turn). Full 6-case sweep sim+judge cost ≈ $0.05–0.07 per sweep; total Task-13 spend ≈ $0.21. Avg LLM TTFB per turn: 0.5–1.8 s.
  - Genuine agent findings (not harness bugs): haiku frequently fails to call `end_call`/`propose_summary` (dominant reliability gap — now measurable, feeds D-12 (d) few-shot work and D-11 model-floor reassessment); intermittent high-sensitivity DNI disclosure without `request_approval` (caught by policy axis); intermittent role-drift marker and payment over-commit in restaurant case. Non-deterministic across runs — use `--runs 3+` for signal.
  - Open items: (1) case-design precondition issue — `insurance/cancel_denied` and `generic/approval_expiry` expect the agent to attempt the gated action; a conservative agent that refuses verbally never triggers the policy engine → "missing expected decision" policy fail; needs multi-run confirmation before retuning. (2) `tools.py` builds `ActionRequest` without `fact_key`, so the engine's fact-access deny branch is unreachable from the worker in production — a separate fix, not addressed on this branch.
