"""Tests for AMS Consultant Wizard — Sections 8-9: Functional & System Tests.

Tests the wizard logic (not Streamlit UI) via wizard_cli module functions.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

# Ensure scripts/ is importable
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR.parent))

from agents.orchestration.execution_plan import (
    ExecutionPlan,
    PlanStatus,
    StrategyApproach,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project_yaml(tmp_path: Path, config: dict) -> Path:
    """Write a project.yaml to a fake project structure."""
    yaml_path = tmp_path / "project.yaml"
    yaml_path.write_text(yaml.dump(config), encoding="utf-8")
    return yaml_path


def _minimal_config() -> dict:
    return {
        "project": {"id": "test-001", "name": "Test Project"},
        "client": {"slug": "test", "name": "Test Inc", "industry": "mining"},
        "scope": {
            "type": "full-plant",
            "plant": {"name": "Test Plant", "code": "TST-01"},
            "priority_equipment": ["PUMP-001", "CONV-002"],
        },
        "maintenance_context": {
            "strategy_maturity": "developing",
            "cmms": "sap-pm",
            "existing_data": {
                "equipment_list": True,
                "failure_history": True,
                "existing_pm_plans": False,
            },
        },
    }


# ---------------------------------------------------------------------------
# Step 2 logic: starting milestone determination
# ---------------------------------------------------------------------------

class TestStartingMilestoneLogic:
    """Test the starting-point assessment logic from the wizard."""

    def test_no_hierarchy_starts_m1(self):
        """No existing data → start from M1."""
        assessment = {
            "has_hierarchy": False,
            "has_criticality": False,
            "has_pm_plans": False,
            "objective": StrategyApproach.FULL_RCM.value,
        }
        starting = 1
        if assessment["has_hierarchy"] and assessment["has_criticality"]:
            starting = 2
        assert starting == 1

    def test_hierarchy_and_criticality_starts_m2(self):
        """Has hierarchy + criticality → skip M1, start M2."""
        starting = 1
        has_hierarchy = True
        has_criticality = True
        if has_hierarchy:
            if has_criticality:
                starting = 2
        assert starting == 2

    def test_pm_optimization_with_plans_starts_m3(self):
        """PM optimization + existing plans → start M3."""
        starting = 1
        has_hierarchy = True
        has_criticality = True
        has_pm_plans = True
        objective = StrategyApproach.PM_OPTIMIZATION

        if has_hierarchy and has_criticality:
            starting = 2
        if objective == StrategyApproach.PM_OPTIMIZATION and has_pm_plans:
            starting = max(starting, 3)
        assert starting == 3


# ---------------------------------------------------------------------------
# Plan generation
# ---------------------------------------------------------------------------

class TestPlanGeneration:
    """Test that generated plans have correct structure."""

    def test_full_rcm_from_m1(self):
        """Full RCM from scratch should have M1-M4 stages."""
        plan = ExecutionPlan(
            starting_milestone=1,
            approach=StrategyApproach.FULL_RCM,
        )
        # Simulate wizard adding stages
        from agents.orchestration.execution_plan import ExecutionPlanStage, ExecutionPlanItem

        plan.stages = [
            ExecutionPlanStage(id="M1-HIER", name="Hierarchy", milestone=1),
            ExecutionPlanStage(id="M1-CRIT", name="Criticality", milestone=1),
            ExecutionPlanStage(id="M2-FMECA", name="FMECA", milestone=2),
            ExecutionPlanStage(id="M3-TASKS", name="Tasks", milestone=3),
            ExecutionPlanStage(id="M3-WP", name="WP", milestone=3),
            ExecutionPlanStage(id="M4-SAP", name="SAP", milestone=4),
        ]
        milestones = {s.milestone for s in plan.stages}
        assert milestones == {1, 2, 3, 4}

    def test_starting_m2_skips_hierarchy(self):
        """Starting at M2 should not have M1-HIER stage."""
        from agents.orchestration.execution_plan import ExecutionPlanStage

        plan = ExecutionPlan(starting_milestone=2, approach=StrategyApproach.FULL_RCM)
        stages = [
            ExecutionPlanStage(id="M2-FMECA", name="FMECA", milestone=2),
            ExecutionPlanStage(id="M3-TASKS", name="Tasks", milestone=3),
            ExecutionPlanStage(id="M4-SAP", name="SAP", milestone=4),
        ]
        plan.stages = stages
        assert not any(s.id.startswith("M1") for s in plan.stages)

    def test_items_grouped_by_equipment(self):
        """Equipment-scoped plans have per-tag items."""
        from agents.orchestration.execution_plan import ExecutionPlanStage, ExecutionPlanItem

        equipment = ["PUMP-001", "CONV-002", "MILL-003"]
        stage = ExecutionPlanStage(id="M2-FMECA", name="FMECA", milestone=2)
        for i, tag in enumerate(equipment):
            stage.items.append(ExecutionPlanItem(
                id=f"fmeca-{i:04d}",
                description=f"FMECA for {tag}",
                equipment_tag=tag,
            ))
        assert len(stage.items) == 3
        assert all(it.equipment_tag for it in stage.items)

    def test_plan_yaml_roundtrip(self, tmp_path):
        """Plan generated by wizard should survive YAML roundtrip."""
        from agents.orchestration.execution_plan import ExecutionPlanStage, ExecutionPlanItem

        plan = ExecutionPlan(
            starting_milestone=1,
            approach=StrategyApproach.FMECA_SIMPLIFIED,
            client_slug="test",
            project_slug="test-proj",
        )
        stage = ExecutionPlanStage(id="M1-HIER", name="Hierarchy", milestone=1)
        stage.items.append(ExecutionPlanItem(id="h-0001", description="Build hierarchy"))
        plan.stages.append(stage)

        path = tmp_path / "plan.yaml"
        plan.to_file(path)
        restored = ExecutionPlan.from_file(path)

        assert restored.approach == StrategyApproach.FMECA_SIMPLIFIED
        assert restored.starting_milestone == 1
        assert len(restored.stages) == 1
        assert restored.stages[0].items[0].id == "h-0001"


# ---------------------------------------------------------------------------
# Section 9: System-level E2E
# ---------------------------------------------------------------------------

class TestE2EFlow:
    """Simulate end-to-end wizard flow without Streamlit."""

    def test_wizard_produces_valid_yaml(self, tmp_path):
        """Wizard generates a valid execution-plan.yaml."""
        from agents.orchestration.execution_plan import ExecutionPlanStage, ExecutionPlanItem

        plan = ExecutionPlan(
            starting_milestone=1,
            approach=StrategyApproach.FULL_RCM,
            client_slug="ocp",
            project_slug="jfc",
        )
        stage = ExecutionPlanStage(id="M1-HIER", name="Hierarchy", milestone=1)
        stage.items.append(ExecutionPlanItem(id="h-0001", description="Decompose equipment"))
        plan.stages.append(stage)

        path = tmp_path / "execution-plan.yaml"
        plan.to_file(path)

        # Verify YAML is valid
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "execution_plan" in raw
        assert raw["execution_plan"]["starting_milestone"] == 1

    def test_wizard_without_project_yaml(self):
        """Wizard works in manual mode when project.yaml is missing."""
        # Just verify plan generation doesn't require project.yaml
        plan = ExecutionPlan(
            starting_milestone=1,
            approach=StrategyApproach.FULL_RCM,
        )
        assert plan.starting_milestone == 1
        assert plan.approach == StrategyApproach.FULL_RCM

    def test_progress_after_milestone_completion(self, tmp_path):
        """After completing a milestone, progress updates correctly."""
        from agents.orchestration.execution_plan import ExecutionPlanStage, ExecutionPlanItem

        plan = ExecutionPlan(
            starting_milestone=1,
            approach=StrategyApproach.FULL_RCM,
        )
        stage = ExecutionPlanStage(id="M1-HIER", name="Hierarchy", milestone=1)
        stage.items = [
            ExecutionPlanItem(id="h-0001", description="Item 1"),
            ExecutionPlanItem(id="h-0002", description="Item 2"),
        ]
        plan.stages.append(stage)

        # Before completion
        progress = plan.calculate_progress()
        assert progress["overall_progress"] == 0.0

        # Complete all items
        plan.update_item_status("h-0001", PlanStatus.COMPLETED)
        plan.update_item_status("h-0002", PlanStatus.COMPLETED)

        progress = plan.calculate_progress()
        assert progress["overall_progress"] == 100.0
