"""Tests for Quality Score Engine — Phase 9.

Tests the core engine: deterministic scoring, grade boundaries, config loading,
session-level aggregation.
"""

import pytest
import yaml
from pathlib import Path

from tools.engines.quality_score_engine import (
    QualityScoreEngine,
    MILESTONE_DELIVERABLES,
    STRATEGY_REGISTRY,
    _grade_from_score,
)
from tools.models.schemas import (
    DeliverableQualityScore,
    QualityDimension,
    QualityGrade,
    QualityScoreDimension,
    SessionQualityReport,
)


# ---------------------------------------------------------------------------
# Fixtures: synthetic data for a complete, correct deliverable set
# ---------------------------------------------------------------------------

def _make_hierarchy_nodes(count=5):
    """Create a complete 5-node hierarchy (PLANT→AREA→SYSTEM→EQUIPMENT→MI)."""
    return [
        {"node_id": "N1", "name": "Plant A", "name_fr": "Usine A", "node_type": "PLANT", "level": 1, "parent_node_id": None},
        {"node_id": "N2", "name": "Area 1", "name_fr": "Zone 1", "node_type": "AREA", "level": 2, "parent_node_id": "N1"},
        {"node_id": "N3", "name": "Conveyor System", "name_fr": "Système Convoyeur", "node_type": "SYSTEM", "level": 3, "parent_node_id": "N2"},
        {"node_id": "N4", "name": "Belt Conveyor 001", "name_fr": "Convoyeur à Bande 001", "node_type": "EQUIPMENT", "level": 4, "parent_node_id": "N3", "metadata": {"manufacturer": "Metso", "model": "CV-200"}},
        {"node_id": "N5", "name": "Drive Motor", "name_fr": "Moteur d'Entraînement", "node_type": "MAINTAINABLE_ITEM", "level": 5, "parent_node_id": "N4", "component_lib_ref": "CL-MTR-001"},
    ]


def _make_criticality_assessments():
    return [
        {
            "assessment_id": "CA1", "node_id": "N4", "assessed_at": "2026-01-15",
            "assessed_by": "J. Doe", "method": "FULL_MATRIX", "probability": 3,
            "overall_score": 45.0, "risk_class": "III_HIGH",
            "criteria_scores": [{"category": "SAFETY", "consequence_level": 4}],
        },
        {
            "assessment_id": "CA2", "node_id": "N3", "assessed_at": "2026-01-15",
            "assessed_by": "J. Doe", "method": "FULL_MATRIX", "probability": 2,
            "overall_score": 20.0, "risk_class": "II_MEDIUM",
            "criteria_scores": [{"category": "SAFETY", "consequence_level": 2}],
        },
    ]


def _make_functions():
    return [{"function_id": "F1", "node_id": "N5", "function_type": "PRIMARY", "description": "Drive belt"}]


def _make_functional_failures():
    return [{"failure_id": "FF1", "function_id": "F1", "failure_type": "TOTAL", "description": "Cannot drive"}]


def _make_failure_modes():
    return [
        {
            "failure_mode_id": "FM1", "functional_failure_id": "FF1",
            "what": "Motor winding burns out",
            "mechanism": "OVERHEATS/MELTS", "cause": "OVERLOAD",
            "failure_pattern": "E_RANDOM", "failure_consequence": "EVIDENT_OPERATIONAL",
            "is_hidden": False, "strategy_type": "CONDITION_BASED",
        },
    ]


def _make_tasks():
    return [
        {
            "task_id": "T1", "name": "Check motor temperature weekly",
            "task_type": "CHECK", "failure_mode_id": "FM1",
            "frequency_value": 7, "frequency_unit": "DAYS", "constraint": "ONLINE",
            "access_time_hours": 0, "acceptable_limits": "< 80°C",
            "conditional_comments": "If > 80°C, schedule inspection",
            "labour_resources": [{"specialty": "ELECTRICIAN", "quantity": 1, "hours_per_person": 0.5}],
        },
    ]


def _make_work_packages():
    return [
        {
            "work_package_id": "WP1", "name": "WEEKLY BELT CONVEYOR ONLINE",
            "code": "WP-001", "node_id": "N4",
            "frequency_value": 7, "frequency_unit": "DAYS",
            "constraint": "ONLINE", "work_package_type": "STANDALONE",
            "allocated_tasks": [{"task_id": "T1", "order": 1, "operation_number": 10}],
        },
    ]


def _make_sap_package():
    return {
        "package_id": "SAP1", "plant_code": "OCP-JFC", "generated_at": "2026-01-20",
        "status": "GENERATED",
        "maintenance_plan": {"plan_id": "MP1", "description": "Belt Conveyor PM Plan", "cycle_value": 7, "cycle_unit": "DAYS"},
        "maintenance_items": [{"item_id": "MI1", "func_loc": "N4", "task_list_ref": "TL1", "priority": 3}],
        "task_lists": [{"task_list_id": "TL1", "operations": [{"operation_number": 10, "work_centre": "ELEC", "short_text": "Check motor temperature"}]}],
    }


def _make_complete_entities():
    """Build a complete set of entities for all milestones."""
    return {
        "hierarchy_nodes": _make_hierarchy_nodes(),
        "criticality_assessments": _make_criticality_assessments(),
        "functions": _make_functions(),
        "functional_failures": _make_functional_failures(),
        "failure_modes": _make_failure_modes(),
        "maintenance_tasks": _make_tasks(),
        "work_packages": _make_work_packages(),
        "sap_upload_package": _make_sap_package(),
    }


# ---------------------------------------------------------------------------
# Tests: Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_input_same_score(self):
        """Same input always produces identical score."""
        entities = _make_complete_entities()
        score1 = QualityScoreEngine.score_deliverable("hierarchy", entities, 1)
        score2 = QualityScoreEngine.score_deliverable("hierarchy", entities, 1)
        assert score1.composite_score == score2.composite_score
        assert len(score1.dimensions) == len(score2.dimensions)

    def test_session_score_deterministic(self):
        entities = _make_complete_entities()
        r1 = QualityScoreEngine.score_session(entities, 4, "S1")
        r2 = QualityScoreEngine.score_session(entities, 4, "S1")
        assert r1.overall_score == r2.overall_score


# ---------------------------------------------------------------------------
# Tests: Score ranges
# ---------------------------------------------------------------------------

class TestScoreRanges:
    def test_complete_deliverable_above_threshold(self):
        """A complete, correct hierarchy should score high."""
        entities = _make_complete_entities()
        score = QualityScoreEngine.score_deliverable("hierarchy", entities, 1)
        assert score.composite_score > 70.0  # Well-formed data

    def test_empty_entities_zero_score(self):
        """Empty entities produce 0.0 score."""
        score = QualityScoreEngine.score_deliverable("hierarchy", {}, 1)
        assert score.composite_score == 0.0

    def test_incomplete_deliverable_below_70(self):
        """Missing required fields produce score < 70."""
        # Nodes: empty names, no name_fr, orphan refs, MI without component_lib_ref
        entities = {
            "hierarchy_nodes": [
                {"node_id": "N1", "name": "", "node_type": "PLANT", "level": 1},
                {"node_id": "N2", "name": "", "node_type": "EQUIPMENT", "level": 4, "parent_node_id": "ORPHAN"},
                {"node_id": "N3", "name": "", "node_type": "MAINTAINABLE_ITEM", "level": 5, "parent_node_id": "ORPHAN"},
            ],
        }
        score = QualityScoreEngine.score_deliverable("hierarchy", entities, 1)
        assert score.composite_score < 70.0

    def test_severe_errors_below_50(self):
        """Structural errors produce score < 50."""
        # Orphan nodes, invalid levels, missing everything
        entities = {
            "hierarchy_nodes": [
                {"node_id": "N1", "name": "Bad", "node_type": "EQUIPMENT", "level": 99, "parent_node_id": "NONEXISTENT"},
            ],
        }
        score = QualityScoreEngine.score_deliverable("hierarchy", entities, 1)
        assert score.composite_score < 50.0


# ---------------------------------------------------------------------------
# Tests: Dimensions
# ---------------------------------------------------------------------------

class TestDimensions:
    def test_each_dimension_produces_score(self):
        entities = _make_complete_entities()
        score = QualityScoreEngine.score_deliverable("hierarchy", entities, 1)
        dims = {d.dimension for d in score.dimensions}
        # Should have at least the 6 core dimensions (no intent alignment when no profile)
        expected = {
            QualityDimension.TECHNICAL_ACCURACY,
            QualityDimension.COMPLETENESS,
            QualityDimension.CONSISTENCY,
            QualityDimension.FORMAT,
            QualityDimension.ACTIONABILITY,
            QualityDimension.TRACEABILITY,
        }
        assert expected.issubset(dims)

    def test_intent_alignment_added_when_profile_present(self):
        entities = _make_complete_entities()
        context = {"intent_profile": {"naming": "ALL_CAPS", "language": "fr"}}
        score = QualityScoreEngine.score_deliverable("hierarchy", entities, 1, context=context)
        dims = {d.dimension for d in score.dimensions}
        assert QualityDimension.INTENT_ALIGNMENT in dims


# ---------------------------------------------------------------------------
# Tests: Grade boundaries
# ---------------------------------------------------------------------------

class TestGrades:
    @pytest.mark.parametrize("score,expected", [
        (95.0, QualityGrade.A),
        (91.0, QualityGrade.A),
        (90.9, QualityGrade.B),
        (80.0, QualityGrade.B),
        (79.9, QualityGrade.C),
        (70.0, QualityGrade.C),
        (69.9, QualityGrade.D),
        (50.0, QualityGrade.D),
        (49.9, QualityGrade.F),
        (0.0, QualityGrade.F),
    ])
    def test_grade_boundary(self, score, expected):
        assert _grade_from_score(score) == expected


# ---------------------------------------------------------------------------
# Tests: Config loading
# ---------------------------------------------------------------------------

class TestConfig:
    def test_config_loads(self):
        cfg = QualityScoreEngine.load_config()
        assert "default_weights" in cfg
        assert "thresholds" in cfg

    def test_weights_sum_approximately_one(self):
        cfg = QualityScoreEngine.load_config()
        default = cfg.get("default_weights", {})
        total = sum(v for v in default.values() if isinstance(v, (int, float)))
        assert abs(total - 1.0) < 0.01

    def test_deliverable_overrides_applied(self):
        weights = QualityScoreEngine.get_weights("fmeca")
        assert weights.get("technical_accuracy") == 0.35

    def test_weights_with_intent(self):
        weights = QualityScoreEngine.get_weights("hierarchy", has_intent=True)
        assert weights.get("intent_alignment", 0) > 0


# ---------------------------------------------------------------------------
# Tests: Session quality report
# ---------------------------------------------------------------------------

class TestSessionReport:
    def test_session_aggregation(self):
        entities = _make_complete_entities()
        report = QualityScoreEngine.score_session(entities, 4, "S1")
        assert isinstance(report, SessionQualityReport)
        assert report.session_id == "S1"
        assert len(report.deliverable_scores) > 0
        assert report.overall_score >= 0.0

    def test_milestone_1_scores_hierarchy_and_criticality(self):
        entities = _make_complete_entities()
        report = QualityScoreEngine.score_session(entities, 1, "S1")
        types = {s.deliverable_type for s in report.deliverable_scores}
        assert "hierarchy" in types
        assert "criticality" in types
        assert "fmeca" not in types

    def test_milestone_4_scores_all(self):
        entities = _make_complete_entities()
        report = QualityScoreEngine.score_session(entities, 4, "S1")
        types = {s.deliverable_type for s in report.deliverable_scores}
        assert types == {"hierarchy", "criticality", "fmeca", "tasks", "work_packages", "sap_upload"}

    def test_passes_gate_when_above_threshold(self):
        entities = _make_complete_entities()
        report = QualityScoreEngine.score_session(entities, 1, "S1", pass_threshold=0.0)
        assert report.passes_gate is True

    def test_fails_gate_when_below_threshold(self):
        report = QualityScoreEngine.score_session({}, 1, "S1", pass_threshold=91.0)
        assert report.passes_gate is False


# ---------------------------------------------------------------------------
# Tests: Strategy registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_all_strategies_registered(self):
        expected = {"hierarchy", "criticality", "fmeca", "tasks", "work_packages", "sap_upload"}
        assert set(STRATEGY_REGISTRY.keys()) == expected

    def test_invalid_deliverable_raises(self):
        with pytest.raises(ValueError, match="No scoring strategy"):
            QualityScoreEngine.score_deliverable("nonexistent", {}, 1)

    def test_milestone_deliverables_complete(self):
        all_types = set()
        for m_types in MILESTONE_DELIVERABLES.values():
            all_types.update(m_types)
        assert all_types == set(STRATEGY_REGISTRY.keys())
