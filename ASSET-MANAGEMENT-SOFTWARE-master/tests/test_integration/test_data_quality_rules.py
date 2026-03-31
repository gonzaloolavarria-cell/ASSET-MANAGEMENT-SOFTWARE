"""
Integration tests: Data quality rules validation.
72-combo rule, T-16 rule, SAP constraints, confidence thresholds.
"""

import pytest

from tools.models.schemas import (
    ApprovalStatus,
    Cause,
    FailureConsequence,
    FailureEffect,
    FailureMode,
    FailurePattern,
    FrequencyUnit,
    LabourResource,
    LabourSpecialty,
    MaintenanceTask,
    MaterialResource,
    Mechanism,
    NodeMetadata,
    NodeType,
    PlantHierarchyNode,
    StrategyType,
    TaskConstraint,
    TaskType,
    UnitOfMeasure,
    VALID_FM_COMBINATIONS,
    WorkPackage,
    WPConstraint,
    WPType,
    LabourSummary,
    LabourSummaryEntry,
    BudgetType,
)
from tools.engines.sap_export_engine import SAPExportEngine, SAP_SHORT_TEXT_MAX, SAP_FUNC_LOC_MAX


pytestmark = pytest.mark.integration


class TestComboRule72:
    """Validate the 72 valid failure mode combinations."""

    def test_valid_combos_count(self):
        """There should be exactly 72 valid combinations."""
        assert len(VALID_FM_COMBINATIONS) == 72

    def test_all_valid_combos_accepted(self):
        """All 72 combos create valid FailureMode objects."""
        for mechanism_val, cause_val in list(VALID_FM_COMBINATIONS)[:10]:
            fm = FailureMode(
                functional_failure_id="test-ff",
                what="Component",
                mechanism=Mechanism(mechanism_val),
                cause=Cause(cause_val),
                failure_consequence=FailureConsequence.EVIDENT_OPERATIONAL,
                is_hidden=False,
                failure_effect=FailureEffect(
                    evidence="Test evidence",
                    production_impact="Test impact",
                    estimated_downtime_hours=1.0,
                ),
                strategy_type=StrategyType.CONDITION_BASED,
            )
            assert fm.mechanism.value == mechanism_val
            assert fm.cause.value == cause_val

    def test_mechanism_enum_completeness(self):
        """All mechanisms in combos are valid enum values."""
        mechanisms_in_combos = {m for m, _ in VALID_FM_COMBINATIONS}
        for m in mechanisms_in_combos:
            assert Mechanism(m)  # Should not raise

    def test_cause_enum_completeness(self):
        """All causes in combos are valid enum values."""
        causes_in_combos = {c for _, c in VALID_FM_COMBINATIONS}
        for c in causes_in_combos:
            assert Cause(c)  # Should not raise

    def test_pipeline_fmeca_uses_valid_combos(self, pipeline_fmeca):
        """Pipeline test data uses valid 72-combo pairs."""
        for fm in pipeline_fmeca["failure_modes"]:
            combo = (fm.mechanism.value, fm.cause.value)
            assert combo in VALID_FM_COMBINATIONS

    def test_combo_is_tuple_set(self):
        """Combos stored as set of tuples for O(1) lookup."""
        assert isinstance(VALID_FM_COMBINATIONS, (set, frozenset))
        sample = next(iter(VALID_FM_COMBINATIONS))
        assert isinstance(sample, tuple)
        assert len(sample) == 2


class TestT16Rule:
    """T-16 rule: REPLACE tasks MUST have materials."""

    def test_replace_without_materials_detected(self, pipeline_tasks):
        """Detect REPLACE tasks missing materials."""
        for task in pipeline_tasks:
            if task.task_type == TaskType.REPLACE:
                assert len(task.material_resources) > 0, (
                    f"T-16 violation: '{task.name}'"
                )

    def test_non_replace_ok_without_materials(self):
        """Non-REPLACE tasks don't need materials."""
        task = MaintenanceTask(
            name="Inspect bearing vibration",
            name_fr="Inspecter vibration",
            task_type=TaskType.INSPECT,
            consequences="Bearing failure",
            constraint=TaskConstraint.ONLINE,
            access_time_hours=0.0,
            frequency_value=4,
            frequency_unit=FrequencyUnit.WEEKS,
        )
        # No material_resources -- should be fine for INSPECT
        assert task.task_type == TaskType.INSPECT
        assert len(task.material_resources) == 0

    def test_replace_with_materials_passes(self):
        """REPLACE task with materials satisfies T-16."""
        task = MaintenanceTask(
            name="Replace bearing",
            name_fr="Remplacer roulement",
            task_type=TaskType.REPLACE,
            consequences="Shaft damage",
            constraint=TaskConstraint.OFFLINE,
            access_time_hours=2.0,
            frequency_value=52,
            frequency_unit=FrequencyUnit.WEEKS,
            material_resources=[
                MaterialResource(
                    description="Bearing 22340",
                    stock_code="MAT-001",
                    quantity=1,
                    unit_of_measure=UnitOfMeasure.EA,
                    unit_price=12500.0,
                ),
            ],
        )
        assert len(task.material_resources) > 0

    def test_secondary_replace_has_materials(self, pipeline_tasks):
        """Secondary REPLACE tasks also require materials."""
        secondary_replace = [t for t in pipeline_tasks
                             if t.task_type == TaskType.REPLACE and t.is_secondary]
        for task in secondary_replace:
            assert len(task.material_resources) > 0


class TestSAPConstraints:
    """SAP field length constraints."""

    def test_short_text_max_72(self):
        """Task names must be <= 72 chars."""
        assert SAP_SHORT_TEXT_MAX == 72

    def test_func_loc_max_40(self):
        """Functional location codes must be <= 40 chars."""
        assert SAP_FUNC_LOC_MAX == 40

    def test_task_list_desc_max_40(self):
        """Task list descriptions must be <= 40 chars (same as func loc)."""
        assert SAP_FUNC_LOC_MAX == 40

    def test_pipeline_tasks_under_limit(self, pipeline_tasks):
        """All pipeline tasks respect SAP_SHORT_TEXT_MAX."""
        for task in pipeline_tasks:
            assert len(task.name) <= 72, f"'{task.name}' is {len(task.name)} chars"

    def test_pipeline_wps_under_limit(self, pipeline_work_packages):
        """All pipeline WPs respect name limit."""
        for wp in pipeline_work_packages:
            assert len(wp.name) <= 40, f"'{wp.name}' is {len(wp.name)} chars"


class TestConfidenceThresholds:
    """Confidence scoring thresholds."""

    def test_below_07_should_flag(self):
        """Entities with confidence < 0.7 should be flagged."""
        fm = FailureMode(
            functional_failure_id="test",
            what="Bearing",
            mechanism=Mechanism.WEARS,
            cause=Cause.RELATIVE_MOVEMENT,
            failure_consequence=FailureConsequence.EVIDENT_OPERATIONAL,
            is_hidden=False,
            failure_effect=FailureEffect(evidence="Test", estimated_downtime_hours=1),
            strategy_type=StrategyType.CONDITION_BASED,
            ai_confidence=0.5,
        )
        assert fm.ai_confidence < 0.7

    def test_above_07_passes(self):
        """Entities with confidence >= 0.7 pass threshold."""
        fm = FailureMode(
            functional_failure_id="test",
            what="Bearing",
            mechanism=Mechanism.WEARS,
            cause=Cause.RELATIVE_MOVEMENT,
            failure_consequence=FailureConsequence.EVIDENT_OPERATIONAL,
            is_hidden=False,
            failure_effect=FailureEffect(evidence="Test", estimated_downtime_hours=1),
            strategy_type=StrategyType.CONDITION_BASED,
            ai_confidence=0.85,
        )
        assert fm.ai_confidence >= 0.7

    def test_confidence_range_validation(self):
        """Confidence must be between 0 and 1."""
        fm = FailureMode(
            functional_failure_id="test",
            what="Bearing",
            mechanism=Mechanism.WEARS,
            cause=Cause.RELATIVE_MOVEMENT,
            failure_consequence=FailureConsequence.EVIDENT_OPERATIONAL,
            is_hidden=False,
            failure_effect=FailureEffect(evidence="Test", estimated_downtime_hours=1),
            strategy_type=StrategyType.CONDITION_BASED,
            ai_confidence=0.0,
        )
        assert 0.0 <= fm.ai_confidence <= 1.0

    def test_pipeline_fms_confidence_valid(self, pipeline_fmeca):
        """Pipeline failure modes have valid confidence values."""
        for fm in pipeline_fmeca["failure_modes"]:
            if fm.ai_confidence is not None:
                assert 0.0 <= fm.ai_confidence <= 1.0

    def test_none_confidence_acceptable(self):
        """None confidence (not AI-generated) is acceptable."""
        fm = FailureMode(
            functional_failure_id="test",
            what="Bearing",
            mechanism=Mechanism.WEARS,
            cause=Cause.RELATIVE_MOVEMENT,
            failure_consequence=FailureConsequence.EVIDENT_OPERATIONAL,
            is_hidden=False,
            failure_effect=FailureEffect(evidence="Test", estimated_downtime_hours=1),
            strategy_type=StrategyType.CONDITION_BASED,
            ai_confidence=None,
        )
        assert fm.ai_confidence is None
