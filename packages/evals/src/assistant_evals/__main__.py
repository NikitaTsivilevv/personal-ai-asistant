"""CLI: uv run python -m assistant_evals run [--scenario X] [--case Y] [--runs N] ..."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from .case import load_cases
from .runner import CaseRunResult, EvalConfig, run_case


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="assistant_evals")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run eval cases against real models")
    run.add_argument("--cases-dir", type=Path, default=Path("packages/evals/cases"))
    run.add_argument("--scenario", help="only cases of this scenario")
    run.add_argument("--case", dest="case_name", help="only this case (scenario/name)")
    run.add_argument("--model", default="claude-haiku-4-5", help="agent model")
    run.add_argument("--sim-model", default="claude-haiku-4-5")
    run.add_argument("--judge-model", default="claude-sonnet-4-6")
    run.add_argument("--runs", type=int, default=3)
    run.add_argument("--max-cost", type=float, default=5.0,
                     help="abort sweep above this USD (sim+judge cost only; "
                          "agent tokens billed separately)")
    run.add_argument("--out", type=Path, default=Path("evals-results"))
    return parser.parse_args(argv)


def _print_summary(results: list[CaseRunResult]) -> None:
    print(f"\n{'case':40} {'policy':8} {'success':8} {'role':8} {'ttfb_ms':9} {'cost_usd':9}")
    for r in results:
        by = {a.axis: a for a in r.axes}
        flag = lambda a: "PASS" if by[a].passed else "FAIL"  # noqa: E731
        print(f"{r.case_name:40} {flag('policy'):8} {flag('success'):8} "
              f"{flag('role'):8} {by['latency'].score:9.0f} {by['cost'].score:9.4f}")
    total = sum(a.score for r in results for a in r.axes if a.axis == "cost")
    print(f"\ntotal sim+judge cost: ${total:.4f} (agent tokens billed separately)")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    if "LLM_API_KEY" not in os.environ:
        print("set LLM_API_KEY (and LLM_BASE_URL) to run evals against real models")
        return 2
    cases = load_cases(args.cases_dir)
    if args.scenario:
        cases = [c for c in cases if c.goal.scenario == args.scenario]
    if args.case_name:
        cases = [c for c in cases if c.name == args.case_name]
    if not cases:
        print("no cases matched")
        return 2
    cfg = EvalConfig(agent_model=args.model, sim_model=args.sim_model,
                     judge_model=args.judge_model, out_dir=args.out)
    results: list[CaseRunResult] = []
    spent = 0.0
    for case in cases:
        for i in range(args.runs):
            result = asyncio.run(run_case(case, cfg, run_index=i))
            results.append(result)
            spent += next(a.score for a in result.axes if a.axis == "cost")
            if spent > args.max_cost:
                print(f"max-cost ${args.max_cost} exceeded (${spent:.2f}); aborting sweep")
                _print_summary(results)
                return 1
    _print_summary(results)
    return 0 if all(r.policy_passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
