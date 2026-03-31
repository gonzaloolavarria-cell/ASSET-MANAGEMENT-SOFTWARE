"""Integration tests for Quality Scorer with workflow and session state — Phase 9.

Tests that quality scoring integrates correctly with:
- Gate summary formatting
- Session state storage
- Workflow threshold behavior
"""

import pytest

from agents.orchestration.session_state import SessionState, ENTITY_OWNERSHIP
from agents.orchestration.workflow import (
    _format_gate_summary,
    _run_quality_scoring,
    _run_validation,
)
from agents.orchestration.milestones import (
    MilestoneGate,
    MilestoneStatus,
    ValidationSummary,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_entities():
    """Minimal valid entities for milestone 1."""
    return {
        "hierarchy_nodes": [
            {"node_id": "N1", "name": "Plant A", "name_fr": "Usine A", "node_type": "PLANT", "level": 1, "parent_node_id": None},
            {"node_id": "N2", "name": "Area 1", "name_fr": "Zone 1", "node_type": "AREA", "level": 2, "parent_node_id": "N1"},
            {"node_id": "N3", "name": "System 1", "name_fr": "Système 1", "node_type": "SYSTEM", "level": 3, "parent_node_id": "N2"},
            {"node_id": "N4", "name": "Equip 1", "name_fr": "Équip 1", "node_type": "EQUIPMENT", "level": 4, "parent_node_id": "N3", "metadata": {"manufacturer": "ABB", "model": "M100"}},
            {"node_id": "N5", "name": "Motor", "name_fr": "Moteur", "node_type": "MAINTAINABLE_ITEM", "level": 5, "parent_node_id": "N4", "component_lib_ref": "CL-001"},
        ],
        "criticality_assessments": [
            {
                "assessment_id": "CA1", "node_id": "N4", "assessed_at": "2026-01-01",
                "assessed_by": "Analyst", "method": "FULL_MATRIX", "probability": 3,
                "overall_score": 35.0, "risk_class": "III_HIGH",
                "criteria_scores": [{"category": "SAFETY", "consequence_level": 3}],
            },
            {
                "assessment_id": "CA2", "node_id": "N3", "assessed_at": "2026-01-01",
                "assessed_by": "Analyst", "method": "FULL_MATRIX", "probability": 2,
                "overall_score": 20.0, "risk_class": "II_MEDIUM",
                "criteria_scores": [{"category": "SAFETY", "consequence_level": 2}],
            },
        ],
    }


def _make_gate():
    """Create a milestone 1 gate."""
    gate = MilestoneGate(
        number=1,
        name="Hierarchy Decomposition",
        description="Build equipment hierarchy and assess criticality",
        required_agents=["reliability"],
        required_entities=["hierarchy_nodes", "criticality_assessments"],
    )
    return gate


def _make_session_with_entities():
    session = SessionState(session_id="test-session-001")
    for key, data in _make_entities().items():
        if key in ENTITY_OWNERSHIP:
            owner = ENTITY_OWNERSHIP[key].value
            session.write_entities(key, data, owner)
    return session


# ---------------------------------------------------------------------------
# Tests: Gate summary includes quality score
# ---------------------------------------------------------------------------

class TestGateSummaryQualityScore:
    def test_quality_score_section_present(self):
        """Gate summary should include quality score section."""
        gate = _make_gate()
        session = _make_session_with_entities()
        validation = ValidationSummary()
        quality_report = _run_quality_scoring(session, 1)

        summary = _format_gate_summary(gate, session, validation, quality_report=quality_report)

        assert "Quality Score:" in summary
        assert "%" in summary
        assert "Grade:" in summary

    def test_quality_score_absent_when_none(self):
        """Gate summary should not include quality section when report is None."""
        gate = _make_gate()
        session = _make_session_with_entities()
        validation = ValidationSummary()

        summary = _format_gate_summary(gate, session, validation, quality_report=None)

        assert "Quality Score:" not in summary

    def test_quality_report_shows_per_deliverable(self):
        """Gate summary should show per-deliverable scores."""
        gate = _make_gate()
        session = _make_session_with_entities()
        validation = ValidationSummary()
        quality_report = _run_quality_scoring(session, 1)

        summary = _format_gate_summary(gate, session, validation, quality_report=quality_report)

        assert "hierarchy:" in summary
        assert "criticality:" in summary


# ---------------------------------------------------------------------------
# Tests: Quality scoring function
# ---------------------------------------------------------------------------

class TestQualityScoring:
    def test_run_quality_scoring_returns_dict(self):
        session = _make_session_with_entities()
        report = _run_quality_scoring(session, 1)
        assert isinstance(report, dict)
        assert "overall_score" in report
        assert "deliverable_scores" in report

    def test_run_quality_scoring_with_threshold(self):
        session = _make_session_with_entities()
        report = _run_quality_scoring(session, 1, pass_threshold=0.0)
        assert report.get("passes_gate") is True

    def test_run_quality_scoring_empty_session(self):
        session = SessionState(session_id="empty")
        report = _run_quality_scoring(session, 1)
        # Should return dict (possibly empty or with 0 score)
        assert isinstance(report, dict)


# ---------------------------------------------------------------------------
# Tests: Session state quality_scores entity
# ---------------------------------------------------------------------------

class TestSessionStateQualityScores:
    def test_quality_scores_entity_registered(self):
        assert "quality_scores" in ENTITY_OWNERSHIP

    def test_quality_scores_writable_by_orchestrator(self):
        session = SessionState(session_id="test")
        session.write_entities("quality_scores", [{"score": 95.0}], "orchestrator")
        assert len(session.quality_scores) == 1

    def test_quality_scores_not_writable_by_reliability(self):
        session = SessionState(session_id="test")
        with pytest.raises(PermissionError):
            session.write_entities("quality_scores", [{"score": 95.0}], "reliability")

    def test_quality_scores_property_accessor(self):
        session = SessionState(session_id="test")
        assert session.quality_scores == []
        session.write_entities("quality_scores", [{"score": 80.0}], "orchestrator")
        assert len(session.quality_scores) == 1

    def test_quality_scores_serialization(self):
        session = SessionState(session_id="test")
        session.write_entities("quality_scores", [{"milestone": 1, "score": 92.0}], "orchestrator")
        json_str = session.to_json()
        restored = SessionState.from_json(json_str)
        assert len(restored.quality_scores) == 1
        assert restored.quality_scores[0]["score"] == 92.0


# ---------------------------------------------------------------------------
# Tests: Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    def test_entity_counts_includes_quality_scores(self):
        session = _make_session_with_entities()
        counts = session.get_entity_counts()
        assert "quality_scores" in counts
        assert counts["quality_scores"] == 0

    def test_existing_validation_still_works(self):
        """Existing get_validation_input() should not include quality_scores."""
        session = _make_session_with_entities()
        vi = session.get_validation_input()
        # quality_scores is not a validation entity
        assert "quality_scores" not in vi
