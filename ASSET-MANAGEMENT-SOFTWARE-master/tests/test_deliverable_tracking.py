"""Tests for DeliverableTrackingEngine — GAP-W10.

Covers: state transitions, variance calculation, summary aggregation,
and execution plan seeding.
"""

import pytest

from tools.engines.deliverable_tracking_engine import (
    DEFAULT_HOURS,
    STAGE_TO_CATEGORY,
    VALID_TRANSITIONS,
    DeliverableTrackingEngine,
)
from tools.models.schemas import DeliverableCategory, DeliverableStatus


# ═══════════════════════════════════════════════════════════════════════════
# Status transition tests
# ═══════════════════════════════════════════════════════════════════════════

class TestValidTransitions:

    @pytest.mark.parametrize("current,target", [
        (DeliverableStatus.DRAFT, DeliverableStatus.IN_PROGRESS),
        (DeliverableStatus.IN_PROGRESS, DeliverableStatus.SUBMITTED),
        (DeliverableStatus.SUBMITTED, DeliverableStatus.UNDER_REVIEW),
        (DeliverableStatus.UNDER_REVIEW, DeliverableStatus.APPROVED),
        (DeliverableStatus.UNDER_REVIEW, DeliverableStatus.REJECTED),
        (DeliverableStatus.REJECTED, DeliverableStatus.IN_PROGRESS),
    ])
    def test_valid_transition(self, current, target):
        assert DeliverableTrackingEngine.validate_transition(current, target) is True
        result = DeliverableTrackingEngine.transition(current, target)
        assert result == target

    def test_invalid_transition_draft_to_approved(self):
        assert DeliverableTrackingEngine.validate_transition(
            DeliverableStatus.DRAFT, DeliverableStatus.APPROVED
        ) is False
        with pytest.raises(ValueError, match="Invalid transition"):
            DeliverableTrackingEngine.transition(
                DeliverableStatus.DRAFT, DeliverableStatus.APPROVED
            )

    def test_invalid_transition_approved_terminal(self):
        """APPROVED is terminal — no transitions out."""
        for target in DeliverableStatus:
            if target != DeliverableStatus.APPROVED:
                assert DeliverableTrackingEngine.validate_transition(
                    DeliverableStatus.APPROVED, target
                ) is False

    def test_invalid_transition_rejected_to_submitted(self):
        """REJECTED can only go to IN_PROGRESS, not SUBMITTED."""
        assert DeliverableTrackingEngine.validate_transition(
            DeliverableStatus.REJECTED, DeliverableStatus.SUBMITTED
        ) is False

    def test_transition_error_message_includes_valid_targets(self):
        with pytest.raises(ValueError, match="Valid targets"):
            DeliverableTrackingEngine.transition(
                DeliverableStatus.DRAFT, DeliverableStatus.SUBMITTED
            )


# ═══════════════════════════════════════════════════════════════════════════
# Variance calculation tests
# ═══════════════════════════════════════════════════════════════════════════

class TestVarianceCalculation:

    def test_on_track(self):
        result = DeliverableTrackingEngine.calculate_variance(10.0, 10.5)
        assert result["on_track"] is True
        assert result["variance_hours"] == 0.5
        assert result["variance_pct"] == 5.0

    def test_over_budget(self):
        result = DeliverableTrackingEngine.calculate_variance(10.0, 12.0)
        assert result["on_track"] is False
        assert result["variance_hours"] == 2.0
        assert result["variance_pct"] == 20.0

    def test_under_budget(self):
        result = DeliverableTrackingEngine.calculate_variance(10.0, 8.0)
        assert result["on_track"] is True
        assert result["variance_hours"] == -2.0
        assert result["variance_pct"] == -20.0

    def test_zero_estimate(self):
        result = DeliverableTrackingEngine.calculate_variance(0.0, 5.0)
        assert result["variance_pct"] == 0.0
        # When estimate is 0, can't compute meaningful pct

    def test_exact_threshold_10pct(self):
        """10% variance is still considered on track (<=10)."""
        result = DeliverableTrackingEngine.calculate_variance(10.0, 11.0)
        assert result["on_track"] is True
        assert result["variance_pct"] == 10.0


# ═══════════════════════════════════════════════════════════════════════════
# Summary aggregation tests
# ═══════════════════════════════════════════════════════════════════════════

class TestBuildSummary:

    def test_empty_list(self):
        summary = DeliverableTrackingEngine.build_summary([])
        assert summary.total_deliverables == 0
        assert summary.overall_completion_pct == 0.0
        assert summary.by_status == {}
        assert summary.by_milestone == {}

    def test_mixed_deliverables(self):
        deliverables = [
            {"status": "DRAFT", "milestone": 1, "estimated_hours": 2.0, "actual_hours": 0.0},
            {"status": "IN_PROGRESS", "milestone": 1, "estimated_hours": 3.0, "actual_hours": 1.5},
            {"status": "APPROVED", "milestone": 2, "estimated_hours": 8.0, "actual_hours": 7.0},
            {"status": "APPROVED", "milestone": 2, "estimated_hours": 4.0, "actual_hours": 5.0},
        ]
        summary = DeliverableTrackingEngine.build_summary(deliverables)
        assert summary.total_deliverables == 4
        assert summary.by_status["DRAFT"] == 1
        assert summary.by_status["IN_PROGRESS"] == 1
        assert summary.by_status["APPROVED"] == 2
        assert summary.by_milestone[1] == 2
        assert summary.by_milestone[2] == 2
        assert summary.total_estimated_hours == 17.0
        assert summary.total_actual_hours == 13.5
        assert summary.overall_completion_pct == 50.0  # 2 approved / 4 total

    def test_all_approved(self):
        deliverables = [
            {"status": "APPROVED", "milestone": 1, "estimated_hours": 2.0, "actual_hours": 2.0},
            {"status": "APPROVED", "milestone": 1, "estimated_hours": 3.0, "actual_hours": 3.0},
        ]
        summary = DeliverableTrackingEngine.build_summary(deliverables)
        assert summary.overall_completion_pct == 100.0
        assert summary.variance_hours == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# Seed from execution plan tests
# ═══════════════════════════════════════════════════════════════════════════

class TestSeedFromExecutionPlan:

    def test_maps_stage_names_to_categories(self):
        plan = {
            "stages": [
                {"id": "s1", "name": "hierarchy", "milestone": 1},
                {"id": "s2", "name": "criticality", "milestone": 1},
                {"id": "s3", "name": "fmeca", "milestone": 2},
            ]
        }
        result = DeliverableTrackingEngine.seed_from_execution_plan(plan, "ocp", "jfc")
        assert len(result) == 3
        assert result[0]["category"] == "HIERARCHY"
        assert result[1]["category"] == "CRITICALITY"
        assert result[2]["category"] == "FMECA"
        assert result[0]["client_slug"] == "ocp"
        assert result[0]["project_slug"] == "jfc"

    def test_default_hours_assigned(self):
        plan = {
            "stages": [
                {"id": "s1", "name": "hierarchy", "milestone": 1},
                {"id": "s2", "name": "fmeca", "milestone": 2},
            ]
        }
        result = DeliverableTrackingEngine.seed_from_execution_plan(plan)
        assert result[0]["estimated_hours"] == DEFAULT_HOURS[DeliverableCategory.HIERARCHY]
        assert result[1]["estimated_hours"] == DEFAULT_HOURS[DeliverableCategory.FMECA]

    def test_unknown_stage_maps_to_custom(self):
        plan = {
            "stages": [
                {"id": "s1", "name": "something-unknown", "milestone": 3},
            ]
        }
        result = DeliverableTrackingEngine.seed_from_execution_plan(plan)
        assert result[0]["category"] == "CUSTOM"
        assert result[0]["estimated_hours"] == DEFAULT_HOURS[DeliverableCategory.CUSTOM]

    def test_all_deliverables_start_as_draft(self):
        plan = {
            "stages": [
                {"id": "s1", "name": "hierarchy", "milestone": 1},
                {"id": "s2", "name": "rcm", "milestone": 2},
            ]
        }
        result = DeliverableTrackingEngine.seed_from_execution_plan(plan)
        for d in result:
            assert d["status"] == "DRAFT"
            assert d["actual_hours"] == 0.0

    def test_empty_plan_returns_empty(self):
        result = DeliverableTrackingEngine.seed_from_execution_plan({})
        assert result == []

    def test_prefix_match_for_stage_names(self):
        """Stage names containing a known key should match (e.g., 'work-packages-review')."""
        plan = {
            "stages": [
                {"id": "s1", "name": "work-packages-review", "milestone": 3},
            ]
        }
        result = DeliverableTrackingEngine.seed_from_execution_plan(plan)
        assert result[0]["category"] == "WORK_PACKAGES"


# ═══════════════════════════════════════════════════════════════════════════
# Constants integrity tests
# ═══════════════════════════════════════════════════════════════════════════

class TestConstants:

    def test_valid_transitions_covers_all_statuses(self):
        for status in DeliverableStatus:
            assert status in VALID_TRANSITIONS

    def test_default_hours_covers_all_categories(self):
        for cat in DeliverableCategory:
            assert cat in DEFAULT_HOURS
            assert DEFAULT_HOURS[cat] > 0

    def test_stage_to_category_values_valid(self):
        for cat in STAGE_TO_CATEGORY.values():
            assert isinstance(cat, DeliverableCategory)
