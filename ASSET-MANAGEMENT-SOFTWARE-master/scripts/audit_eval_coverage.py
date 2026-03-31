#!/usr/bin/env python3
"""Eval coverage auditor for AMS and OR SYSTEM.

Scans all skill directories, checks for evals/evals.json and
evals/trigger-eval.json, and validates minimum thresholds.

Usage:
    python scripts/audit_eval_coverage.py [--project-root PATH] [--format json|markdown]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Minimum thresholds
MIN_SHOULD_TRIGGER = 10
MIN_SHOULD_NOT_TRIGGER = 10
MIN_FUNCTIONAL_TESTS = 3


@dataclass
class EvalCoverageResult:
    skill_name: str
    skill_path: str
    has_evals_json: bool = False
    has_trigger_eval_json: bool = False
    functional_test_count: int = 0
    should_trigger_count: int = 0
    should_not_trigger_count: int = 0
    functional_min_met: bool = False
    trigger_min_met: bool = False
    anti_trigger_min_met: bool = False
    issues: list[str] = field(default_factory=list)

    @property
    def coverage_grade(self) -> str:
        """A/B/C/F grading."""
        if all([self.has_evals_json, self.has_trigger_eval_json,
                self.functional_min_met, self.trigger_min_met, self.anti_trigger_min_met]):
            return "A"
        if self.has_evals_json and self.has_trigger_eval_json:
            return "B"
        if self.has_evals_json or self.has_trigger_eval_json:
            return "C"
        return "F"


def _load_json_safe(path: Path) -> dict | list | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def audit_eval_coverage(skill_dir: Path) -> EvalCoverageResult:
    """Audit eval coverage for one skill."""
    result = EvalCoverageResult(
        skill_name=skill_dir.name,
        skill_path=str(skill_dir),
    )

    evals_dir = skill_dir / "evals"
    evals_json = evals_dir / "evals.json"
    trigger_json = evals_dir / "trigger-eval.json"

    # Functional evals
    if evals_json.exists():
        result.has_evals_json = True
        data = _load_json_safe(evals_json)
        if isinstance(data, list):
            result.functional_test_count = len(data)
            result.functional_min_met = len(data) >= MIN_FUNCTIONAL_TESTS
            if not result.functional_min_met:
                result.issues.append(
                    f"Only {len(data)} functional tests (min {MIN_FUNCTIONAL_TESTS})"
                )
        else:
            result.issues.append("evals.json is not a JSON array")
    else:
        result.issues.append("Missing evals/evals.json")

    # Trigger evals
    if trigger_json.exists():
        result.has_trigger_eval_json = True
        data = _load_json_safe(trigger_json)
        if isinstance(data, dict):
            st = data.get("should_trigger", [])
            snt = data.get("should_not_trigger", [])
            result.should_trigger_count = len(st)
            result.should_not_trigger_count = len(snt)
            result.trigger_min_met = len(st) >= MIN_SHOULD_TRIGGER
            result.anti_trigger_min_met = len(snt) >= MIN_SHOULD_NOT_TRIGGER
            if not result.trigger_min_met:
                result.issues.append(
                    f"Only {len(st)} should_trigger examples (min {MIN_SHOULD_TRIGGER})"
                )
            if not result.anti_trigger_min_met:
                result.issues.append(
                    f"Only {len(snt)} should_not_trigger examples (min {MIN_SHOULD_NOT_TRIGGER})"
                )
        else:
            result.issues.append("trigger-eval.json is not a JSON object")
    else:
        result.issues.append("Missing evals/trigger-eval.json")

    return result


def discover_skills(project_root: Path) -> list[Path]:
    """Find all skill directories under skills/."""
    skills_dir = project_root / "skills"
    if not skills_dir.exists():
        return []
    results = []
    for claude_md in sorted(skills_dir.rglob("CLAUDE.md")):
        rel = claude_md.relative_to(skills_dir)
        if str(rel).startswith("00-knowledge-base"):
            continue
        results.append(claude_md.parent)
    return results


def _format_markdown(results: list[EvalCoverageResult]) -> str:
    lines = [
        "# Eval Coverage Audit Report",
        "",
        f"**Total skills:** {len(results)}",
        "",
    ]

    # Grade distribution
    grades = {"A": 0, "B": 0, "C": 0, "F": 0}
    for r in results:
        grades[r.coverage_grade] += 1
    lines.append("## Grade Distribution")
    lines.append("")
    for g in ["A", "B", "C", "F"]:
        bar = "#" * grades[g]
        lines.append(f"- **{g}**: {grades[g]} {bar}")
    lines.append("")

    # Detail table
    lines.extend([
        "## Detail",
        "",
        "| Skill | Grade | Functional | Should Trg | Should NOT Trg | Issues |",
        "|-------|-------|------------|------------|----------------|--------|",
    ])
    for r in sorted(results, key=lambda x: x.coverage_grade, reverse=True):
        lines.append(
            f"| {r.skill_name} | {r.coverage_grade} | "
            f"{r.functional_test_count} | {r.should_trigger_count} | "
            f"{r.should_not_trigger_count} | {len(r.issues)} |"
        )

    # Skills with issues
    lines.extend(["", "## Skills Needing Attention", ""])
    for r in sorted(results, key=lambda x: x.coverage_grade, reverse=True):
        if r.issues:
            lines.append(f"### {r.skill_name} (Grade: {r.coverage_grade})")
            for issue in r.issues:
                lines.append(f"- {issue}")
            lines.append("")

    return "\n".join(lines)


def _format_json(results: list[EvalCoverageResult]) -> str:
    data = {
        "total_skills": len(results),
        "grade_distribution": {
            g: sum(1 for r in results if r.coverage_grade == g)
            for g in ["A", "B", "C", "F"]
        },
        "skills": [
            {**asdict(r), "coverage_grade": r.coverage_grade}
            for r in sorted(results, key=lambda x: x.coverage_grade, reverse=True)
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit eval coverage")
    parser.add_argument(
        "--project-root", type=Path, default=Path.cwd(),
        help="Project root directory",
    )
    parser.add_argument(
        "--format", choices=["json", "markdown"], default="markdown",
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    skills = discover_skills(args.project_root)
    if not skills:
        print(f"No skills found under {args.project_root / 'skills'}", file=sys.stderr)
        sys.exit(1)

    results = [audit_eval_coverage(s) for s in skills]

    output = _format_markdown(results) if args.format == "markdown" else _format_json(results)

    if args.output:
        args.output.write_text(output, encoding="utf-8")
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
