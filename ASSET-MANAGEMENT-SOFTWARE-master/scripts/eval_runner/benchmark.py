#!/usr/bin/env python3
"""A/B benchmark runner — compare skill performance across conditions.

Supports:
  - with-skill vs without-skill (capability uplift testing)
  - skill-v1 vs skill-v2 (iterative improvement testing)
  - multi-model comparison (e.g., Sonnet vs Opus)

Usage:
    python -m scripts.eval_runner.benchmark --skill assess-criticality --mode ab
    python -m scripts.eval_runner.benchmark --skill perform-fmeca --mode ab --model-a claude-sonnet-4-5-20250514 --model-b claude-opus-4-20250514
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.eval_runner.functional_eval import (
    find_functional_evals,
    run_functional_evals,
)
from scripts.eval_runner.models import (
    BenchmarkComparison,
    BenchmarkResult,
    EvalMode,
    SkillType,
)
from scripts.eval_runner.trigger_eval import (
    build_skill_catalog,
    find_trigger_evals,
    run_trigger_eval,
)


def _load_skill_classification(project_root: Path) -> dict[str, SkillType]:
    """Load skill type classifications from SKILL_CLASSIFICATION.md."""
    path = project_root / "skills" / "SKILL_CLASSIFICATION.md"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    result: dict[str, SkillType] = {}
    for line in text.split("\n"):
        if "|" in line and "capability" in line.lower():
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2:
                result[parts[0]] = SkillType.CAPABILITY_UPLIFT
        elif "|" in line and "encoded" in line.lower():
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2:
                result[parts[0]] = SkillType.ENCODED_PREFERENCE
    return result


def run_ab_benchmark(
    skill_name: str,
    project_root: Path,
    model_a: str = "claude-sonnet-4-5-20250514",
    model_b: str | None = None,
    run_triggers: bool = True,
) -> BenchmarkComparison:
    """Run A/B benchmark: with-skill (A) vs without-skill (B)."""
    functional_evals = find_functional_evals(project_root)
    trigger_evals = find_trigger_evals(project_root)
    catalog = build_skill_catalog(project_root)
    classifications = _load_skill_classification(project_root)

    if skill_name not in functional_evals:
        raise ValueError(f"No evals.json found for skill: {skill_name}")

    evals_path, skill_dir = functional_evals[skill_name]
    effective_model_b = model_b or model_a

    # Condition A: with-skill
    print(f"Running condition A (with-skill, {model_a})...", file=sys.stderr)
    eval_a = run_functional_evals(skill_name, evals_path, skill_dir, True, model_a)

    trigger_a = None
    if run_triggers and skill_name in trigger_evals:
        trigger_a = run_trigger_eval(
            skill_name, trigger_evals[skill_name], catalog, EvalMode.FAST
        )

    condition_a = BenchmarkResult(
        condition="with-skill",
        skill_name=skill_name,
        model=model_a,
        eval_result=eval_a,
        trigger_result=trigger_a,
    )

    # Condition B: without-skill
    print(f"Running condition B (without-skill, {effective_model_b})...", file=sys.stderr)
    eval_b = run_functional_evals(skill_name, evals_path, skill_dir, False, effective_model_b)

    condition_b = BenchmarkResult(
        condition="without-skill",
        skill_name=skill_name,
        model=effective_model_b,
        eval_result=eval_b,
        trigger_result=None,  # No triggers without skill
    )

    skill_type = classifications.get(skill_name, SkillType.CAPABILITY_UPLIFT)

    return BenchmarkComparison(
        skill_name=skill_name,
        skill_type=skill_type,
        condition_a=condition_a,
        condition_b=condition_b,
    )


def run_version_benchmark(
    skill_name: str,
    skill_dir_v1: Path,
    skill_dir_v2: Path,
    project_root: Path,
    model: str = "claude-sonnet-4-5-20250514",
) -> BenchmarkComparison:
    """Run version comparison benchmark: v1 vs v2 of a skill."""
    functional_evals = find_functional_evals(project_root)
    classifications = _load_skill_classification(project_root)

    if skill_name not in functional_evals:
        raise ValueError(f"No evals.json found for skill: {skill_name}")

    evals_path, _ = functional_evals[skill_name]

    # V1
    print(f"Running condition A (v1, {model})...", file=sys.stderr)
    eval_v1 = run_functional_evals(skill_name, evals_path, skill_dir_v1, True, model)
    condition_a = BenchmarkResult(
        condition="v1", skill_name=skill_name, model=model, eval_result=eval_v1,
    )

    # V2
    print(f"Running condition B (v2, {model})...", file=sys.stderr)
    eval_v2 = run_functional_evals(skill_name, evals_path, skill_dir_v2, True, model)
    condition_b = BenchmarkResult(
        condition="v2", skill_name=skill_name, model=model, eval_result=eval_v2,
    )

    skill_type = classifications.get(skill_name, SkillType.CAPABILITY_UPLIFT)
    return BenchmarkComparison(
        skill_name=skill_name,
        skill_type=skill_type,
        condition_a=condition_a,
        condition_b=condition_b,
    )


def _print_comparison(comp: BenchmarkComparison) -> None:
    print(f"\n{'=' * 70}")
    print(f"BENCHMARK: {comp.skill_name} ({comp.skill_type.value})")
    print(f"{'=' * 70}")

    a = comp.condition_a
    b = comp.condition_b
    if not a or not b:
        print("  Incomplete comparison — missing condition data")
        return

    header = f"{'Metric':<25} {'A (' + a.condition + ')':<20} {'B (' + b.condition + ')':<20} {'Delta':<15}"
    print(header)
    print("-" * 70)

    print(f"{'Pass Rate':<25} {a.pass_rate:>18.1f}% {b.pass_rate:>18.1f}% {comp.pass_rate_delta:>+13.1f}%")
    print(f"{'Total Tokens':<25} {a.total_tokens:>19} {b.total_tokens:>19} {comp.token_delta:>+14}")
    print(f"{'Avg Latency (ms)':<25} {a.avg_latency_ms:>18.0f} {b.avg_latency_ms:>18.0f} {comp.latency_delta_ms:>+13.0f}")
    if a.trigger_result:
        print(f"{'Trigger Accuracy':<25} {a.trigger_accuracy:>18.1f}% {'N/A':>19}")

    print(f"\nRecommendation: {comp.recommendation}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="A/B benchmark runner")
    parser.add_argument("--skill", required=True, help="Skill to benchmark")
    parser.add_argument(
        "--mode", choices=["ab", "version"], default="ab",
        help="ab: with-skill vs without-skill; version: v1 vs v2",
    )
    parser.add_argument("--model-a", default="claude-sonnet-4-5-20250514")
    parser.add_argument("--model-b", default=None, help="Model for condition B (default: same as A)")
    parser.add_argument("--v1-dir", type=Path, help="Skill v1 directory (for version mode)")
    parser.add_argument("--v2-dir", type=Path, help="Skill v2 directory (for version mode)")
    parser.add_argument("--no-triggers", action="store_true")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--format", choices=["json", "text"], default="text")
    args = parser.parse_args()

    if args.mode == "ab":
        comp = run_ab_benchmark(
            args.skill, args.project_root, args.model_a, args.model_b,
            run_triggers=not args.no_triggers,
        )
    elif args.mode == "version":
        if not args.v1_dir or not args.v2_dir:
            print("--v1-dir and --v2-dir required for version mode", file=sys.stderr)
            sys.exit(1)
        comp = run_version_benchmark(
            args.skill, args.v1_dir, args.v2_dir, args.project_root, args.model_a,
        )
    else:
        sys.exit(1)

    if args.format == "text":
        _print_comparison(comp)
    else:
        import dataclasses
        print(json.dumps(dataclasses.asdict(comp), indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
