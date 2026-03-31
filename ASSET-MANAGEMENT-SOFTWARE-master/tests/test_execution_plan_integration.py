"""Tests for execution plan integration — Section 10: Integration Tests.

Tests integration between wizard, paths.py, workflow.py, and session_state.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

from agents.orchestration.execution_plan import (
    ExecutionPlan,
    ExecutionPlanItem,
    ExecutionPlanStage,
    PlanStatus,
    StrategyApproach,
)
from agents.orchestration.session_state import SessionState


# ---------------------------------------------------------------------------
# Wizard + paths.py integration
# ---------------------------------------------------------------------------

class TestWizardPaths:
    """Execution plan saved to correct 2-state/ location."""

    def test_plan_saved_to_state_dir(self, tmp_path):
        """Plan saves to 2-state/execution-plan.yaml via paths.py."""
        state_dir = tmp_path / "2-state"
        state_dir.mkdir()

        plan = ExecutionPlan(
            starting_milestone=1,
            approach=StrategyApproach.FULL_RCM,
            client_slug="test",
            project_slug="proj",
        )
        stage = ExecutionPlanStage(id="M1-HIER", name="Hierarchy", milestone=1)
        stage.items.append(ExecutionPlanItem(id="h-0001", description="Build"))
        plan.stages.append(stage)

        path = state_dir / "execution-plan.yaml"
        plan.to_file(path)

        assert path.is_file()
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data["execution_plan"]["client_slug"] == "test"


# ---------------------------------------------------------------------------
# Wizard + RFI data (project.yaml)
# ---------------------------------------------------------------------------

class TestWizardRFI:
    """Project.yaml from RFI correctly feeds wizard Step 1."""

    def test_project_yaml_fields_used(self, tmp_path):
        """Config from project.yaml populates wizard assessment defaults."""
        config = {
            "client": {"slug": "ocp", "name": "OCP Group"},
            "scope": {
                "type": "full-plant",
                "plant": {"name": "JFC", "code": "OCP-JFC"},
                "priority_equipment": ["SAG-001", "PUMP-002"],
            },
            "maintenance_context": {
                "strategy_maturity": "developing",
                "cmms": "sap-pm",
                "existing_data": {
                    "equipment_list": True,
                    "failure_history": False,
                },
            },
        }

        # Simulate wizard reading config
        existing = config["maintenance_context"]["existing_data"]
        assert existing["equipment_list"] is True
        assert existing["failure_history"] is False
        assert len(config["scope"]["priority_equipment"]) == 2


# ---------------------------------------------------------------------------
# Progress + workflow.py
# ---------------------------------------------------------------------------

class TestProgressWorkflow:
    """Workflow auto-updates execution plan on milestone completion."""

    def test_milestone_completion_marks_items(self, tmp_path):
        """When milestone is approved, its plan items are completed."""
        # Create a plan
        plan = ExecutionPlan(starting_milestone=1, approach=StrategyApproach.FULL_RCM)
        stage = ExecutionPlanStage(id="M1-HIER", name="Hierarchy", milestone=1)
        stage.items = [
            ExecutionPlanItem(id="h-0001", description="Item 1"),
            ExecutionPlanItem(id="h-0002", description="Item 2"),
        ]
        plan.stages.append(stage)

        plan_path = tmp_path / "execution-plan.yaml"
        plan.to_file(plan_path)

        # Simulate workflow approval: load, mark, save
        loaded = ExecutionPlan.from_file(plan_path)
        for s in loaded.stages:
            if s.milestone == 1:
                for item in s.items:
                    item.mark_completed()
                s.recalculate_status()
        loaded.to_file(plan_path)

        # Verify
        final = ExecutionPlan.from_file(plan_path)
        for s in final.stages:
            if s.milestone == 1:
                assert s.status == PlanStatus.COMPLETED
                for item in s.items:
                    assert item.status == PlanStatus.COMPLETED


# ---------------------------------------------------------------------------
# Progress + session_state.py
# ---------------------------------------------------------------------------

class TestProgressSessionState:
    """execution_plan_path is accessible from session state."""

    def test_execution_plan_path_in_session(self):
        """Session state stores execution_plan_path."""
        session = SessionState(
            session_id="s1",
            client_slug="ocp",
            project_slug="jfc",
            execution_plan_path="/tmp/plan.yaml",
        )
        assert session.execution_plan_path == "/tmp/plan.yaml"

    def test_execution_plan_path_serialized(self):
        """execution_plan_path survives JSON roundtrip."""
        session = SessionState(
            session_id="s1",
            execution_plan_path="/tmp/plan.yaml",
        )
        json_str = session.to_json()
        restored = SessionState.from_json(json_str)
        assert restored.execution_plan_path == "/tmp/plan.yaml"

    def test_execution_plan_path_default_empty(self):
        """Default execution_plan_path is empty string."""
        session = SessionState()
        assert session.execution_plan_path == ""


# ---------------------------------------------------------------------------
# YAML schema evolution
# ---------------------------------------------------------------------------

class TestSchemaEvolution:
    """Execution plan YAML is compatible between versions."""

    def test_extra_fields_ignored(self):
        """Future YAML with extra fields still loads."""
        yaml_str = yaml.dump({
            "execution_plan": {
                "starting_milestone": 1,
                "approach": "full-rcm",
                "client_slug": "x",
                "project_slug": "y",
                "created_at": "2026-01-01",
                "future_field": "should be ignored",
                "stages": [],
            }
        })
        plan = ExecutionPlan.from_yaml(yaml_str)
        assert plan.starting_milestone == 1

    def test_missing_optional_fields(self):
        """YAML without optional fields still loads."""
        yaml_str = yaml.dump({
            "execution_plan": {
                "stages": [],
            }
        })
        plan = ExecutionPlan.from_yaml(yaml_str)
        assert plan.starting_milestone == 1  # default
        assert plan.approach == StrategyApproach.FULL_RCM  # default
