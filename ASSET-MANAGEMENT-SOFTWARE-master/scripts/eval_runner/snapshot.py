"""Baseline snapshot manager — save and load eval baselines for regression detection."""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone
from pathlib import Path


def _default_baselines_dir(project_root: Path) -> Path:
    return project_root / "evals" / "baselines"


def save_snapshot(
    skill_name: str,
    model: str,
    metrics: dict,
    project_root: Path,
) -> Path:
    """Save a baseline snapshot for a skill/model combo.

    Args:
        skill_name: Skill identifier.
        model: Model identifier (e.g., "claude-opus-4-20250514").
        metrics: Dict with keys: pass_rate, trigger_accuracy, total_tokens, avg_latency_ms.
        project_root: Project root directory.

    Returns:
        Path to the saved snapshot file.
    """
    baselines_dir = _default_baselines_dir(project_root) / _sanitize(model)
    baselines_dir.mkdir(parents=True, exist_ok=True)

    snapshot = {
        "skill_name": skill_name,
        "model": model,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
    }

    path = baselines_dir / f"{skill_name}.json"
    path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_snapshot(
    skill_name: str,
    model: str,
    project_root: Path,
) -> dict | None:
    """Load a baseline snapshot for a skill/model combo."""
    path = _default_baselines_dir(project_root) / _sanitize(model) / f"{skill_name}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_snapshots(project_root: Path) -> list[dict]:
    """List all saved snapshots."""
    baselines_dir = _default_baselines_dir(project_root)
    if not baselines_dir.exists():
        return []
    results = []
    for model_dir in sorted(baselines_dir.iterdir()):
        if model_dir.is_dir():
            for snap_file in sorted(model_dir.glob("*.json")):
                data = json.loads(snap_file.read_text(encoding="utf-8"))
                results.append(data)
    return results


def save_from_eval_results(
    trigger_result=None,
    functional_result=None,
    project_root: Path = Path("."),
) -> Path | None:
    """Convenience: save snapshot from TriggerEvalResult + EvalResult."""
    if not trigger_result and not functional_result:
        return None

    skill_name = (
        trigger_result.skill_name if trigger_result
        else functional_result.skill_name
    )
    model = functional_result.model if functional_result else "unknown"

    metrics = {}
    if trigger_result:
        metrics["trigger_accuracy"] = trigger_result.trigger_accuracy
        metrics["anti_trigger_accuracy"] = trigger_result.anti_trigger_accuracy
        metrics["overall_trigger_accuracy"] = trigger_result.overall_accuracy
    if functional_result:
        metrics["pass_rate"] = functional_result.pass_rate
        metrics["total_tokens"] = functional_result.total_tokens
        metrics["avg_latency_ms"] = functional_result.avg_latency_ms

    return save_snapshot(skill_name, model, metrics, project_root)


def _sanitize(s: str) -> str:
    """Sanitize a string for use as a directory name."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in s)
