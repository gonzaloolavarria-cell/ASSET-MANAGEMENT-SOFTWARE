"""Regression detector — compare current results against saved baselines."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from scripts.eval_runner.snapshot import load_snapshot


# Threshold defaults
PASS_RATE_DROP_THRESHOLD = 10.0      # Alert if pass rate drops > 10%
TRIGGER_ACC_DROP_THRESHOLD = 15.0    # Alert if trigger accuracy drops > 15%
TOKEN_INCREASE_THRESHOLD = 50.0      # Alert if tokens increase > 50%


@dataclass
class RegressionAlert:
    skill_name: str
    metric: str
    baseline_value: float
    current_value: float
    delta: float
    threshold: float
    severity: str = "warning"  # "warning" or "critical"
    message: str = ""


@dataclass
class RegressionReport:
    skill_name: str
    model: str
    alerts: list[RegressionAlert] = field(default_factory=list)
    has_baseline: bool = False
    obsolescence_detected: bool = False

    @property
    def is_clean(self) -> bool:
        return self.has_baseline and len(self.alerts) == 0


def check_regression(
    skill_name: str,
    model: str,
    current_metrics: dict,
    project_root: Path,
    pass_rate_threshold: float = PASS_RATE_DROP_THRESHOLD,
    trigger_threshold: float = TRIGGER_ACC_DROP_THRESHOLD,
    token_threshold: float = TOKEN_INCREASE_THRESHOLD,
) -> RegressionReport:
    """Compare current metrics against the saved baseline.

    Args:
        skill_name: Skill identifier.
        model: Model identifier.
        current_metrics: Dict with: pass_rate, trigger_accuracy, total_tokens, avg_latency_ms.
        project_root: Project root directory.

    Returns:
        RegressionReport with any alerts.
    """
    report = RegressionReport(skill_name=skill_name, model=model)

    baseline = load_snapshot(skill_name, model, project_root)
    if not baseline:
        report.has_baseline = False
        return report
    report.has_baseline = True

    bm = baseline.get("metrics", {})

    # Pass rate regression
    if "pass_rate" in bm and "pass_rate" in current_metrics:
        delta = current_metrics["pass_rate"] - bm["pass_rate"]
        if delta < -pass_rate_threshold:
            report.alerts.append(RegressionAlert(
                skill_name=skill_name,
                metric="pass_rate",
                baseline_value=bm["pass_rate"],
                current_value=current_metrics["pass_rate"],
                delta=delta,
                threshold=pass_rate_threshold,
                severity="critical",
                message=f"Pass rate dropped {abs(delta):.1f}% (threshold: {pass_rate_threshold}%)",
            ))

    # Trigger accuracy regression
    for key in ("trigger_accuracy", "overall_trigger_accuracy"):
        if key in bm and key in current_metrics:
            delta = current_metrics[key] - bm[key]
            if delta < -trigger_threshold:
                report.alerts.append(RegressionAlert(
                    skill_name=skill_name,
                    metric=key,
                    baseline_value=bm[key],
                    current_value=current_metrics[key],
                    delta=delta,
                    threshold=trigger_threshold,
                    severity="warning",
                    message=f"{key} dropped {abs(delta):.1f}% (threshold: {trigger_threshold}%)",
                ))

    # Token increase (skill may be confusing the model)
    if "total_tokens" in bm and "total_tokens" in current_metrics:
        bl_tok = bm["total_tokens"]
        cur_tok = current_metrics["total_tokens"]
        if bl_tok > 0:
            pct_increase = ((cur_tok - bl_tok) / bl_tok) * 100
            if pct_increase > token_threshold:
                report.alerts.append(RegressionAlert(
                    skill_name=skill_name,
                    metric="total_tokens",
                    baseline_value=bl_tok,
                    current_value=cur_tok,
                    delta=pct_increase,
                    threshold=token_threshold,
                    severity="warning",
                    message=f"Tokens increased {pct_increase:.1f}% (threshold: {token_threshold}%)",
                ))

    return report


def check_obsolescence(
    skill_name: str,
    with_skill_pass_rate: float,
    without_skill_pass_rate: float,
) -> bool:
    """Check if a capability-uplift skill is obsolete.

    Returns True if the model performs as well or better WITHOUT the skill.
    """
    return without_skill_pass_rate >= with_skill_pass_rate - 2.0


def format_regression_report(reports: list[RegressionReport]) -> str:
    """Format regression reports as markdown."""
    lines = [
        "# Regression Detection Report",
        "",
    ]

    clean = [r for r in reports if r.is_clean]
    alerts = [r for r in reports if r.alerts]
    no_baseline = [r for r in reports if not r.has_baseline]

    lines.append(f"**Clean:** {len(clean)} | **Alerts:** {len(alerts)} | **No baseline:** {len(no_baseline)}")
    lines.append("")

    if alerts:
        lines.append("## Alerts")
        lines.append("")
        for r in alerts:
            lines.append(f"### {r.skill_name} ({r.model})")
            for a in r.alerts:
                icon = "!!!" if a.severity == "critical" else "!"
                lines.append(
                    f"- [{icon}] **{a.metric}**: {a.baseline_value:.1f} -> "
                    f"{a.current_value:.1f} ({a.delta:+.1f}) — {a.message}"
                )
            lines.append("")

    if no_baseline:
        lines.append("## No Baseline Available")
        lines.append("")
        for r in no_baseline:
            lines.append(f"- {r.skill_name}")
        lines.append("")
        lines.append("Run `snapshot.py` to create baselines for these skills.")

    return "\n".join(lines)
