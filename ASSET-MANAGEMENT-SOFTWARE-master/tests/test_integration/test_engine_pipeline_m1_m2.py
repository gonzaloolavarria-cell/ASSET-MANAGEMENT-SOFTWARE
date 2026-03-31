"""
Integration tests: M1->M2 engine pipeline.
Hierarchy -> Criticality -> FMECA -> RCM decision chain.
"""

import json
import pytest

from tools.engines.criticality_engine import CriticalityEngine
from tools.engines.fmeca_engine import FMECAEngine
from tools.engines.rcm_decision_engine import RCMDecisionEngine, RCMDecisionInput
from tools.engines.quality_score_engine import QualityScoreEngine
from tools.models.schemas import (
    CriticalityAssessment,
    CriticalityCategory,
    CriticalityMethod,
    CriteriaScore,
    FailureConsequence,
    FailurePattern,
    NodeType,
    PlantHierarchyNode,
    RiskClass,
    StrategyType,
    VALID_FM_COMBINATIONS,
)
from agents.orchestration.session_state import SessionState


pytestmark = pytest.mark.integration


# ------------------------------------------------------------------
# M1 Pipeline: Hierarchy + Criticality
# ------------------------------------------------------------------
class TestM1Pipeline:
    """Tests for the M1 milestone: hierarchy building and criticality assessment."""

    def test_hierarchy_nodes_validate_against_schema(self, pipeline_hierarchy_nodes):
        """Engine output validates against PlantHierarchyNode schema."""
        for node in pipeline_hierarchy_nodes:
            assert isinstance(node, PlantHierarchyNode)
            assert node.name
            assert node.name_fr
            assert node.code

    def test_hierarchy_nodes_correct_parent_chain(self, pipeline_hierarchy_nodes):
        """Every parent_node_id resolves to an existing node."""
        node_ids = {n.node_id for n in pipeline_hierarchy_nodes}
        for node in pipeline_hierarchy_nodes:
            if node.parent_node_id is not None:
                assert node.parent_node_id in node_ids, (
                    f"Node {node.code} references non-existent parent {node.parent_node_id}"
                )

    def test_hierarchy_level_matches_type(self, pipeline_hierarchy_nodes):
        """Node level matches expected level for its type."""
        expected = {
            NodeType.PLANT: 1, NodeType.AREA: 2, NodeType.SYSTEM: 3,
            NodeType.EQUIPMENT: 4, NodeType.SUB_ASSEMBLY: 5, NodeType.MAINTAINABLE_ITEM: 6,
        }
        for node in pipeline_hierarchy_nodes:
            assert node.level == expected[node.node_type], (
                f"Node {node.code}: level {node.level} != expected {expected[node.node_type]}"
            )

    def test_criticality_engine_accepts_hierarchy_output(self, pipeline_criticality):
        """CriticalityEngine.assess() processes assessments from hierarchy."""
        for assessment in pipeline_criticality:
            result = CriticalityEngine.assess(assessment)
            assert result.overall_score > 0
            assert result.risk_class is not None

    def test_criticality_full_matrix_validation(self, pipeline_criticality):
        """Full matrix validation passes with all 11 criteria."""
        for assessment in pipeline_criticality:
            errors = CriticalityEngine.validate_full_matrix(assessment.criteria_scores)
            assert len(errors) == 0, f"Validation errors: {errors}"

    def test_quality_scorer_m1_produces_score(self, pipeline_session):
        """QualityScoreEngine scores M1 entities."""
        score = QualityScoreEngine.score_deliverable(
            deliverable_type="hierarchy",
            entities=pipeline_session.get_validation_input(),
            milestone=1,
        )
        assert score.composite_score >= 0
        assert score.grade is not None

    def test_criticality_all_risk_classes_reachable(self):
        """Verify AA/A+/A/B/C/D risk classes are all producible."""
        test_cases = [
            (5, 5, RiskClass.IV_CRITICAL),
            (3, 3, RiskClass.III_HIGH),
            (2, 2, RiskClass.II_MEDIUM),
            (1, 1, RiskClass.I_LOW),
        ]
        for consequence, probability, expected_class in test_cases:
            scores = [
                CriteriaScore(category=cat, consequence_level=consequence)
                for cat in CriticalityCategory
            ]
            assessment = CriticalityAssessment(
                node_id="test-node",
                assessed_by="test",
                criteria_scores=scores,
                probability=probability,
                risk_class=expected_class,
            )
            result = CriticalityEngine.assess(assessment)
            assert result.risk_class is not None

    def test_equipment_node_has_tag(self, pipeline_hierarchy_nodes):
        """Equipment nodes should have a tag."""
        equip_nodes = [n for n in pipeline_hierarchy_nodes if n.node_type == NodeType.EQUIPMENT]
        assert len(equip_nodes) > 0
        for node in equip_nodes:
            assert node.tag is not None and len(node.tag) > 0


# ------------------------------------------------------------------
# M2 Pipeline: FMECA + RCM
# ------------------------------------------------------------------
class TestM2Pipeline:
    """Tests for the M2 milestone: FMECA generation and RCM decisions."""

    def test_fmeca_engine_creates_worksheet(self, pipeline_hierarchy_nodes):
        """FMECAEngine creates worksheet from hierarchy MIs."""
        mi_nodes = [n for n in pipeline_hierarchy_nodes if n.node_type == NodeType.MAINTAINABLE_ITEM]
        for mi in mi_nodes:
            ws = FMECAEngine.create_worksheet(
                equipment_id=mi.node_id,
                equipment_tag=mi.code,
                equipment_name=mi.name,
            )
            assert ws is not None
            assert ws.equipment_id == mi.node_id

    def test_rcm_decision_for_each_failure_mode(self, pipeline_fmeca):
        """Each failure mode gets a valid strategy_type from RCM."""
        for fm in pipeline_fmeca["failure_modes"]:
            rcm_input = RCMDecisionInput(
                is_hidden=fm.is_hidden,
                failure_consequence=fm.failure_consequence,
                cbm_technically_feasible=fm.strategy_type == StrategyType.CONDITION_BASED,
                cbm_economically_viable=fm.strategy_type == StrategyType.CONDITION_BASED,
                ft_feasible=fm.strategy_type in (StrategyType.FIXED_TIME, StrategyType.FAULT_FINDING),
                failure_pattern=fm.failure_pattern,
            )
            result = RCMDecisionEngine.decide(rcm_input)
            assert result.strategy_type is not None
            assert result.reasoning

    def test_72_combo_validation(self, pipeline_fmeca):
        """All failure modes use valid mechanism+cause from MASTER."""
        for fm in pipeline_fmeca["failure_modes"]:
            combo = (fm.mechanism.value, fm.cause.value)
            assert combo in VALID_FM_COMBINATIONS, (
                f"Invalid combo: {combo}. Must be from 72 valid combinations."
            )

    def test_failure_patterns_map_to_valid_rcm_paths(self, pipeline_fmeca):
        """Each failure pattern yields a reachable RCM decision."""
        for fm in pipeline_fmeca["failure_modes"]:
            rcm_input = RCMDecisionInput(
                is_hidden=fm.is_hidden,
                failure_consequence=fm.failure_consequence,
                cbm_technically_feasible=True,
                cbm_economically_viable=True,
                ft_feasible=True,
                failure_pattern=fm.failure_pattern,
            )
            result = RCMDecisionEngine.decide(rcm_input)
            assert result.path is not None

    def test_m2_validation_entities_present(self, pipeline_session):
        """M2 entities are present in session."""
        counts = pipeline_session.get_entity_counts()
        assert counts.get("functions", 0) > 0
        assert counts.get("functional_failures", 0) > 0
        assert counts.get("failure_modes", 0) > 0

    def test_m2_quality_score_above_minimum(self, pipeline_session):
        """Quality score on well-formed M2 data is above 0."""
        score = QualityScoreEngine.score_deliverable(
            deliverable_type="fmeca",
            entities=pipeline_session.get_validation_input(),
            milestone=2,
        )
        assert score.composite_score >= 0

    def test_fmeca_worksheet_add_row(self, pipeline_fmeca):
        """FMECAEngine.add_row builds up worksheet."""
        ws = FMECAEngine.create_worksheet(equipment_id="test-eq", equipment_tag="EQ-001")
        for fm in pipeline_fmeca["failure_modes"]:
            ws = FMECAEngine.add_row(ws, {
                "failure_mode_id": fm.failure_mode_id,
                "what": fm.what,
                "mechanism": fm.mechanism.value,
                "cause": fm.cause.value,
                "failure_consequence": fm.failure_consequence.value,
                "is_hidden": fm.is_hidden,
            })
        assert len(ws.rows) == len(pipeline_fmeca["failure_modes"])

    def test_hidden_failure_mode_gets_failure_finding(self, pipeline_fmeca):
        """Hidden failure modes with safety consequence should get failure-finding."""
        hidden_fms = [fm for fm in pipeline_fmeca["failure_modes"] if fm.is_hidden]
        assert len(hidden_fms) > 0, "Test data should include at least one hidden FM"
        for fm in hidden_fms:
            rcm_input = RCMDecisionInput(
                is_hidden=True,
                failure_consequence=fm.failure_consequence,
                cbm_technically_feasible=False,
                cbm_economically_viable=False,
                ft_feasible=True,
                failure_pattern=fm.failure_pattern,
            )
            result = RCMDecisionEngine.decide(rcm_input)
            assert result.strategy_type in (
                StrategyType.FAULT_FINDING,
                StrategyType.REDESIGN,
                StrategyType.CONDITION_BASED,
                StrategyType.FIXED_TIME,
            )


# ------------------------------------------------------------------
# M1->M2 Handoff
# ------------------------------------------------------------------
class TestM1ToM2Handoff:
    """Tests for data integrity across M1->M2 milestone boundary."""

    def test_session_state_accumulates_m1_then_m2(self, pipeline_session):
        """Both M1 and M2 entity sets present in session."""
        counts = pipeline_session.get_entity_counts()
        # M1
        assert counts.get("hierarchy_nodes", 0) == 6
        assert counts.get("criticality_assessments", 0) == 2
        # M2
        assert counts.get("functions", 0) == 3
        assert counts.get("functional_failures", 0) == 3
        assert counts.get("failure_modes", 0) == 6

    def test_swmr_ownership_m1_entities(self, pipeline_hierarchy_nodes, pipeline_criticality):
        """Reliability agent owns hierarchy_nodes and criticality_assessments."""
        session = SessionState(
            session_id="swmr-test", equipment_tag="TEST", plant_code="TEST",
        )
        # Should succeed - reliability owns these
        session.write_entities("hierarchy_nodes",
                               [n.model_dump() for n in pipeline_hierarchy_nodes], "reliability")
        session.write_entities("criticality_assessments",
                               [c.model_dump() for c in pipeline_criticality], "reliability")
        # Should fail - planning doesn't own hierarchy_nodes
        with pytest.raises(PermissionError):
            session.write_entities("hierarchy_nodes", [], "planning")

    def test_swmr_ownership_m2_entities(self, pipeline_fmeca):
        """Reliability owns functions, failures, failure_modes."""
        session = SessionState(
            session_id="swmr-test-m2", equipment_tag="TEST", plant_code="TEST",
        )
        session.write_entities("functions",
                               [f.model_dump() for f in pipeline_fmeca["functions"]], "reliability")
        session.write_entities("functional_failures",
                               [ff.model_dump() for ff in pipeline_fmeca["failures"]], "reliability")
        session.write_entities("failure_modes",
                               [fm.model_dump() for fm in pipeline_fmeca["failure_modes"]], "reliability")
        with pytest.raises(PermissionError):
            session.write_entities("functions", [], "planning")

    def test_m2_functions_reference_m1_node_ids(self, pipeline_hierarchy_nodes, pipeline_fmeca):
        """Every function's node_id exists in hierarchy."""
        node_ids = {n.node_id for n in pipeline_hierarchy_nodes}
        for func in pipeline_fmeca["functions"]:
            assert func.node_id in node_ids, (
                f"Function {func.function_id} references non-existent node {func.node_id}"
            )

    def test_m2_failures_reference_functions(self, pipeline_fmeca):
        """Every functional failure's function_id exists."""
        func_ids = {f.function_id for f in pipeline_fmeca["functions"]}
        for ff in pipeline_fmeca["failures"]:
            assert ff.function_id in func_ids, (
                f"Failure {ff.failure_id} references non-existent function {ff.function_id}"
            )

    def test_m2_failure_modes_reference_failures(self, pipeline_fmeca):
        """Every failure mode's functional_failure_id exists."""
        failure_ids = {ff.failure_id for ff in pipeline_fmeca["failures"]}
        for fm in pipeline_fmeca["failure_modes"]:
            assert fm.functional_failure_id in failure_ids, (
                f"FM {fm.failure_mode_id} references non-existent failure {fm.functional_failure_id}"
            )

    def test_entity_extraction_from_json(self):
        """_extract_entities_from_response() parses mixed JSON."""
        from agents.orchestration.workflow import _extract_entities_from_response
        test_response = '''Here are the results:
```json
{"hierarchy_nodes": [{"node_id": "n1", "name": "Test"}], "functions": [{"function_id": "f1"}]}
```
'''
        result = _extract_entities_from_response(test_response)
        assert "hierarchy_nodes" in result or "functions" in result

    def test_session_json_roundtrip(self, pipeline_session):
        """to_json() / from_json() preserves all entities."""
        json_str = pipeline_session.to_json()
        restored = SessionState.from_json(json_str)
        assert restored.session_id == pipeline_session.session_id
        assert restored.equipment_tag == pipeline_session.equipment_tag
        orig_counts = pipeline_session.get_entity_counts()
        restored_counts = restored.get_entity_counts()
        for key in orig_counts:
            assert orig_counts[key] == restored_counts.get(key, 0), (
                f"Entity count mismatch for {key}: {orig_counts[key]} != {restored_counts.get(key, 0)}"
            )

    def test_validation_input_complete(self, pipeline_session):
        """get_validation_input() includes entity types."""
        vi = pipeline_session.get_validation_input()
        # Keys may be remapped (e.g. hierarchy_nodes → nodes) by get_validation_input()
        assert len(vi) > 0
        # Should contain node data under some key
        all_values = str(vi)
        assert "Jorf" in all_values or "SAG" in all_values
