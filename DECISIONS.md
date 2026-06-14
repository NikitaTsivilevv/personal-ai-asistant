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

## D-14 - Task-scoped call data (`call_facts`) + deterministic call-termination backstop

- **Date:** 2026-06-12
- **Status:** Accepted
- **Context:** The first **real** outbound call (run `84c4c3c6`, Pizza Parking, transcript pulled from Neon `transcript_segments`) exposed two defects. (#1) The task said "booking under the name Victoria"; `normalize.py` correctly extracted it into `structured_goal.allowed_facts`, but the worker treats `allowed_facts` as a **whitelist of OWNER profile-fact keys** (`agent.py:allowed_facts` filters profile facts by key), so "Victoria" matched no profile fact and was silently dropped before reaching the prompt. The only name in `ALLOWED FACTS` was the owner's `Имя: Nikita`, and `ROLE_FEWSHOT` hard-instructed "state the name from ALLOWED FACTS" — so the agent said "a nombre de Nikita". There was **no channel for data specific to a call** (booking name, date, party size) distinct from the owner's persistent profile. (#3) The agent said a full goodbye but never called `end_call`; the run was left `running` with zero tool events — the pipeline only finalizes on media-stream close, and nothing forced the call to end when the agent had verbally finished.
- **Decision:**
  - **`call_facts`**: add `StructuredGoal.call_facts: dict[str, str]` (no DB migration — it lives in the JSON `structured_goal`). It carries data the agent states to the callee for THIS call, separate from `allowed_facts`. Flows end-to-end: `normalize.py` extracts it (third-party booking names go here, not `allowed_facts`); the bot confirm card shows it; `build_system_prompt` renders a `DETAILS FOR THIS CALL` block; `ROLE_FEWSHOT` rewritten to source the booking name from `DETAILS FOR THIS CALL` (else the client's name from `ALLOWED FACTS`). `_POLICY_PREAMBLE` rule 2 gets a carve-out: call_facts are client-provided for this call and may be stated directly (NOT approval-gated, NOT fed into the `disclose_fact` engine). Newlines stripped from rendered call_facts (prompt-injection defense-in-depth).
  - **Termination**: `_POLICY_PREAMBLE` rule 6 strengthened to "you MUST call end_call"; new `TERMINATION_WRAPUP` phrase; worker settings `max_call_duration_s` (360) / `max_call_turns` (16); a pure `TerminationGuard` (`call/termination.py`, unit-tested) wired into `run_call_pipeline` as a duration watchdog + a per-callee-turn counter that force-speaks the wrap-up and hangs up via a single-shot `try_fire()` gate. The eval harness path is unaffected (`on_callee_turn` defaults `None`; text edges emit no `UserStoppedSpeakingFrame`).
  - **Eval**: new `restaurant/booking_third_party` case (booking name Victoria ≠ profile name Nikita) and a `require_end_call` flag on `EvalCase` enforced in `score_success`.
- **Rationale:** The booking name is task data, not owner identity; conflating the two is the root cause of the wrong-name bug, and a structured channel makes it testable. The LLM cannot be relied on to call `end_call` (live: voluntary rate ~2–3/5 on haiku), so a deterministic in-call backstop is required to guarantee no run hangs `running`.
- **Consequences:**
  - Shipped on branch `feature/call-data-and-termination` (10 impl commits, subagent-driven with per-task spec+quality review; 150 tests pass, ruff clean, `uv lock --check` ok). **Live-validated:** `restaurant/booking_third_party` ×3 — the agent states **Victoria** (never Nikita), policy/role/success all pass.
  - **Voluntary `end_call` is still unreliable on haiku** (live `--runs 5`: info_gathering 2/5, doctor/booking_basic 3/5, doctor/role_drift_probe 5/5). The prompt nudge helped but did not solve it; production termination is now guaranteed by the backstop, which the harness cannot exercise (so the flagship case deliberately does NOT set `require_end_call`). This keeps `end_call`-rate / model-floor reassessment open (feeds D-11).
  - **Out of scope, recorded in risks:** role drift at the data/wrap-up stage (live: agent asked the callee "¿cuántas personas?" in 1/3 flagship runs and addressed the receptionist's "birthday" in the original call — the few-shot covers names, not other missing data); result over-claim ("la reserva está confirmada" when nothing was booked); STT mishearing ("Pizza Parking" → "Pisopaylink"); word-by-word transcript segmentation with synthetic `ts_ms`.

## D-15 - Audit: stop symptom-patching; flow-based dialog, raise the model floor, audio-aware evals, invest in the compliance moat

- **Date:** 2026-06-14
- **Status:** Accepted (direction; concrete execution via brainstorming → spec → plan, like D-12)
- **Context:** A whole-project audit read the code end-to-end (`agent.py`, `tools.py`, `pipeline.py`, policy `engine.py`, eval `scoring.py`/`runner.py`/`simulator.py`, `normalize.py`, the five rule files, `summary.py`/`state.py`/`termination.py`) and cross-checked external best practice with sources. The first real call (D-14) and the eval findings (D-13) were being treated as a series of independent bugs, each fixed by adding a rule to the single system prompt or another code patch. The audit concluded the "bad behaviour" (wrong booking name, role drift, result over-claim, `end_call` omission, STT mishear) is **not N independent bugs** but the output of two compounding root causes — and that the fix *method* itself (append STRICT RULE #N to `_POLICY_PREAMBLE`, add a few-shot) is the anti-pattern.
- **Root causes:**
  1. **Conversation LLM below the reliability floor.** Haiku-tier underperforms on multi-turn tool-using voice. External benchmarks (Daily.co voice-agent benchmark: prod standardises near GPT-4.1 ~95% / Gemini 2.5 Flash; tool-calling benchmarks: <70% tool-call success = unfit) match our live symptoms (`end_call` 2-5/5, over-claim, role drift). D-11's "haiku holds role 3/3" was **false confidence**: that A/B was a single tool-free isolated turn; the full multi-turn tool-enabled call regressed.
  2. **Monolithic single-prompt architecture.** One system prompt (`build_system_prompt`, `agent.py:172`) + all tools available every turn + behaviour encoded as growing text rules (`_POLICY_PREAMBLE` now 7 rules). This is "context rot / context pollution": more instructions → worse following, task confusion, role exit. Patching each symptom with another rule worsens it.
  - **Meta-issue:** the eval harness is text-edge only, so it structurally cannot catch what actually broke the real call (STT mishear, real-telephony timing, the termination backstop — which the harness does not even invoke). It is a good inner loop mistaken for a safety net.
- **Decision (direction):**
  - Treat symptom-by-symptom prompt-patching of a monolithic agent as an anti-pattern; stop adding per-symptom rules.
  - **Architecture:** migrate the dialog to a flow / state-machine model (**Pipecat Flows** — the same stack as D-5): per-node scoped sub-prompt + only the tools valid in that node, so role drift / wrong data / over-claim become structurally impossible and each node is easy enough for a cheaper model.
  - **Model floor:** evaluate and likely move the dialog LLM off Haiku-tier to **Gemini 2.5 Flash / GPT-4.1** (config-only per D-5's swappable-LLM). Reopens D-11.
  - **Termination:** keep the deterministic backstop (industry-accepted: Vapi endCallPhrases / timeouts); add forced `tool_choice` in the terminal node so `end_call` is emitted, not "decided".
  - **Grounding:** result-claims ("confirmed") may only be emitted from a tool result, not free text.
  - **STT:** Deepgram **Nova-3 keyterm prompting**, injecting per-call proper nouns (`target_name`, `call_facts`).
  - **Evals:** keep the LLM-judge text harness as the fast inner loop; add an **audio-in-the-loop tier** (TTS→STT→agent) so STT mishears and the backstop are actually exercised.
  - **Strategy (D-7):** the moat is EU/Spain compliance-first (disclosure + approvals + audit), not the conversational plumbing the field has commoditised. Take the dialog layer from the framework; spend effort on the moat.
- **Sequencing:** P0 cheap/high-leverage (model A/B swap + Nova-3 keyterms + forced tool_choice) → P1 Flows re-platform → P2 audio eval tier + honest gaps (`fact_key` not passed in `tools.py`; conservative-refusal eval cases; prod/eval approval-timeout mismatch) → P3 moat + ops. Concrete execution begins with brainstorm → spec → plan.
- **Rationale:** P0 tests root cause #1 in an hour for cents; P1 removes a whole class of bugs structurally instead of one rule at a time; an audio-aware eval closes the blind spot that let the real call ship broken; focusing on the moat is what differentiates the product.
- **Consequences:**
  - D-11 (model floor) reopened; the haiku decision is no longer assumed.
  - `call_facts` (D-14) and the role few-shot become **interim** mechanisms; Flows nodes likely subsume them.
  - The Flows re-platform may warrant its own epic; decided during planning.
  - Keeps D-5 (Pipecat) — in fact leans into it (Flows is Pipecat). Refines D-12 (eval-driven, reliability-before-scale) with a concrete architecture + model direction.
  - Lesson recorded: an eval that is too easy (single-turn, tool-free) produces false confidence; evals must match the production difficulty surface.
- **Evidence (key sources):** Daily.co "Benchmarking LLMs for voice agent use cases" and "Why your voice agent needs structure (Pipecat Flows)"; Pipecat Flows docs; Vapi prompting guide + default-tools (identity lock, endCall/endCallPhrases); Anthropic "reduce hallucinations" + "writing tools for agents" (grounding, tool_choice); Deepgram Nova-3 keyterm prompting; voice-agent eval write-ups (Cekura / Maxim / FutureAGI).
