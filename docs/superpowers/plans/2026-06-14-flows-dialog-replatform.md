# Flows Dialog Re-platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pick the dialog LLM on evidence (Phase 0), then re-platform the call dialog from a monolithic single-prompt agent onto a Pipecat Flows graph so termination and over-claim become structural and role-drift/wrong-data shrink to a small focused prompt.

**Architecture:** A `FlowManager` orchestrates a 3-node graph (conversation → confirm_result → wrap_up) on top of the existing, unchanged audio pipeline. Per-node `NodeConfig` scopes prompt + tools; `FlowsFunctionSchema` handlers wrap the existing `CallToolbox` (policy engine untouched). The Flows path lives behind a `dialog_engine` flag inside `build_call_pipeline`, so production and the eval harness share one core and the monolith stays available until the Flows path passes an eval gate.

**Tech Stack:** Python 3.12, uv workspace, pytest, pipecat-ai 1.3, `pipecat-flows`, OpenAI-compat LLM clients (`OpenAILLMService`, `OpenAICompatChat`), Deepgram/Cartesia/Twilio (audio path untouched).

**Spec:** `docs/superpowers/specs/2026-06-14-flows-dialog-replatform-design.md` (D-15).

**Branch:** continue on `feature/d15-flows-replatform` (already created).

---

## Phase 0 — Model decision (do first; gates P1's model)

### Task P0.1: Add price rows for candidate models

**Files:**
- Modify: `packages/evals/src/assistant_evals/llm_client.py:16` (`PRICES_PER_MTOK`)
- Test: `tests/test_eval_llm_client.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_eval_llm_client.py`:

```python
from assistant_evals.llm_client import cost_usd


def test_cost_known_for_candidate_models():
    # Non-zero cost means the model has a price row (no $0 fallback warning path).
    assert cost_usd("gemini-2.5-flash", input_tokens=1_000_000, output_tokens=0) > 0
    assert cost_usd("gpt-4.1", input_tokens=0, output_tokens=1_000_000) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_eval_llm_client.py::test_cost_known_for_candidate_models -v`
Expected: FAIL (both return 0.0; the $0-fallback branch is taken).

- [ ] **Step 3: Add the price rows**

In `llm_client.py`, extend `PRICES_PER_MTOK` (values are 2026-01 list-price estimates — confirm against the Google AI / OpenAI pricing pages before committing; provider drift is a tracked risk):

```python
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "gemini-2.5-flash": (0.30, 2.50),
    "gpt-4.1": (2.00, 8.00),
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_eval_llm_client.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/evals/src/assistant_evals/llm_client.py tests/test_eval_llm_client.py
git commit -m "feat(evals): price rows for gemini-2.5-flash and gpt-4.1"
```

---

### Task P0.2: Per-role LLM endpoints (agent vs sim/judge)

**Why:** `runner.py:99-102` (agent `OpenAILLMService`) and `llm_client.py:46-47` (sim/judge `OpenAICompatChat`) all read the single `LLM_API_KEY`/`LLM_BASE_URL`. A fair A/B needs the agent on a candidate endpoint while sim+judge stay fixed (constant judge = comparable scores).

**Files:**
- Modify: `packages/evals/src/assistant_evals/runner.py` (`EvalConfig`, `_LivePipeline.__init__`)
- Modify: `packages/evals/src/assistant_evals/__main__.py` (CLI flags)
- Test: `tests/test_eval_runner.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_eval_runner.py`:

```python
from assistant_evals.runner import EvalConfig


def test_evalconfig_per_role_endpoints_default_to_env(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_BASE_URL", "https://aux.example/v1/")
    cfg = EvalConfig(agent_base_url="https://agent.example/v1/", agent_api_key="ak")
    # Agent uses its own endpoint; sim/judge fall back to env.
    assert cfg.agent_base_url == "https://agent.example/v1/"
    assert cfg.agent_api_key == "ak"
    assert cfg.aux_base_url == "https://aux.example/v1/"
    assert cfg.aux_api_key == "k"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_eval_runner.py::test_evalconfig_per_role_endpoints_default_to_env -v`
Expected: FAIL (`EvalConfig` has no `agent_base_url`).

- [ ] **Step 3: Add per-role endpoints to `EvalConfig`**

In `runner.py`, extend `EvalConfig` (add fields + resolved properties; keep `sim_chat`/`judge_chat` but point them at the aux endpoint):

```python
@dataclass
class EvalConfig:
    agent_model: str = "claude-haiku-4-5"
    sim_model: str = "claude-haiku-4-5"
    judge_model: str = "claude-sonnet-4-6"
    approval_timeout_s: int = 3
    out_dir: Path = Path("evals-results")
    # Per-role endpoints. Agent may live on a candidate provider while sim/judge
    # stay fixed for comparable scoring. All default to the shared LLM_* env.
    agent_base_url: str | None = None
    agent_api_key: str | None = None
    aux_base_url: str | None = None
    aux_api_key: str | None = None
    sim_chat_factory: "Callable | None" = None
    judge_chat_factory: "Callable | None" = None

    def __post_init__(self) -> None:
        env_base = os.environ.get("LLM_BASE_URL") or None
        env_key = os.environ.get("LLM_API_KEY")
        self.agent_base_url = self.agent_base_url or env_base
        self.agent_api_key = self.agent_api_key or env_key
        self.aux_base_url = self.aux_base_url or env_base
        self.aux_api_key = self.aux_api_key or env_key

    def sim_chat(self):
        return (self.sim_chat_factory
                or (lambda: OpenAICompatChat(self.sim_model,
                    api_key=self.aux_api_key, base_url=self.aux_base_url)))()

    def judge_chat(self):
        return (self.judge_chat_factory
                or (lambda: OpenAICompatChat(self.judge_model,
                    api_key=self.aux_api_key, base_url=self.aux_base_url)))()
```

- [ ] **Step 4: Point the agent LLM at the agent endpoint**

In `_LivePipeline.__init__`, replace the `OpenAILLMService(...)` construction (`runner.py:98-102`) with:

```python
        llm = OpenAILLMService(
            api_key=cfg.agent_api_key,
            model=cfg.agent_model,
            base_url=cfg.agent_base_url,
        )
```

- [ ] **Step 5: Add CLI flags**

In `__main__.py`, add to the `run` subparser (after `--judge-model`):

```python
    run.add_argument("--agent-base-url", default=None, help="agent LLM endpoint (default: LLM_BASE_URL)")
    run.add_argument("--agent-api-key", default=None, help="agent LLM key (default: LLM_API_KEY)")
    run.add_argument("--aux-base-url", default=None, help="sim/judge endpoint (default: LLM_BASE_URL)")
    run.add_argument("--aux-api-key", default=None, help="sim/judge key (default: LLM_API_KEY)")
```

And thread them into `EvalConfig(...)` in `main()`:

```python
    cfg = EvalConfig(agent_model=args.model, sim_model=args.sim_model,
                     judge_model=args.judge_model, out_dir=args.out,
                     agent_base_url=args.agent_base_url, agent_api_key=args.agent_api_key,
                     aux_base_url=args.aux_base_url, aux_api_key=args.aux_api_key)
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_eval_runner.py -v`
Expected: PASS. Then `uv run ruff check packages/evals`.

- [ ] **Step 7: Commit**

```bash
git add packages/evals/src/assistant_evals/runner.py packages/evals/src/assistant_evals/__main__.py tests/test_eval_runner.py
git commit -m "feat(evals): per-role LLM endpoints for cross-provider A/B"
```

---

### Task P0.3: Run the model A/B and record the decision

**Files:**
- Modify: `DECISIONS.md` (update D-11 with the result table)

This task runs the experiment; no code. Requires real keys for each provider in `.env` (not committed).

- [ ] **Step 1: Run the suite per candidate (sim/judge fixed on Anthropic)**

```bash
# Baseline (all on Anthropic OpenAI-compat, current default)
uv run python -m assistant_evals run --runs 5 --model claude-haiku-4-5 --out evals-results/p0-haiku

# Gemini agent, sim/judge fixed on Anthropic
uv run python -m assistant_evals run --runs 5 --model gemini-2.5-flash \
  --agent-base-url https://generativelanguage.googleapis.com/v1beta/openai/ --agent-api-key "$GEMINI_API_KEY" \
  --aux-base-url https://api.anthropic.com/v1/ --aux-api-key "$ANTHROPIC_API_KEY" \
  --out evals-results/p0-gemini

# GPT-4.1 agent (native OpenAI), sim/judge fixed on Anthropic
uv run python -m assistant_evals run --runs 5 --model gpt-4.1 \
  --agent-base-url "" --agent-api-key "$OPENAI_API_KEY" \
  --aux-base-url https://api.anthropic.com/v1/ --aux-api-key "$ANTHROPIC_API_KEY" \
  --out evals-results/p0-gpt41
```

Expected: three result dirs of JSON artifacts; the CLI prints a per-case PASS/FAIL table per run.

- [ ] **Step 2: Aggregate per-axis pass rates**

For each candidate, compute across 7 cases × 5 runs: policy %, role %, success %, voluntary `end_call` rate (count artifacts where `end_outcome` is non-null), avg TTFB. (Read the JSON artifacts; `end_outcome` and `axes` are in each file.)

- [ ] **Step 3: Apply the decision rule and record**

Pick the cheapest candidate that clearly beats haiku on policy+role+success+`end_call` without a TTFB regression breaking the ~1.5 s voice budget. Append the result to D-11 in `DECISIONS.md` (follow-up dated 2026-06-14): the comparison table + the chosen model + one-line rationale. Set that model as the worker default in `.env` (`LLM_MODEL`, `LLM_BASE_URL`) — `.env` is not committed.

- [ ] **Step 4: Commit the decision record**

```bash
git add DECISIONS.md
git commit -m "docs(D-11): model A/B result; dialog model = <winner>"
```

---

## Spike — gate before P1 build

### Task S1: pipecat-flows compatibility spike

**Goal:** confirm `pipecat-flows` works with the installed `pipecat 1.3`, `OpenAILLMService`, our custom processors, and the text-edge harness — and pin the exact API calls the P1 tasks depend on. **This is investigation, not TDD.**

**Files:**
- Create (throwaway): `scripts/spike_flows.py`
- Modify: `apps/voice-worker/pyproject.toml` (add `pipecat-flows` to the `call` extra)

- [ ] **Step 1: Add the dependency and resolve**

Add `pipecat-flows` to the `call` optional-dependency group in `apps/voice-worker/pyproject.toml`, then:

Run: `uv sync --extra call` (from repo root)
Expected: resolves without a `pipecat` version conflict. If it pins a different `pipecat`, record the exact versions.

- [ ] **Step 2: Smoke-test a 2-node static flow over text edges**

Write `scripts/spike_flows.py` that builds a minimal `FlowManager(task, llm, context_aggregator)` with a `NodeConfig` whose only function transitions to a terminal node with `post_actions=[{"type": "end_conversation"}]`, driven via the eval `text_edges` helpers (`AssistantOutputCapture`, `inject_callee_turn`) — i.e. NO Twilio. Reuse `eval_user_params()` from `assistant_evals.text_edges`.

Run: `LLM_API_KEY=... uv run python scripts/spike_flows.py`
Expected: the agent speaks, a callee text injection drives a transition, and `end_conversation` terminates the run cleanly.

- [ ] **Step 3: Answer the gate questions (write findings into the spec's §6)**

Confirm and record exact signatures/behaviour for:
1. `FlowManager(...)` constructor params actually available in the installed version.
2. `flow_manager.initialize(node)` and how to start it without a transport `on_client_connected` (eval path).
3. How to inject a live system message mid-flow (whisper) — exact call.
4. Whether `_CallObserver`, `PauseGate`, `InboundAudioProbe` coexist with the FlowManager on the same pipeline.
5. `end_conversation` behaviour over text edges (does it terminate the `PipelineRunner` like `EndFrame`?).

- [ ] **Step 4: Decision gate**

If compatible → proceed to P1 as written. If not → STOP and re-plan P1 around the hand-rolled fallback (manual per-state message/tool switching over `CallStateMachine`); the node graph and handlers (Tasks 2-3) are reusable either way.

- [ ] **Step 5: Commit the dependency + delete the throwaway**

```bash
rm scripts/spike_flows.py
git add apps/voice-worker/pyproject.toml uv.lock
git commit -m "build: add pipecat-flows to the call extra (spike passed)"
```

---

## P1 — Flows re-platform

### Task 1: `dialog_engine` settings flag

**Files:**
- Modify: `apps/voice-worker/src/assistant_worker/settings.py:8` (add field)
- Test: `tests/test_turn_config.py` (settings already exercised there) or add to an existing worker settings test

- [ ] **Step 1: Write the failing test**

Add to `tests/test_turn_config.py`:

```python
from assistant_worker.settings import WorkerSettings


def test_dialog_engine_defaults_to_monolith():
    s = WorkerSettings(_env_file=None)
    assert s.dialog_engine == "monolith"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_turn_config.py::test_dialog_engine_defaults_to_monolith -v`
Expected: FAIL (no such attribute).

- [ ] **Step 3: Add the field**

In `settings.py`, after `worker_mode`:

```python
    # Dialog engine: "monolith" = single-prompt agent (legacy), "flows" = Pipecat Flows graph.
    dialog_engine: str = "monolith"
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_turn_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/voice-worker/src/assistant_worker/settings.py tests/test_turn_config.py
git commit -m "feat(worker): dialog_engine flag (monolith|flows)"
```

---

### Task 2: Flows node builders

**Files:**
- Create: `apps/voice-worker/src/assistant_worker/call/flows/__init__.py` (empty)
- Create: `apps/voice-worker/src/assistant_worker/call/flows/nodes.py`
- Test: `tests/test_flows_nodes.py`

The builders decompose `agent.py:build_system_prompt`. Reuse `_LANGUAGE_NAMES`, `call_facts` rendering, and the role-lock wording from `agent.py`. Functions are passed in (built in Task 3) so nodes.py stays free of handler logic.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_flows_nodes.py`:

```python
from assistant_worker.call.agent import AgentConfig
from assistant_worker.call.flows.nodes import (
    build_conversation_node, build_confirm_node, build_wrapup_node, shared_role_message,
)
from assistant_shared.schemas import StructuredGoal


def _cfg():
    goal = StructuredGoal(
        objective="Confirm a booking",
        constraints=["after 17:00"],
        scenario="restaurant",
        call_facts={"имя брони": "Victoria"},
    )
    return AgentConfig(goal=goal, language="es", target_name="Pizza Parking")


def test_shared_role_message_locks_caller_role():
    msg = shared_role_message("es")
    assert "CALLER" in msg
    assert "never ask" in msg.lower()


def test_conversation_node_renders_call_facts_and_objective():
    node = build_conversation_node(_cfg(), functions=[])
    text = " ".join(m["content"] for m in node["task_messages"])
    assert "Victoria" in text          # call_facts present in N1
    assert "Confirm a booking" in text  # objective present
    assert node.get("respond_immediately") is True


def test_confirm_node_mentions_no_overstating():
    node = build_confirm_node(_cfg(), outcome="achieved", functions=[])
    text = " ".join(m["content"] for m in node["task_messages"]).lower()
    assert "achieved" in text
    assert "not overstate" in text or "only what was actually agreed" in text


def test_wrapup_node_ends_conversation():
    node = build_wrapup_node(_cfg())
    assert any(a.get("type") == "end_conversation" for a in node.get("post_actions", []))
    assert not node.get("functions")
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_flows_nodes.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement `nodes.py`**

```python
"""Pipecat Flows NodeConfig builders. Decomposes agent.build_system_prompt into
scoped per-node prompts. Functions are injected by the caller (call/flows/functions.py)."""
from __future__ import annotations

from pipecat_flows import NodeConfig

from ..agent import AgentConfig, _LANGUAGE_NAMES, allowed_facts

_ROLE_LOCK = {
    "es": ("Eres un asistente de IA llamando por teléfono en nombre de tu cliente. "
           "YA has dicho que eres una IA. Eres el QUE LLAMA (CALLER); quien contesta es "
           "personal del establecimiento, NO tu cliente: nunca actúes como su personal y "
           "nunca le pidas los datos de tu propio cliente. Habla solo en español, frases breves."),
    "en": ("You are an AI assistant on a phone call for your client. You have ALREADY said "
           "you are an AI. You are the CALLER; the person answering is the callee's staff, not "
           "your client - never act as their staff, never ask them for your client's own data. "
           "Speak only English, short phone sentences."),
    "ru": ("Ты ИИ-ассистент, звонящий по телефону от имени клиента. Ты УЖЕ сказал, что ты ИИ. "
           "Ты — ЗВОНЯЩИЙ (CALLER); тот, кто ответил, — сотрудник заведения, НЕ твой клиент: "
           "никогда не действуй как их персонал и не спрашивай у них данные своего клиента. "
           "Говори только по-русски, короткими фразами."),
}


def shared_role_message(language: str) -> str:
    return _ROLE_LOCK.get(language, _ROLE_LOCK["en"])


def _details_block(cfg: AgentConfig) -> str:
    cf = cfg.goal.call_facts
    if not cf:
        return ""
    rendered = "\n".join(
        f"- {k.replace(chr(10), ' ').strip()}: {v.replace(chr(10), ' ').strip()}"
        for k, v in cf.items()
    )
    return "\nDETAILS FOR THIS CALL (state these as needed; data for this specific call):\n" + rendered


def _facts_block(cfg: AgentConfig) -> str:
    facts = allowed_facts(cfg)
    if not facts:
        return "\nALLOWED FACTS:\n- (none)"
    lines = []
    for f in facts:
        if f.sensitivity == "high":
            lines.append(f"- {f.key}: {f.value} [SENSITIVE: request_approval before disclosure]")
        else:
            lines.append(f"- {f.key}: {f.value}")
    return "\nALLOWED FACTS:\n" + "\n".join(lines)


def build_conversation_node(cfg: AgentConfig, *, functions: list) -> NodeConfig:
    goal = cfg.goal
    constraints = "\n".join(f"- {c}" for c in goal.constraints) or "- (none)"
    who = ""
    if cfg.target_name:
        who = (f"\nWHO YOU ARE CALLING: {cfg.target_name}. They are NOT your client; "
               f"never introduce yourself as calling from {cfg.target_name}.")
    task = (f"OBJECTIVE:\n{goal.objective}{who}{_details_block(cfg)}"
            f"\nCONSTRAINTS:\n{constraints}{_facts_block(cfg)}"
            f"\nAUTONOMY LEVEL: {goal.autonomy_level}/3"
            "\nWhen the objective is resolved (or clearly cannot be), call record_outcome.")
    return NodeConfig(
        name="conversation",
        role_message=shared_role_message(cfg.language),
        task_messages=[{"role": "developer", "content": task}],
        functions=functions,
        respond_immediately=True,
    )


def build_confirm_node(cfg: AgentConfig, *, outcome: str, functions: list) -> NodeConfig:
    task = (f"The outcome is recorded as: {outcome}. State to the callee only what was "
            "actually agreed (from the facts logged during the call) - do not overstate or "
            "claim anything that was not confirmed. Then call end_call to finish.")
    return NodeConfig(
        name="confirm_result",
        role_message=shared_role_message(cfg.language),
        task_messages=[{"role": "developer", "content": task}],
        functions=functions,
    )


def build_wrapup_node(cfg: AgentConfig) -> NodeConfig:
    return NodeConfig(
        name="wrap_up",
        role_message=shared_role_message(cfg.language),
        task_messages=[{"role": "developer", "content": "Say a brief, accurate goodbye."}],
        post_actions=[{"type": "end_conversation"}],
    )
```

NOTE: `NodeConfig` accepts dict-style access in tests because it is a `TypedDict`/dataclass in `pipecat-flows`; if S1 finds it is a pydantic model, change the test accessors to attributes (`node.task_messages`) — pin this in S1.

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/test_flows_nodes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/voice-worker/src/assistant_worker/call/flows/ tests/test_flows_nodes.py
git commit -m "feat(worker): Flows node builders (conversation/confirm/wrap_up)"
```

---

### Task 3: Flows function handlers (transitions + CallToolbox wrappers)

**Files:**
- Create: `apps/voice-worker/src/assistant_worker/call/flows/functions.py`
- Test: `tests/test_flows_functions.py`

Handlers return `(result, next_node)`. `record_outcome` → confirm node; `end_call` → wrap_up node; `request_approval` delegates to `CallToolbox.request_approval` and stays (returns `(result, None)`); `log_fact` stays.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_flows_functions.py`:

```python
import pytest

from assistant_worker.call.agent import AgentConfig
from assistant_worker.call.flows.functions import build_flow_functions
from assistant_shared.schemas import StructuredGoal


class _ToolboxStub:
    def __init__(self):
        self.end_outcome = None
        self.logged = []
    async def end_call(self, outcome):
        self.end_outcome = outcome
        return {"status": "ok"}
    async def log_fact(self, fact):
        self.logged.append(fact)
        return {"status": "ok"}
    async def request_approval(self, action, detail):
        return {"status": "approved"}


def _cfg():
    return AgentConfig(goal=StructuredGoal(objective="x", scenario="restaurant"), language="es")


@pytest.mark.asyncio
async def test_record_outcome_transitions_to_confirm():
    tb = _ToolboxStub()
    fns = {f.name: f for f in build_flow_functions(_cfg(), tb)}
    result, next_node = await fns["record_outcome"].handler(
        {"outcome": "achieved", "what_was_agreed": "table at 19:30"}, None)
    assert result["status"] == "ok"
    assert next_node["name"] == "confirm_result"


@pytest.mark.asyncio
async def test_end_call_transitions_to_wrapup_and_records_outcome():
    tb = _ToolboxStub()
    fns = {f.name: f for f in build_flow_functions(_cfg(), tb)}
    result, next_node = await fns["end_call"].handler({"outcome": "not_achieved"}, None)
    assert tb.end_outcome == "not_achieved"
    assert next_node["name"] == "wrap_up"


@pytest.mark.asyncio
async def test_request_approval_stays_in_node():
    tb = _ToolboxStub()
    fns = {f.name: f for f in build_flow_functions(_cfg(), tb)}
    result, next_node = await fns["request_approval"].handler(
        {"action": "book_appointment", "detail": "book table"}, None)
    assert result["status"] == "approved"
    assert next_node is None  # approval does not change node
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_flows_functions.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement `functions.py`**

```python
"""Pipecat Flows function handlers. Thin wrappers over the existing CallToolbox so the
policy engine and approval flow are reused unchanged; only transitions are added here."""
from __future__ import annotations

from pipecat_flows import FlowsFunctionSchema

from ..agent import AgentConfig
from .nodes import build_confirm_node, build_wrapup_node


def build_flow_functions(cfg: AgentConfig, toolbox) -> list[FlowsFunctionSchema]:
    async def record_outcome(args, flow_manager):
        flow_manager and flow_manager.state.__setitem__("outcome", args["outcome"])
        await toolbox.log_fact(f"outcome={args['outcome']}: {args.get('what_was_agreed','')}")
        return {"status": "ok"}, build_confirm_node(cfg, outcome=args["outcome"],
                                                     functions=_confirm_functions(cfg, toolbox))

    async def end_call(args, flow_manager):
        await toolbox.end_call(args["outcome"])
        return {"status": "ok"}, build_wrapup_node(cfg)

    async def log_fact(args, flow_manager):
        return await toolbox.log_fact(args["fact"]), None

    async def request_approval(args, flow_manager):
        return await toolbox.request_approval(args["action"], args["detail"]), None

    return [
        FlowsFunctionSchema(
            name="record_outcome",
            description="Record the call result once the objective is resolved or clearly cannot be.",
            properties={"outcome": {"type": "string",
                        "enum": ["achieved", "partially_achieved", "not_achieved", "callee_refused"]},
                        "what_was_agreed": {"type": "string"}},
            required=["outcome"], handler=record_outcome, cancel_on_interruption=False),
        FlowsFunctionSchema(
            name="request_approval",
            description="Ask the client before a payment, cancellation, contract change, or sharing personal data.",
            properties={"action": {"type": "string"}, "detail": {"type": "string"}},
            required=["action", "detail"], handler=request_approval, cancel_on_interruption=False),
        FlowsFunctionSchema(
            name="log_fact",
            description="Record an important fact learned during the call.",
            properties={"fact": {"type": "string"}}, required=["fact"],
            handler=log_fact, cancel_on_interruption=False),
        FlowsFunctionSchema(
            name="end_call",
            description="End the call politely after goodbye, or if the callee asks to stop.",
            properties={"outcome": {"type": "string",
                        "enum": ["achieved", "partially_achieved", "not_achieved", "callee_refused"]}},
            required=["outcome"], handler=end_call, cancel_on_interruption=False),
    ]


def _confirm_functions(cfg: AgentConfig, toolbox) -> list[FlowsFunctionSchema]:
    # In confirm_result only log_fact + end_call are valid (no new gated actions).
    return [f for f in build_flow_functions(cfg, toolbox) if f.name in ("log_fact", "end_call")]
```

NOTE: the `request_approval` action enum mirrors `tools._ACTION_MAP` keys; keep them in sync. If S1 shows `FlowsFunctionSchema.handler` receives `(args, flow_manager)` positionally vs kwargs, adjust the stub call in the test accordingly (pin in S1).

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/test_flows_functions.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/voice-worker/src/assistant_worker/call/flows/functions.py tests/test_flows_functions.py
git commit -m "feat(worker): Flows function handlers with tool-driven transitions"
```

---

### Task 4: Wire the Flows path into `build_call_pipeline`

**Files:**
- Modify: `apps/voice-worker/src/assistant_worker/call/pipeline.py` (`build_call_pipeline`)
- Test: `tests/test_pipeline_builder.py`

Add an optional `dialog_engine: str = "monolith"` parameter. When `"flows"`, build a `FlowManager` over the same `task`/`llm`/aggregator instead of registering the static tools + static system prompt; expose `flow_manager` on `CallPipelineHandles` and an `init_flow()` coroutine the caller invokes after disclosure.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pipeline_builder.py`:

```python
def test_build_call_pipeline_flows_mode_exposes_flow_init():
    # Construct config/llm/sm/metrics/make_toolbox exactly as the existing monolith
    # test in this file does (copy that arrangement verbatim), then:
    handles = build_call_pipeline(
        config=config, run_client=run_client, llm=llm, sm=sm, metrics=metrics,
        make_toolbox=make_toolbox, pre_llm=[], post_llm=[], user_params=eval_user_params(),
        dialog_engine="flows",
    )
    assert handles.flow_manager is not None
    assert callable(handles.init_flow)
```

(Match the existing setup in `test_pipeline_builder.py`; it already constructs these parts for the monolith case — copy that arrangement.)

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_pipeline_builder.py::test_build_call_pipeline_flows_mode_exposes_flow_init -v`
Expected: FAIL (`dialog_engine` kwarg unknown / no `flow_manager`).

- [ ] **Step 3: Implement the Flows branch**

In `pipeline.py`: add `flow_manager` and `init_flow` to the `CallPipelineHandles` dataclass (both `Optional`, default `None`). Add `dialog_engine: str = "monolith"` to `build_call_pipeline`. Keep the existing monolith branch (context with `build_system_prompt` + `_tool_schemas` + `_register`). Add:

```python
    if dialog_engine == "flows":
        from pipecat_flows import FlowManager
        from .flows.functions import build_flow_functions
        from .flows.nodes import build_conversation_node

        context = LLMContext()  # Flows manages messages; start empty
        user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
            context, user_params=user_params or LLMUserAggregatorParams())
        pause_gate = PauseGate()
        pipeline = Pipeline([*pre_llm, pause_gate, user_aggregator, llm, *post_llm, assistant_aggregator])
        task = PipelineTask(pipeline, params=PipelineParams(enable_metrics=True))

        async def speak(text: str) -> None:
            await task.queue_frame(TTSSpeakFrame(text))

        async def hangup_call() -> None:
            _safe_transition(sm, CallState.wrapping_up)
            await task.queue_frame(EndFrame())

        toolbox = make_toolbox(speak, hangup_call)
        flow_manager = FlowManager(task=task, llm=llm, context_aggregator=(user_aggregator, assistant_aggregator))
        # exact context_aggregator argument shape is pinned by S1

        async def init_flow() -> None:
            functions = build_flow_functions(config, toolbox)
            await flow_manager.initialize(build_conversation_node(config, functions=functions))

        # Attach the SAME transcript/metrics observer and on_callee_turn wiring as the
        # monolith branch — extract that block into a local _make_call_observer() helper
        # (DRY) and call it identically here.
        return CallPipelineHandles(task=task, toolbox=toolbox, pause_gate=pause_gate,
                                   speak=speak, hangup=hangup_call, transcript_log=transcript_log,
                                   flow_manager=flow_manager, init_flow=init_flow)
```

Refactor the existing `_CallObserver` construction into a small local helper (`_make_call_observer`) so both branches share it (DRY). Keep `on_callee_turn` wiring identical.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_pipeline_builder.py -v`
Expected: PASS. Then `uv run pytest tests/test_call_tools.py tests/test_call_termination.py -v` (monolith path unchanged).

- [ ] **Step 5: Commit**

```bash
git add apps/voice-worker/src/assistant_worker/call/pipeline.py tests/test_pipeline_builder.py
git commit -m "feat(worker): Flows path in build_call_pipeline behind dialog_engine"
```

---

### Task 5: Drive the Flows path in production (`run_call_pipeline`)

**Files:**
- Modify: `apps/voice-worker/src/assistant_worker/call/pipeline.py` (`run_call_pipeline`)
- Modify: `apps/voice-worker/src/assistant_worker/call/runner.py` (pass `settings.dialog_engine`)
- Test: covered by `tests/test_worker_e2e.py` (extend if it asserts the dialog path)

- [ ] **Step 1: Pass the flag through**

In `run_call_pipeline`, pass `dialog_engine=settings.dialog_engine` into `build_call_pipeline`. After the hardcoded disclosure in `on_client_connected`, call `await handles.init_flow()` when `handles.init_flow is not None`:

```python
        await handles.speak(disclosure_text(config.language))
        if handles.init_flow is not None:
            await handles.init_flow()
        _safe_transition(sm, CallState.conversation)
```

Whisper handling: when `dialog_engine == "flows"`, inject the live instruction via the FlowManager context (exact call pinned by S1) instead of `LLMMessagesAppendFrame`; keep the `config.whispers.append(text)` line. Pause/hangup unchanged. `TerminationGuard` + watchdog unchanged.

- [ ] **Step 2: Verify the worker assembles in both modes**

Run: `uv run pytest tests/test_worker_e2e.py -v`
Expected: PASS (existing e2e uses `worker_mode="simulate"`, so this checks no import/wiring regressions). Then `uv run ruff check .`.

- [ ] **Step 3: Commit**

```bash
git add apps/voice-worker/src/assistant_worker/call/pipeline.py apps/voice-worker/src/assistant_worker/call/runner.py
git commit -m "feat(worker): run_call_pipeline drives Flows path; whisper via FlowManager"
```

---

### Task 6: Drive the Flows path in the eval harness

**Files:**
- Modify: `packages/evals/src/assistant_evals/runner.py` (`EvalConfig`, `_LivePipeline`)
- Test: `tests/test_eval_runner.py`

The harness must build the same Flows graph and call `init_flow()` after disclosure (no transport event there).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_eval_runner.py`:

```python
def test_evalconfig_carries_dialog_engine():
    assert EvalConfig().dialog_engine == "monolith"
    assert EvalConfig(dialog_engine="flows").dialog_engine == "flows"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_eval_runner.py::test_evalconfig_carries_dialog_engine -v`
Expected: FAIL.

- [ ] **Step 3: Thread `dialog_engine` through the harness**

Add `dialog_engine: str = "monolith"` to `EvalConfig`. In `_LivePipeline.__init__`, pass `dialog_engine=cfg.dialog_engine` to `build_call_pipeline`. In `_LivePipeline.start`, after `await self.handles.speak(disclosure_text(...))`, add:

```python
        if self.handles.init_flow is not None:
            await self.handles.init_flow()
```

Add a `--dialog-engine` CLI flag in `__main__.py` (default `monolith`) and thread it into `EvalConfig`.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_eval_runner.py tests/test_eval_text_edges.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/evals/src/assistant_evals/runner.py packages/evals/src/assistant_evals/__main__.py tests/test_eval_runner.py
git commit -m "feat(evals): drive Flows path via --dialog-engine"
```

---

### Task 7: Eval gate — Flows vs monolith on the 7 cases

**Files:**
- Modify: `packages/evals/cases/**/*.yaml` (re-enable `require_end_call` where structural termination now allows)
- Modify: `DECISIONS.md` (record the gate result; possibly flip the default)

- [ ] **Step 1: Run both engines on the chosen model**

```bash
uv run python -m assistant_evals run --runs 5 --model <winner> --dialog-engine monolith --out evals-results/gate-monolith
uv run python -m assistant_evals run --runs 5 --model <winner> --dialog-engine flows    --out evals-results/gate-flows
```

Expected: two result sets; compare per-axis pass rates.

- [ ] **Step 2: Assert the gate**

Flows must be **no worse** than monolith on policy/success/role and should improve `end_call` termination and over-claim. If `end_conversation` reliably terminates over text edges (confirmed in S1), set `require_end_call: true` on the booking/info cases and re-run to confirm they pass on Flows.

- [ ] **Step 3: Flip the default (only if the gate passes)**

Set `dialog_engine: str = "flows"` default in `settings.py`, update the eval default in `__main__.py`/`EvalConfig`, and add a D-15 follow-up entry in `DECISIONS.md` with the gate table. Keep the monolith code in place for one cycle (removal is a separate follow-up, out of this plan).

- [ ] **Step 4: Full suite + lint**

Run: `uv run pytest -q && uv run ruff check .`
Expected: all pass, ruff clean.

- [ ] **Step 5: Commit**

```bash
git add settings.py packages/evals tests DECISIONS.md
git commit -m "feat: default dialog_engine=flows after eval gate (D-15)"
```

---

## Self-review notes (coverage)

- Spec §3 Phase 0 → Tasks P0.1-P0.3. Spec §4.5 compat spike → Task S1. §4.1 integration → Tasks 4-5. §4.2 node graph → Tasks 2-3. §4.4 control/state/backstop → Task 5. §4.5 eval → Tasks 6-7. §5 acceptance → Tasks P0.3 (model recorded), 7 (gate, structural termination, no-worse, tests/ruff).
- Out of scope here (per spec §2): P2 audio eval tier, P3 moat/ops, monolith removal — tracked separately.
- Spike-pinned specifics (NodeConfig access style, FlowManager `context_aggregator` arg shape, handler arg passing, whisper injection call, `end_conversation` over text edges) are explicitly flagged in Tasks 2/3/4/5 and resolved by S1 before those tasks run.
