#!/usr/bin/env python3
"""Unified CLI for the eval runner suite.

Usage:
    python -m scripts.eval_runner.cli trigger --skill assess-criticality --mode fast
    python -m scripts.eval_runner.cli trigger --all --mode fast
    python -m scripts.eval_runner.cli functional --skill assess-criticality
    python -m scripts.eval_runner.cli benchmark --skill assess-criticality --mode ab
    python -m scripts.eval_runner.cli snapshot --skill assess-criticality
    python -m scripts.eval_runner.cli regression --skill assess-criticality
    python -m scripts.eval_runner.cli report --type trigger --all --output report.md
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from scripts.eval_runner.models import EvalMode
from scripts.eval_runner.trigger_eval import (
    build_skill_catalog,
    find_trigger_evals,
    run_trigger_eval,
)
from scripts.eval_runner.reporter import (
    trigger_report_markdown,
    trigger_report_json,
    save_report,
)
from scripts.eval_runner.snapshot import save_snapshot, list_snapshots


def cmd_trigger(args: argparse.Namespace) -> None:
    """Run trigger evals."""
    catalog = build_skill_catalog(args.project_root)
    trigger_evals = find_trigger_evals(args.project_root)
    mode = EvalMode(args.mode)

    skills = _resolve_skills(args, trigger_evals)
    results = []
    for skill in skills:
        if skill not in trigger_evals:
            print(f"SKIP: {skill} — no trigger-eval.json", file=sys.stderr)
            continue
        result = run_trigger_eval(skill, trigger_evals[skill], catalog, mode, args.top_n)
        results.append(result)

    if args.format == "markdown":
        output = trigger_report_markdown(results)
    elif args.format == "json":
        output = trigger_report_json(results)
    else:
        # text: print individual results
        for r in results:
            print(f"{r.skill_name}: trigger={r.trigger_accuracy:.1f}% anti={r.anti_trigger_accuracy:.1f}% overall={r.overall_accuracy:.1f}%")
        return

    if args.output:
        save_report(output, args.output)
        print(f"Report saved to {args.output}", file=sys.stderr)
    else:
        print(output)


def cmd_functional(args: argparse.Namespace) -> None:
    """Run functional evals (requires ANTHROPIC_API_KEY)."""
    from scripts.eval_runner.functional_eval import find_functional_evals, run_functional_evals

    evals = find_functional_evals(args.project_root)
    skills = _resolve_skills(args, evals)

    for skill in skills:
        if skill not in evals:
            print(f"SKIP: {skill} — no evals.json", file=sys.stderr)
            continue
        evals_path, skill_dir = evals[skill]
        result = run_functional_evals(skill, evals_path, skill_dir, True, args.model)
        print(f"{skill}: pass_rate={result.pass_rate:.1f}% tokens={result.total_tokens} latency={result.avg_latency_ms:.0f}ms")


def cmd_benchmark(args: argparse.Namespace) -> None:
    """Run A/B benchmark (requires ANTHROPIC_API_KEY)."""
    from scripts.eval_runner.benchmark import run_ab_benchmark
    comp = run_ab_benchmark(args.skill, args.project_root, args.model_a, args.model_b)
    if args.format == "json":
        print(json.dumps(dataclasses.asdict(comp), indent=2, default=str))
    else:
        a = comp.condition_a
        b = comp.condition_b
        if a and b:
            print(f"A ({a.condition}): pass={a.pass_rate:.1f}% tokens={a.total_tokens}")
            print(f"B ({b.condition}): pass={b.pass_rate:.1f}% tokens={b.total_tokens}")
            print(f"Delta: {comp.pass_rate_delta:+.1f}%")
            print(f"Recommendation: {comp.recommendation}")


def cmd_snapshot(args: argparse.Namespace) -> None:
    """Save or list baseline snapshots."""
    if args.list:
        snapshots = list_snapshots(args.project_root)
        for s in snapshots:
            print(f"{s['skill_name']} ({s['model']}): {s['metrics']}")
        return

    # To save, we need trigger eval results
    catalog = build_skill_catalog(args.project_root)
    trigger_evals = find_trigger_evals(args.project_root)

    if args.skill and args.skill in trigger_evals:
        result = run_trigger_eval(args.skill, trigger_evals[args.skill], catalog, EvalMode.FAST)
        metrics = {
            "trigger_accuracy": result.trigger_accuracy,
            "anti_trigger_accuracy": result.anti_trigger_accuracy,
            "overall_trigger_accuracy": result.overall_accuracy,
        }
        path = save_snapshot(args.skill, args.model, metrics, args.project_root)
        print(f"Snapshot saved: {path}")
    else:
        print("Specify --skill NAME to save, or --list to list", file=sys.stderr)


def cmd_regression(args: argparse.Namespace) -> None:
    """Check for regressions against baselines."""
    from scripts.eval_runner.regression import check_regression, format_regression_report

    catalog = build_skill_catalog(args.project_root)
    trigger_evals = find_trigger_evals(args.project_root)
    skills = _resolve_skills(args, trigger_evals)

    reports = []
    for skill in skills:
        if skill not in trigger_evals:
            continue
        # Run current eval
        result = run_trigger_eval(skill, trigger_evals[skill], catalog, EvalMode.FAST)
        current_metrics = {
            "trigger_accuracy": result.trigger_accuracy,
            "overall_trigger_accuracy": result.overall_accuracy,
        }
        report = check_regression(skill, args.model, current_metrics, args.project_root)
        reports.append(report)

    output = format_regression_report(reports)
    if args.output:
        save_report(output, args.output)
        print(f"Report saved to {args.output}", file=sys.stderr)
    else:
        print(output)


def _resolve_skills(args: argparse.Namespace, available: dict) -> list[str]:
    if hasattr(args, 'skill') and args.skill:
        return [args.skill]
    if hasattr(args, 'all') and args.all:
        return sorted(available.keys())
    print("Specify --skill NAME or --all", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(prog="eval_runner", description="Skill eval runner suite")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())

    sub = parser.add_subparsers(dest="command", required=True)

    # trigger
    p_trigger = sub.add_parser("trigger", help="Run trigger evals")
    p_trigger.add_argument("--skill", type=str)
    p_trigger.add_argument("--all", action="store_true")
    p_trigger.add_argument("--mode", choices=["fast", "deep"], default="fast")
    p_trigger.add_argument("--top-n", type=int, default=3)
    p_trigger.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    p_trigger.add_argument("--output", type=Path)

    # functional
    p_func = sub.add_parser("functional", help="Run functional evals")
    p_func.add_argument("--skill", type=str)
    p_func.add_argument("--all", action="store_true")
    p_func.add_argument("--model", default="claude-sonnet-4-5-20250514")
    p_func.add_argument("--format", choices=["text", "json"], default="text")

    # benchmark
    p_bench = sub.add_parser("benchmark", help="A/B benchmark")
    p_bench.add_argument("--skill", required=True)
    p_bench.add_argument("--model-a", default="claude-sonnet-4-5-20250514")
    p_bench.add_argument("--model-b", default=None)
    p_bench.add_argument("--format", choices=["text", "json"], default="text")

    # snapshot
    p_snap = sub.add_parser("snapshot", help="Save/list baselines")
    p_snap.add_argument("--skill", type=str)
    p_snap.add_argument("--all", action="store_true")
    p_snap.add_argument("--model", default="claude-sonnet-4-5-20250514")
    p_snap.add_argument("--list", action="store_true")

    # regression
    p_reg = sub.add_parser("regression", help="Check regressions")
    p_reg.add_argument("--skill", type=str)
    p_reg.add_argument("--all", action="store_true")
    p_reg.add_argument("--model", default="claude-sonnet-4-5-20250514")
    p_reg.add_argument("--output", type=Path)

    args = parser.parse_args()

    commands = {
        "trigger": cmd_trigger,
        "functional": cmd_functional,
        "benchmark": cmd_benchmark,
        "snapshot": cmd_snapshot,
        "regression": cmd_regression,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
