"""Tests for agents.orchestration.execution_plan — Section 8: Functional Tests."""

from __future__ import annotations

import pytest
import yaml

from agents.orchestration.execution_plan import (
    ExecutionPlan,
    ExecutionPlanItem,
    ExecutionPlanStage,
    PlanStatus,
    StrategyApproach,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_item(id: str, status: PlanStatus = PlanStatus.PENDING, **kw) -> ExecutionPlanItem:
    return ExecutionPlanItem(id=id, description=f"Item {id}", status=status, **kw)


def _make_stage(
    id: str,
    milestone: int,
    items: list[ExecutionPlanItem] | None = None,
) -> ExecutionPlanStage:
    stage = ExecutionPlanStage(id=id, name=f"Stage {id}", milestone=milestone)
    stage.items = items or []
    return stage


def _make_plan(stages: list[ExecutionPlanStage] | None = None) -> ExecutionPlan:
    plan = ExecutionPlan(
        starting_milestone=1,
        approach=StrategyApproach.FULL_RCM,
        client_slug="test",
        project_slug="test-project",
    )
    plan.stages = stages or []
    return plan


# ---------------------------------------------------------------------------
# ExecutionPlanItem serialization
# ---------------------------------------------------------------------------

class TestExecutionPlanItem:
    def test_to_dict_minimal(self):
        item = _make_item("i1")
        d = item.to_dict()
        assert d["id"] == "i1"
        assert d["status"] == "pending"
        assert "depends_on" not in d  # empty list not serialized

    def test_to_dict_full(self):
        item = _make_item("i2", depends_on=["i1"], equipment_tag="PUMP-001")
        item.mark_completed()
        d = item.to_dict()
        assert d["depends_on"] == ["i1"]
        assert d["equipment_tag"] == "PUMP-001"
        assert d["status"] == "completed"
        assert "completed_at" in d

    def test_roundtrip(self):
        item = _make_item("i3", depends_on=["i1"], equipment_tag="X", criticality_class="AA")
        item.mark_in_progress()
        d = item.to_dict()
        restored = ExecutionPlanItem.from_dict(d)
        assert restored.id == "i3"
        assert restored.status == PlanStatus.IN_PROGRESS
        assert restored.depends_on == ["i1"]
        assert restored.equipment_tag == "X"
        assert restored.criticality_class == "AA"
        assert restored.started_at is not None

    def test_mark_skipped(self):
        item = _make_item("i4")
        item.mark_skipped()
        assert item.status == PlanStatus.SKIPPED


# ---------------------------------------------------------------------------
# ExecutionPlanStage progress
# ---------------------------------------------------------------------------

class TestExecutionPlanStage:
    def test_progress_empty(self):
        stage = _make_stage("s1", 1, items=[])
        assert stage.progress == 100.0

    def test_progress_all_pending(self):
        stage = _make_stage("s1", 1, items=[_make_item("i1"), _make_item("i2")])
        assert stage.progress == 0.0

    def test_progress_half(self):
        items = [
            _make_item("i1", PlanStatus.COMPLETED),
            _make_item("i2", PlanStatus.PENDING),
        ]
        stage = _make_stage("s1", 1, items=items)
        assert stage.progress == 50.0

    def test_progress_100(self):
        items = [
            _make_item("i1", PlanStatus.COMPLETED),
            _make_item("i2", PlanStatus.SKIPPED),
        ]
        stage = _make_stage("s1", 1, items=items)
        assert stage.progress == 100.0

    def test_recalculate_status_completed(self):
        items = [
            _make_item("i1", PlanStatus.COMPLETED),
            _make_item("i2", PlanStatus.COMPLETED),
        ]
        stage = _make_stage("s1", 1, items=items)
        stage.recalculate_status()
        assert stage.status == PlanStatus.COMPLETED

    def test_recalculate_status_in_progress(self):
        items = [
            _make_item("i1", PlanStatus.IN_PROGRESS),
            _make_item("i2", PlanStatus.PENDING),
        ]
        stage = _make_stage("s1", 1, items=items)
        stage.recalculate_status()
        assert stage.status == PlanStatus.IN_PROGRESS

    def test_recalculate_status_mixed(self):
        items = [
            _make_item("i1", PlanStatus.COMPLETED),
            _make_item("i2", PlanStatus.PENDING),
        ]
        stage = _make_stage("s1", 1, items=items)
        stage.recalculate_status()
        assert stage.status == PlanStatus.IN_PROGRESS

    def test_roundtrip(self):
        items = [_make_item("i1"), _make_item("i2")]
        stage = _make_stage("s1", 1, items=items)
        stage.skill = "hierarchy"
        d = stage.to_dict()
        restored = ExecutionPlanStage.from_dict(d)
        assert restored.id == "s1"
        assert restored.milestone == 1
        assert restored.skill == "hierarchy"
        assert len(restored.items) == 2


# ---------------------------------------------------------------------------
# ExecutionPlan.calculate_progress
# ---------------------------------------------------------------------------

class TestExecutionPlanProgress:
    def test_empty_plan(self):
        plan = _make_plan([])
        progress = plan.calculate_progress()
        assert progress["overall_progress"] == 100.0

    def test_total_progress(self):
        stages = [
            _make_stage("s1", 1, [
                _make_item("i1", PlanStatus.COMPLETED),
                _make_item("i2", PlanStatus.PENDING),
            ]),
            _make_stage("s2", 2, [
                _make_item("i3", PlanStatus.COMPLETED),
                _make_item("i4", PlanStatus.COMPLETED),
            ]),
        ]
        plan = _make_plan(stages)
        progress = plan.calculate_progress()
        # 3 of 4 done = 75%
        assert progress["overall_progress"] == 75.0
        assert progress["total_items"] == 4
        assert progress["total_completed"] == 3

    def test_stage_progress_reported(self):
        stages = [
            _make_stage("s1", 1, [_make_item("i1", PlanStatus.COMPLETED)]),
        ]
        plan = _make_plan(stages)
        progress = plan.calculate_progress()
        assert len(progress["stages"]) == 1
        assert progress["stages"][0]["progress"] == 100.0


# ---------------------------------------------------------------------------
# update_item_status
# ---------------------------------------------------------------------------

class TestUpdateItemStatus:
    def test_mark_completed(self):
        items = [_make_item("i1")]
        plan = _make_plan([_make_stage("s1", 1, items)])
        plan.update_item_status("i1", PlanStatus.COMPLETED)
        assert items[0].status == PlanStatus.COMPLETED

    def test_mark_in_progress(self):
        items = [_make_item("i1")]
        plan = _make_plan([_make_stage("s1", 1, items)])
        plan.update_item_status("i1", PlanStatus.IN_PROGRESS)
        assert items[0].status == PlanStatus.IN_PROGRESS
        assert items[0].started_at is not None

    def test_unknown_item_raises(self):
        plan = _make_plan([])
        with pytest.raises(KeyError, match="not-there"):
            plan.update_item_status("not-there", PlanStatus.COMPLETED)

    def test_stage_recalculated(self):
        items = [_make_item("i1"), _make_item("i2")]
        stage = _make_stage("s1", 1, items)
        plan = _make_plan([stage])
        plan.update_item_status("i1", PlanStatus.COMPLETED)
        plan.update_item_status("i2", PlanStatus.COMPLETED)
        assert stage.status == PlanStatus.COMPLETED


# ---------------------------------------------------------------------------
# get_next_pending_items
# ---------------------------------------------------------------------------

class TestGetNextPendingItems:
    def test_simple(self):
        items = [_make_item("i1"), _make_item("i2")]
        plan = _make_plan([_make_stage("s1", 1, items)])
        pending = plan.get_next_pending_items()
        assert len(pending) == 2
        assert pending[0].id == "i1"

    def test_respects_dependencies(self):
        items = [
            _make_item("i1"),
            _make_item("i2", depends_on=["i1"]),
        ]
        plan = _make_plan([_make_stage("s1", 1, items)])
        pending = plan.get_next_pending_items()
        # i2 depends on i1, so only i1 is eligible
        assert len(pending) == 1
        assert pending[0].id == "i1"

    def test_deps_met(self):
        items = [
            _make_item("i1", PlanStatus.COMPLETED),
            _make_item("i2", depends_on=["i1"]),
        ]
        plan = _make_plan([_make_stage("s1", 1, items)])
        pending = plan.get_next_pending_items()
        assert len(pending) == 1
        assert pending[0].id == "i2"

    def test_limit(self):
        items = [_make_item(f"i{n}") for n in range(20)]
        plan = _make_plan([_make_stage("s1", 1, items)])
        pending = plan.get_next_pending_items(limit=5)
        assert len(pending) == 5

    def test_skipped_deps_count_as_met(self):
        items = [
            _make_item("i1", PlanStatus.SKIPPED),
            _make_item("i2", depends_on=["i1"]),
        ]
        plan = _make_plan([_make_stage("s1", 1, items)])
        pending = plan.get_next_pending_items()
        assert len(pending) == 1
        assert pending[0].id == "i2"


# ---------------------------------------------------------------------------
# YAML serialization roundtrip
# ---------------------------------------------------------------------------

class TestYAMLSerialization:
    def test_to_yaml_valid(self):
        items = [_make_item("i1"), _make_item("i2")]
        plan = _make_plan([_make_stage("s1", 1, items)])
        yaml_str = plan.to_yaml()
        parsed = yaml.safe_load(yaml_str)
        assert "execution_plan" in parsed
        assert parsed["execution_plan"]["starting_milestone"] == 1

    def test_roundtrip(self):
        items = [
            _make_item("i1", depends_on=["i0"], equipment_tag="PUMP-001"),
            _make_item("i2", PlanStatus.COMPLETED),
        ]
        plan = _make_plan([
            _make_stage("s1", 1, items),
            _make_stage("s2", 2, [_make_item("i3")]),
        ])
        plan.approach = StrategyApproach.FMECA_SIMPLIFIED

        yaml_str = plan.to_yaml()
        restored = ExecutionPlan.from_yaml(yaml_str)

        assert restored.starting_milestone == plan.starting_milestone
        assert restored.approach == StrategyApproach.FMECA_SIMPLIFIED
        assert restored.client_slug == "test"
        assert len(restored.stages) == 2
        assert restored.stages[0].items[0].depends_on == ["i0"]
        assert restored.stages[0].items[0].equipment_tag == "PUMP-001"
        assert restored.stages[0].items[1].status == PlanStatus.COMPLETED

    def test_from_yaml_invalid(self):
        with pytest.raises(ValueError, match="missing 'execution_plan'"):
            ExecutionPlan.from_yaml("foo: bar")

    def test_file_roundtrip(self, tmp_path):
        items = [_make_item("i1")]
        plan = _make_plan([_make_stage("s1", 1, items)])
        path = tmp_path / "plan.yaml"
        plan.to_file(path)
        restored = ExecutionPlan.from_file(path)
        assert restored.stages[0].items[0].id == "i1"


# ---------------------------------------------------------------------------
# Dependency validation
# ---------------------------------------------------------------------------

class TestDependencyValidation:
    def test_valid(self):
        items = [_make_item("i1"), _make_item("i2", depends_on=["i1"])]
        plan = _make_plan([_make_stage("s1", 1, items)])
        assert plan.validate_dependencies() == []

    def test_broken_dep(self):
        items = [_make_item("i1", depends_on=["nonexistent"])]
        plan = _make_plan([_make_stage("s1", 1, items)])
        errors = plan.validate_dependencies()
        assert len(errors) == 1
        assert "nonexistent" in errors[0]

    def test_circular(self):
        items = [
            _make_item("i1", depends_on=["i2"]),
            _make_item("i2", depends_on=["i1"]),
        ]
        plan = _make_plan([_make_stage("s1", 1, items)])
        errors = plan.validate_dependencies()
        assert any("Circular" in e for e in errors)

    def test_self_loop(self):
        items = [_make_item("i1", depends_on=["i1"])]
        plan = _make_plan([_make_stage("s1", 1, items)])
        errors = plan.validate_dependencies()
        assert any("Circular" in e for e in errors)
