"""Report generator for eval results — JSON and Markdown outputs."""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.eval_runner.models import (
    BenchmarkComparison,
    EvalResult,
    EvalStatus,
    TriggerEvalResult,
)


def _as_json(obj: object) -> str:
    return json.dumps(dataclasses.asdict(obj), indent=2, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Trigger report
# ---------------------------------------------------------------------------

def trigger_report_markdown(results: list[TriggerEvalResult]) -> str:
    lines = [
        "# Trigger Eval Report",
        "",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Skills tested:** {len(results)}",
        "",
        "| Skill | Mode | Trigger Acc | Anti-Trigger Acc | Overall |",
        "|-------|------|-------------|------------------|---------|",
    ]
    for r in sorted(results, key=lambda x: x.overall_accuracy):
        lines.append(
            f"| {r.skill_name} | {r.mode.value} | "
            f"{r.trigger_accuracy:.1f}% | {r.anti_trigger_accuracy:.1f}% | "
            f"{r.overall_accuracy:.1f}% |"
        )

    avg = sum(r.overall_accuracy for r in results) / max(len(results), 1)
    lines.extend([
        "",
        f"**Average overall accuracy:** {avg:.1f}%",
    ])

    # Failed triggers detail
    failures = []
    for r in results:
        for m in r.should_trigger_results:
            if m.status == EvalStatus.FAIL:
                failures.append((r.skill_name, "should_trigger", m.query, m.matched_skills))
        for m in r.should_not_trigger_results:
            if m.in_top_n:
                failures.append((r.skill_name, "should_NOT_trigger", m.query, m.matched_skills))

    if failures:
        lines.extend(["", "## Failed Triggers", ""])
        for skill, ttype, query, matched in failures[:50]:
            lines.append(f"- **{skill}** ({ttype}): \"{query[:80]}\" -> matched: {', '.join(matched[:3])}")

    return "\n".join(lines)


def trigger_report_json(results: list[TriggerEvalResult]) -> str:
    return json.dumps(
        [dataclasses.asdict(r) for r in results],
        indent=2, ensure_ascii=False, default=str,
    )


# ---------------------------------------------------------------------------
# Functional report
# ---------------------------------------------------------------------------

def functional_report_markdown(results: list[EvalResult]) -> str:
    lines = [
        "# Functional Eval Report",
        "",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Skills tested:** {len(results)}",
        "",
        "| Skill | Model | Pass Rate | Tests | Tokens | Avg Latency |",
        "|-------|-------|-----------|-------|--------|-------------|",
    ]
    for r in sorted(results, key=lambda x: x.pass_rate):
        test_count = len(r.results)
        lines.append(
            f"| {r.skill_name} | {r.model} | {r.pass_rate:.1f}% | "
            f"{test_count} | {r.total_tokens} | {r.avg_latency_ms:.0f}ms |"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Benchmark report
# ---------------------------------------------------------------------------

def benchmark_report_markdown(comparisons: list[BenchmarkComparison]) -> str:
    lines = [
        "# Benchmark Report (A/B Testing)",
        "",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Skills benchmarked:** {len(comparisons)}",
        "",
        "| Skill | Type | A Pass% | B Pass% | Delta | Tokens A | Tokens B | Recommendation |",
        "|-------|------|---------|---------|-------|----------|----------|----------------|",
    ]
    for c in comparisons:
        a_pr = c.condition_a.pass_rate if c.condition_a else 0
        b_pr = c.condition_b.pass_rate if c.condition_b else 0
        a_tok = c.condition_a.total_tokens if c.condition_a else 0
        b_tok = c.condition_b.total_tokens if c.condition_b else 0
        lines.append(
            f"| {c.skill_name} | {c.skill_type.value} | "
            f"{a_pr:.1f}% | {b_pr:.1f}% | {c.pass_rate_delta:+.1f}% | "
            f"{a_tok} | {b_tok} | {c.recommendation[:40]} |"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Save report
# ---------------------------------------------------------------------------

def save_report(content: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
