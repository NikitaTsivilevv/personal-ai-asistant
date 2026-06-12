"""Eval case cards: one YAML per case, validated into pydantic models (spec Part 2)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from assistant_shared.schemas import StructuredGoal


class FactSpec(BaseModel):
    key: str
    value: str
    sensitivity: str = "medium"
    allowed_by_default: bool = False
    allowed_scenarios: list[str] = Field(default_factory=list)


class PolicyExpect(BaseModel):
    """Expected policy_decision event. rule_id is optional: match on action+outcome,
    and additionally on rule_id when set."""

    action: str  # PolicyActionType value, e.g. "disclose_fact"
    outcome: str  # "allow" | "deny" | "require_approval"
    rule_id: str | None = None


class ClientScriptItem(BaseModel):
    """Scripted client answer to the Nth approval request (in order)."""

    decision: Literal["approve", "reject", "expire"]


class EvalCase(BaseModel):
    name: str = ""  # filled by the loader: "<scenario_dir>/<file_stem>"
    goal: StructuredGoal
    facts: list[FactSpec] = Field(default_factory=list)
    persona: str
    language: str = "es"
    probes: list[str] = Field(default_factory=list)
    client_script: list[ClientScriptItem] = Field(default_factory=list)
    expected_policy: list[PolicyExpect] = Field(default_factory=list)
    expected_end_outcome: str | None = None  # end_call outcome enum value
    forbidden_markers: list[str] = Field(default_factory=list)  # role-drift asks etc.
    judge_criteria: str = ""  # extra instruction for the success judge
    max_turns: int = 12


def load_case(path: Path) -> EvalCase:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    case = EvalCase.model_validate(payload)
    case.name = f"{path.parent.name}/{path.stem}"
    return case


def load_cases(cases_dir: Path) -> list[EvalCase]:
    return [load_case(p) for p in sorted(cases_dir.glob("*/*.yaml"))]
