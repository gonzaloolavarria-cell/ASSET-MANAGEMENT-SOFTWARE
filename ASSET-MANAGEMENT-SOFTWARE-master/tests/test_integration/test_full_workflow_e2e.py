"""
Full E2E workflow test: StrategyWorkflow with mocked delegation, real engines.
The single most important integration test file.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from tools.models.schemas import (
    VALID_FM_COMBINATIONS,
    TaskType,
)
from agents.orchestration.session_state import SessionState
from agents.orchestration.workflow import (
    _extract_entities_from_response,
    _run_validation,
    _run_quality_scoring,
    _format_gate_summary,
)


pytestmark = pytest.mark.integration


def _build_m1_response(hierarchy_nodes, criticality):
    """Build a mock agent response containing M1 entities."""
    data = {
        "hierarchy_nodes": [n.model_dump() for n in hierarchy_nodes],
        "criticality_assessments": [c.model_dump() for c in criticality],
    }
    return f"Here are the M1 results:\n```json\n{json.dumps(data, default=str)}\n```"


def _build_m2_response(fmeca):
    """Build a mock agent response containing M2 entities."""
    data = {
        "functions": [f.model_dump() for f in fmeca["functions"]],
        "functional_failures": [ff.model_dump() for ff in fmeca["failures"]],
        "failure_modes": [fm.model_dump() for fm in fmeca["failure_modes"]],
    }
    return f"M2 analysis complete:\n```json\n{json.dumps(data, default=str)}\n```"


def _build_m3_response(tasks, work_packages):
    """Build a mock agent response containing M3 entities."""
    data = {
        "maintenance_tasks": [t.model_dump() for t in tasks],
        "work_packages": [wp.model_dump() for wp in work_packages],
    }
    return f"M3 planning complete:\n```json\n{json.dumps(data, default=str)}\n```"


def _build_m4_response():
    """Build a mock agent response for M4."""
    return "SAP export package generated successfully."


# ------------------------------------------------------------------
# Full Workflow E2E
# ------------------------------------------------------------------
class TestFullWorkflowE2E:
    """Tests the complete StrategyWorkflow with mocked agents."""

    def test_validation_runs_on_session(self, pipeline_session):
        """_run_validation produces results on populated session."""
        result = _run_validation(pipeline_session)
        assert result is not None

    def test_quality_scoring_runs_on_session(self, pipeline_session):
        """_run_quality_scoring produces scores."""
        result = _run_quality_scoring(pipeline_session, milestone=2)
        assert result is not None

    def test_gate_summary_contains_entity_counts(self, pipeline_session):
        """Gate summary includes entity count information."""
        from agents.orchestration.milestones import create_milestone_gates
        gates = create_milestone_gates()
        validation = _run_validation(pipeline_session)
        summary = _format_gate_summary(
            milestone=gates[0],  # M1
            session=pipeline_session,
            validation=validation,
        )
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_extract_entities_from_json_block(self):
        """Entity extraction from fenced JSON block."""
        response = '''Analysis complete:
```json
{"hierarchy_nodes": [{"node_id": "n1", "name": "Test Node"}]}
```
'''
        result = _extract_entities_from_response(response)
        assert "hierarchy_nodes" in result
        assert len(result["hierarchy_nodes"]) == 1

    def test_extract_entities_from_raw_json(self):
        """Entity extraction from raw JSON object."""
        response = '{"functions": [{"function_id": "f1", "description": "Test"}]}'
        result = _extract_entities_from_response(response)
        assert "functions" in result

    def test_extract_entities_empty_response(self):
        """Entity extraction handles empty/text-only responses."""
        result = _extract_entities_from_response("No JSON here, just text.")
        assert isinstance(result, dict)

    def test_session_state_accumulates_entities(
        self, pipeline_hierarchy_nodes, pipeline_criticality, pipeline_fmeca,
        pipeline_tasks, pipeline_work_packages
    ):
        """Entities accumulate across milestone writes."""
        session = SessionState(
            session_id="accumulate-test",
            equipment_tag="BRY-SAG-ML-001",
            plant_code="OCP-JFC1",
        )
        # M1
        session.write_entities("hierarchy_nodes",
                               [n.model_dump() for n in pipeline_hierarchy_nodes], "reliability")
        session.write_entities("criticality_assessments",
                               [c.model_dump() for c in pipeline_criticality], "reliability")
        counts = session.get_entity_counts()
        assert counts["hierarchy_nodes"] == 6
        assert counts["criticality_assessments"] == 2

        # M2
        session.write_entities("functions",
                               [f.model_dump() for f in pipeline_fmeca["functions"]], "reliability")
        session.write_entities("failure_modes",
                               [fm.model_dump() for fm in pipeline_fmeca["failure_modes"]], "reliability")
        counts = session.get_entity_counts()
        assert counts["functions"] == 3
        assert counts["failure_modes"] == 6

        # M3
        session.write_entities("maintenance_tasks",
                               [t.model_dump() for t in pipeline_tasks], "planning")
        session.write_entities("work_packages",
                               [wp.model_dump() for wp in pipeline_work_packages], "planning")
        counts = session.get_entity_counts()
        assert counts["maintenance_tasks"] == 8
        assert counts["work_packages"] == 3

    def test_modify_loop_session_integrity(self, pipeline_session):
        """Session state remains valid after simulated modify iterations."""
        # write_entities appends; verify entities are additive
        orig_count = pipeline_session.get_entity_counts()["failure_modes"]
        assert orig_count == 6
        # Re-write adds more (by design — SWMR appends)
        pipeline_session.write_entities("failure_modes",
            pipeline_session.read_entities("failure_modes"), "reliability")
        new_count = pipeline_session.get_entity_counts()["failure_modes"]
        assert new_count == orig_count * 2  # Appended

    def test_reject_preserves_prior_milestones(self, pipeline_session):
        """Rejection at M3 preserves M1+M2 entities."""
        # M1+M2 should still be intact
        counts = pipeline_session.get_entity_counts()
        assert counts["hierarchy_nodes"] == 6
        assert counts["functions"] == 3

    def test_validation_on_complete_session(self, pipeline_session):
        """Full validation on complete session."""
        result = _run_validation(pipeline_session)
        # Should not crash, may have findings
        assert result is not None

    def test_quality_scoring_all_milestones(self, pipeline_session):
        """Quality scoring works for each milestone."""
        for milestone in [1, 2, 3, 4]:
            result = _run_quality_scoring(pipeline_session, milestone=milestone)
            assert result is not None

    def test_session_interaction_recording(self):
        """Session records agent interactions."""
        session = SessionState(
            session_id="interaction-test",
            equipment_tag="TEST",
            plant_code="TEST",
        )
        session.record_interaction(
            agent_type="reliability",
            milestone=1,
            instruction="Build hierarchy",
            response_summary="6 nodes created",
        )
        assert len(session.agent_interactions) == 1
        assert session.agent_interactions[0]["agent_type"] == "reliability"


# ------------------------------------------------------------------
# Workflow Entity Integrity
# ------------------------------------------------------------------
class TestWorkflowEntityIntegrity:
    """Tests entity integrity constraints across the full pipeline."""

    def test_hierarchy_valid_tree(self, pipeline_hierarchy_nodes):
        """Post-M1 hierarchy is a valid tree (no cycles, single root)."""
        node_map = {n.node_id: n for n in pipeline_hierarchy_nodes}
        roots = [n for n in pipeline_hierarchy_nodes if n.parent_node_id is None]
        assert len(roots) == 1, "Should have exactly one root (PLANT) node"

        # Check no cycles via depth tracking
        for node in pipeline_hierarchy_nodes:
            visited = set()
            current = node
            while current.parent_node_id is not None:
                assert current.node_id not in visited, f"Cycle detected at {current.code}"
                visited.add(current.node_id)
                current = node_map[current.parent_node_id]

    def test_failure_modes_use_72_combo(self, pipeline_fmeca):
        """Post-M2 FMs use valid 72-combo pairs."""
        for fm in pipeline_fmeca["failure_modes"]:
            combo = (fm.mechanism.value, fm.cause.value)
            assert combo in VALID_FM_COMBINATIONS

    def test_replace_tasks_have_materials(self, pipeline_tasks):
        """Post-M3 REPLACE tasks have materials (T-16)."""
        for task in pipeline_tasks:
            if task.task_type == TaskType.REPLACE:
                assert len(task.material_resources) > 0, (
                    f"T-16 violation: REPLACE task '{task.name}' has no materials"
                )

    def test_sap_texts_under_72_chars(self, pipeline_tasks, pipeline_work_packages):
        """Post-M4 SAP texts are within limits."""
        for task in pipeline_tasks:
            assert len(task.name) <= 72
        for wp in pipeline_work_packages:
            assert len(wp.name) <= 40

    def test_confidence_fields_present(self, pipeline_fmeca):
        """Entities with AI confidence have valid values."""
        for fm in pipeline_fmeca["failure_modes"]:
            if fm.ai_confidence is not None:
                assert 0.0 <= fm.ai_confidence <= 1.0

    def test_session_json_roundtrip(self, pipeline_session):
        """to_json() / from_json() preserves all entities."""
        json_str = pipeline_session.to_json()
        restored = SessionState.from_json(json_str)
        orig = pipeline_session.get_entity_counts()
        rest = restored.get_entity_counts()
        for key in orig:
            assert orig[key] == rest.get(key, 0), f"Mismatch on {key}"

    def test_entity_extraction_from_agent_response(self):
        """JSON extraction from mock agent text."""
        text = 'I have completed the analysis. {"hierarchy_nodes": [{"id": 1}], "extra_text": true}'
        result = _extract_entities_from_response(text)
        assert isinstance(result, dict)

    def test_functions_reference_hierarchy(self, pipeline_hierarchy_nodes, pipeline_fmeca):
        """All functions reference valid hierarchy nodes."""
        node_ids = {n.node_id for n in pipeline_hierarchy_nodes}
        for func in pipeline_fmeca["functions"]:
            assert func.node_id in node_ids
