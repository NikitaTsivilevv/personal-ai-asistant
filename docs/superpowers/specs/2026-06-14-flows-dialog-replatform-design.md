# Design — Flows dialog re-platform (+ Phase 0 model decision)

- **Date:** 2026-06-14
- **Status:** Design (approved in brainstorm; pending spec review → implementation plan)
- **Decision link:** D-15 (audit: stop symptom-patching; flow-based dialog, raise model floor)
- **Epic:** P1 likely becomes its own epic (`EPIC-008-flows-dialog`); Phase 0 references EPIC-002.

## 1. Context & problem

The first real call (D-14) and the eval findings (D-13) were being fixed symptom-by-symptom by appending rules to one monolithic system prompt. The D-15 audit reframed the "bad behaviour" (wrong booking name, role drift, result over-claim, `end_call` omission) as the output of two compounding root causes:

1. **Conversation LLM below the reliability floor** (haiku-tier) for multi-turn tool-using voice.
2. **Monolithic single-prompt architecture** — one system prompt (`agent.py:build_system_prompt`) + all tools every turn + behaviour as a growing 7-rule `_POLICY_PREAMBLE` → "context rot": more instructions degrade following.

Plus a meta-issue: the text-edge eval harness is blind to the audio/STT/termination-backstop surface that actually broke the real call.

This design covers the two highest-leverage workstreams: **Phase 0** (pick the dialog model) and **P1** (re-platform the dialog onto Pipecat Flows). P2 (audio eval tier) and P3 (compliance moat + ops) are out of scope here and tracked separately.

## 2. Goals / non-goals

**Goals**
- Pick the dialog LLM on evidence (Phase 0).
- Replace the monolithic prompt+tools with a scoped Pipecat Flows graph so that: termination and over-claim become structural; role drift and wrong-data shrink to a small focused prompt surface.
- Preserve the shared prod/eval pipeline core (D-13 measurement fidelity).
- Keep the policy engine, approvals, control plane, transcript/metrics, and termination backstop working unchanged or thinly wrapped.

**Non-goals**
- No per-scenario node graphs (one generic graph parameterised by scenario/facts; scenarios already differ via policy rules + facts).
- No change to the audio path (transport/STT/TTS/VAD/turn-taking).
- No absolute reliability SLO yet (Phase 0 uses a relative bar; SLO is set during/after P1).
- No audio eval tier here (that is P2).

## 3. Phase 0 — model decision (light protocol)

**Candidates:** `claude-haiku-4-5` (baseline) vs `gemini-2.5-flash` (OpenAI-compat endpoint) vs `gpt-4.1`.

**Method:** full eval suite, `--runs 5`, per candidate, with sim and judge held constant (`sim=claude-haiku-4-5`, `judge=claude-sonnet-4-6`) so the agent model is the only variable.

**Metrics (aggregated across 7 cases × 5 runs):** policy %, role %, success %, voluntary `end_call` rate, LLM TTFB, $/call.

**Decision rule (relative):** pick the **cheapest** candidate that clearly beats haiku on policy+role+success+`end_call` **without** a TTFB regression that breaks the voice budget (~<1.5 s). Tie-break toward cost (personal MVP).

**Code touches (small):**
- Add price rows to `PRICES_PER_MTOK` (`packages/evals/.../llm_client.py:16`, today only haiku/sonnet) for the new models.
- If agent and judge sit on different providers, support per-role `base_url`/`key` (CLI/env) in the harness.

**Output:** winner + comparison table recorded in `DECISIONS.md` (updates D-11) and referenced here.

**Note:** the chosen model is an input to P1 (node prompts and transition reliability assume it). Phase 0 runs first.

## 4. P1 — Flows architecture

### 4.1 Architecture & integration

Adopt `pipecat-flows`. A `FlowManager(task, llm, context_aggregator)` orchestrates per-node prompt+tools **on top of** the existing pipeline. The audio pipeline graph (`transport.input → stt → user_aggregator → llm → tts → transport.output → assistant_aggregator`) is **unchanged** — this is an additive layer.

**Replaced:**
- The static system prompt (`build_system_prompt`) + all-tools registration (`_tool_schemas` / `llm.register_function`) → `NodeConfig` builders + `FlowsFunctionSchema` functions.
- `build_system_prompt` is decomposed: invariants (AI-identity-already-disclosed, caller-role lock, language, brevity) → shared `role_message`; phase content (objective, `call_facts`, constraints, facts) → the relevant node's `task_messages`. The 7-rule `_POLICY_PREAMBLE` dissolves — most rules become structural (a tool is simply absent in nodes where it is invalid).

**Kept (unchanged or thinly wrapped):**
- `CallToolbox` handlers (`request_approval`+policy, `end_call`, `log_fact`, `propose_summary`) → wrapped as `FlowsFunctionSchema` handlers. **Policy engine untouched.**
- `ControlRouter`, `_CallObserver` (transcript + metrics), `PauseGate`, disclosure-first, `CallStateMachine`.
- `TerminationGuard` backstop — now a true safety net (node-loop / network drop / model loop).

**Shared prod/eval core:** the Flows wiring lives inside `build_call_pipeline` so the eval harness exercises the same graph. The harness initialises the `FlowManager` explicitly (no transport `on_client_connected`).

**Tool scoping:** `end_call` as a **global function** (callee can ask to stop in any node → rule 4); `request_approval` scoped to gated nodes; `log_fact` global.

### 4.2 Node graph

Reliable Flows transitions fire on **tool events**, not conversational nuance, so phases that lack a reliable LLM trigger are realised as tool-driven transitions / scoped behaviour rather than separate conversational nodes. Result: **3 conversational nodes**, all transitions tool-driven.

**Shared `role_message` (every node):**
> You are an AI assistant on a phone call for your client. You have ALREADY said you are an AI. You are the CALLER; the person answering is the callee's staff, not your client — never act as their staff, never ask them for your client's own data. Speak only {language}, short phone sentences.

| Node | Scope (`task_messages`) | Functions | Exits |
|---|---|---|---|
| **N1 conversation** (entry, `respond_immediately`) | Objective + constraints + facts + DETAILS FOR THIS CALL (`call_facts`). Opens, converses, answers, provides booking data from DETAILS. | `log_fact`, `request_approval`, `record_outcome`, `end_call` | `record_outcome`→N2; `end_call`→N3 |
| **N2 confirm_result** | "Outcome recorded as {outcome}. State to the callee only what was actually agreed (from logged facts) — do not overstate." | `log_fact`, `end_call` | `end_call`→N3 |
| **N3 wrap_up** (terminal) | Brief, accurate goodbye. | — | `post_action: end_conversation` |

`end_call` and `log_fact` are **global functions** (available in every node); the table lists them where they are most relevant. N3 is terminal, so it exposes no functions and ends via the action.

**Transitions (all tool-driven):**
- `request_approval` → handler runs the policy engine unchanged, waits if needed; returns status to the LLM, **stays in N1** (agent acts on approved/denied/expired conversationally).
- `record_outcome(outcome, what_was_agreed)` → captures result, → **N2**. The only path that unlocks success-claims.
- `end_call(outcome)` → records outcome, → **N3** (global).
- N3 → built-in **`end_conversation`** action terminates structurally.

### 4.3 How each named bug is addressed (honest)

| Bug | Fix | Strength |
|---|---|---|
| `end_call` omission / hung run | N3 `end_conversation` action | **Structural** (no LLM dependency) |
| Over-claim ("confirmed") | Success-claims allowed only in N2, reachable only via `record_outcome`; + existing eval over-claim guard | **Structural-ish** + guard |
| Wrong booking name | `call_facts` rendered in N1's focused prompt; role_message says state-it-never-ask | **Mitigated** (data present + tiny prompt) |
| Role drift | N1 prompt small & focused (context rot gone) + data present; late-call drift removed (N2/N3 separate scopes) | **Mitigated, not eliminated** — asking is free speech, cannot be tool-removed; P0 model upgrade is the complementary lever |
| STT mishear | P0 Nova-3 keyterms (separate workstream) | orthogonal |

We deliberately do not claim Flows "eliminates" role drift; it shrinks the surface, and the model upgrade covers the rest.

### 4.4 Control plane, errors, state, backstop

- **Whisper** → injected as a live system message into the current node context (exact `FlowManager`/aggregator call is a spike item). **Pause** → `PauseGate` unaffected. **Hangup** → ends the flow/pipeline (`EndFrame`).
- **Approvals/expiry** → `request_approval` handler unchanged: policy eval + wait on control list; `approved / denied (deny_phrase) / expired (expiry_wrapup) / cancelled`; 120 s timeout. On `expired`, agent wraps up → `end_call` → N3.
- **State machine (`CallState`)** kept, driven by node transitions: `disclosure` (pre-flow) → `conversation` (N1) → `waiting_approval` (during `request_approval`) → `wrapping_up` (N3) → `ended`. Final reconciliation at the end as today.
- **Termination backstop (`TerminationGuard`)** kept as safety net; fires only on stuck-in-node / drop / loop. Watchdog (duration) + per-callee-turn counter (`UserStoppedSpeakingFrame`) unchanged.
- **Disclosure** hardcoded TTS first, then `flow_manager.initialize(N1)`; eval initialises explicitly.
- **Summary** `end_call` sets `end_outcome`; `record_outcome` + `propose_summary` feed `summary.py` (transcript + logged_facts + proposed summary). Consolidation of `record_outcome`/`propose_summary` deferred (YAGNI).

### 4.5 Eval, tests, compat spike, migration

- **Eval harness** drives the same `build_call_pipeline` Flows graph; initialises `FlowManager` explicitly. Win: if the agent reaches N3, `end_conversation` fires in the text-edge harness too → **structural termination becomes offline-testable** (impossible in D-14). `require_end_call` can be re-enabled on more cases. The duration/turn backstop remains un-exercised by the harness (it is pure safety net).
- **Unit tests** (no LLM, deterministic): node builders (correct function scope per node); `FlowsFunctionSchema` handlers (`record_outcome`→N2, `end_call`→N3, all `request_approval` branches).
- **Eval gate:** the 7 existing cases on the Flows graph must score **no worse than** the monolith before switching the default; expect role / over-claim / `end_call` to improve.
- **Compat spike (first plan task):** verify `pipecat-flows` against installed `pipecat 1.3`, `OpenAILLMService`, custom processors (`PauseGate`, `InboundAudioProbe`, `_CallObserver`), and the text-edge harness. If incompatible → fallback: hand-rolled minimal node-scoping (manual message-set + tool-set switching over a small state machine).
- **Migration (no big bang):** Flows path behind the same `build_call_pipeline` interface; `dialog_engine: monolith|flows` settings flag during validation; monolith stays until Flows passes the eval gate; then switch default and remove the monolith.

### 4.6 Risks

1. `pipecat-flows` ↔ `pipecat 1.3` version compatibility — mitigated by the spike + hand-rolled fallback.
2. Transition reliability on a weak model — mitigated by tool-driven transitions + Phase 0 model choice.
3. Whisper/pause integration with Flows context — spike.
4. Eval over text edges + Flows — spike.
5. Latency: Flows adds context swaps on transitions — measure TTFB in eval.

## 5. Acceptance criteria

- **Phase 0:** a model is chosen by the relative rule and recorded in `DECISIONS.md` (D-11 update) with the comparison table.
- **P1:**
  - The dialog runs on a Pipecat Flows graph (N1/N2/N3) behind `build_call_pipeline`, selectable via the `dialog_engine` flag.
  - Policy engine, approvals (incl. expiry), whisper/pause/hangup, transcript/metrics, and the termination backstop all function on the Flows path.
  - Structural termination via `end_conversation`; the eval shows the agent terminating without relying on voluntary `end_call`.
  - The 7 eval cases score no worse than the monolith; role / over-claim / `end_call` measurably improve.
  - Unit tests cover node scoping and all transition handlers; `uv run pytest -q` and `uv run ruff check .` pass.

## 6. Open questions / spike items

- Exact `FlowManager` API for injecting a live whisper into the current node context.
- Whether `pipecat-flows` runs over the text-edge harness with the existing `LLMContextAggregatorPair` and `_CallObserver` (the #1 compat risk).
- Whether to consolidate `record_outcome` + `propose_summary` (deferred).
- Whether P1 becomes `EPIC-008` or extends EPIC-002 (decide at plan time).

## 7. References

- `DECISIONS.md` D-15 (audit/direction), D-11 (model floor), D-13 (eval harness), D-14 (`call_facts` + backstop).
- Code: `apps/voice-worker/.../call/{agent,pipeline,tools,termination,state}.py`; `packages/policy/.../engine.py`; `packages/evals/.../{runner,scoring,simulator,llm_client}.py`.
- `pipecat-flows` docs (Context7 `/pipecat-ai/pipecat-flows`): `NodeConfig`, `FlowsFunctionSchema`, `FlowManager`, built-in `end_conversation`/`tts_say` actions, `global_functions`, `flow_manager.state`.
- Best-practice sources (per D-15 Evidence): Daily.co voice-agent benchmark + Pipecat Flows "structure" post; Vapi prompting/default-tools; Anthropic grounding + tool design; Deepgram Nova-3 keyterms.
