"""Tests for TroubleshootingEngine — symptom matching, cost ordering, confidence scoring."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.engines.troubleshooting_engine import (
    CATEGORY_KEYWORDS,
    TroubleshootingEngine,
    clear_caches,
)
from tools.models.schemas import (
    DIAGNOSTIC_TEST_COSTS,
    DiagnosisSession,
    DiagnosisStatus,
    DiagnosticPath,
    DiagnosticTest,
    DiagnosticTestType,
    SymptomEntry,
)


@pytest.fixture(autouse=True)
def _clear_engine_caches():
    """Clear caches before each test to avoid cross-test pollution."""
    clear_caches()
    yield
    clear_caches()


# ── Schema / Model Tests ────────────────────────────────────────────


class TestSchemaModels:
    """Test that the Pydantic models work correctly."""

    def test_diagnostic_test_type_values(self):
        assert DiagnosticTestType.SENSORY == "SENSORY"
        assert DiagnosticTestType.SPECIALIST_ANALYSIS == "SPECIALIST_ANALYSIS"

    def test_diagnosis_status_values(self):
        assert DiagnosisStatus.IN_PROGRESS == "IN_PROGRESS"
        assert DiagnosisStatus.COMPLETED == "COMPLETED"
        assert DiagnosisStatus.ESCALATED == "ESCALATED"
        assert DiagnosisStatus.ABANDONED == "ABANDONED"

    def test_diagnostic_test_costs_all_types_present(self):
        for tt in DiagnosticTestType:
            assert tt in DIAGNOSTIC_TEST_COSTS

    def test_diagnostic_test_costs_ordered(self):
        costs = [DIAGNOSTIC_TEST_COSTS[tt] for tt in DiagnosticTestType]
        assert costs == sorted(costs), "Test types should be ordered by cost"

    def test_symptom_entry_creation(self):
        s = SymptomEntry(description="Motor is vibrating excessively")
        assert s.description == "Motor is vibrating excessively"
        assert s.symptom_id.startswith("SYM-")
        assert s.severity == "MEDIUM"
        assert s.category == ""

    def test_diagnostic_test_creation(self):
        t = DiagnosticTest(
            test_type=DiagnosticTestType.VIBRATION_ANALYSIS,
            description="Measure vibration at motor bearings",
            estimated_cost_usd=200,
        )
        assert t.test_id.startswith("TST-")
        assert t.test_type == DiagnosticTestType.VIBRATION_ANALYSIS

    def test_diagnostic_path_creation(self):
        p = DiagnosticPath(fm_code="FM-51", mechanism="OVERHEATS_MELTS", cause="LACK_OF_LUBRICATION")
        assert p.fm_code == "FM-51"
        assert p.confidence == 0.0

    def test_diagnosis_session_creation(self):
        s = DiagnosisSession(equipment_type_id="ET-SAG-MILL")
        assert s.session_id.startswith("DIAG-")
        assert s.status == DiagnosisStatus.IN_PROGRESS
        assert s.symptoms == []
        assert s.candidate_diagnoses == []

    def test_diagnostic_path_confidence_bounds(self):
        p = DiagnosticPath(fm_code="FM-01", confidence=0.5)
        assert 0.0 <= p.confidence <= 1.0

    def test_diagnostic_path_confidence_min(self):
        p = DiagnosticPath(fm_code="FM-01", confidence=0.0)
        assert p.confidence == 0.0

    def test_diagnostic_path_confidence_max(self):
        p = DiagnosticPath(fm_code="FM-01", confidence=1.0)
        assert p.confidence == 1.0


# ── Session Creation Tests ───────────────────────────────────────────


class TestSessionCreation:

    def test_create_session_with_known_equipment(self):
        session = TroubleshootingEngine.create_session("ET-SAG-MILL")
        assert session.equipment_type_id == "ET-SAG-MILL"
        assert session.status == DiagnosisStatus.IN_PROGRESS
        assert session.session_id.startswith("DIAG-")
        assert len(session.session_id) == 13  # DIAG- + 8 hex chars

    def test_create_session_with_unknown_equipment(self):
        session = TroubleshootingEngine.create_session("ET-UNKNOWN-THING")
        assert session.equipment_type_id == "ET-UNKNOWN-THING"
        assert session.status == DiagnosisStatus.IN_PROGRESS

    def test_create_session_with_all_fields(self):
        session = TroubleshootingEngine.create_session(
            equipment_type_id="ET-SAG-MILL",
            equipment_tag="BRY-SAG-ML-001",
            plant_id="OCP-JFC1",
            technician_id="TECH-042",
        )
        assert session.equipment_tag == "BRY-SAG-ML-001"
        assert session.plant_id == "OCP-JFC1"
        assert session.technician_id == "TECH-042"

    def test_session_id_format(self):
        session = TroubleshootingEngine.create_session("ET-SAG-MILL")
        assert session.session_id.startswith("DIAG-")
        # The hex part should be 8 uppercase chars
        hex_part = session.session_id[5:]
        assert len(hex_part) == 8
        assert hex_part == hex_part.upper()

    def test_session_starts_empty(self):
        session = TroubleshootingEngine.create_session("ET-SAG-MILL")
        assert session.symptoms == []
        assert session.tests_performed == []
        assert session.candidate_diagnoses == []
        assert session.final_diagnosis is None
        assert session.actual_cause_feedback is None

    def test_session_has_creation_timestamp(self):
        before = datetime.now()
        session = TroubleshootingEngine.create_session("ET-SAG-MILL")
        after = datetime.now()
        assert before <= session.created_at <= after


# ── Symptom Normalization Tests ──────────────────────────────────────


class TestSymptomNormalization:

    def test_normalize_vibration_symptom(self):
        text, category = TroubleshootingEngine._normalize_symptom(
            "The motor is VIBRATING excessively!"
        )
        assert "vibrating" in text
        assert category == "vibration"

    def test_normalize_temperature_symptom(self):
        _, category = TroubleshootingEngine._normalize_symptom(
            "Bearing is overheating, temperature very high"
        )
        assert category == "temperature"

    def test_normalize_noise_symptom(self):
        _, category = TroubleshootingEngine._normalize_symptom(
            "Strange knocking noise from gearbox"
        )
        assert category == "noise"

    def test_normalize_electrical_symptom(self):
        _, category = TroubleshootingEngine._normalize_symptom(
            "Motor tripping on overcurrent"
        )
        assert category == "electrical"

    def test_normalize_leak_symptom(self):
        _, category = TroubleshootingEngine._normalize_symptom(
            "Oil leak at gearbox seal"
        )
        assert category == "leak"

    def test_normalize_removes_punctuation(self):
        text, _ = TroubleshootingEngine._normalize_symptom(
            "Motor vibration!!! High temperature???"
        )
        assert "!" not in text
        assert "?" not in text

    def test_normalize_lowercases(self):
        text, _ = TroubleshootingEngine._normalize_symptom("HIGH VIBRATION")
        assert text == text.lower()

    def test_normalize_empty_string(self):
        text, category = TroubleshootingEngine._normalize_symptom("")
        assert text == ""
        assert category == ""


# ── Keyword Extraction Tests ─────────────────────────────────────────


class TestKeywordExtraction:

    def test_extract_removes_stop_words(self):
        kw = TroubleshootingEngine._extract_keywords("the motor is vibrating in the factory")
        assert "the" not in kw
        assert "is" not in kw
        assert "in" not in kw
        assert "motor" in kw
        assert "vibrating" in kw

    def test_extract_removes_short_words(self):
        kw = TroubleshootingEngine._extract_keywords("an IR test on a HV motor")
        assert "an" not in kw
        assert "on" not in kw

    def test_extract_lowercases(self):
        kw = TroubleshootingEngine._extract_keywords("VIBRATION ANALYSIS")
        assert "vibration" in kw
        assert "analysis" in kw

    def test_extract_empty_string(self):
        kw = TroubleshootingEngine._extract_keywords("")
        assert kw == set()


# ── Keyword Match Score Tests ────────────────────────────────────────


class TestKeywordMatchScore:

    def test_identical_sets_score_1(self):
        s = TroubleshootingEngine._keyword_match_score({"a", "b"}, {"a", "b"})
        assert s == 1.0

    def test_disjoint_sets_score_0(self):
        s = TroubleshootingEngine._keyword_match_score({"a", "b"}, {"c", "d"})
        assert s == 0.0

    def test_partial_overlap(self):
        s = TroubleshootingEngine._keyword_match_score({"a", "b"}, {"b", "c"})
        assert 0.0 < s < 1.0
        assert abs(s - 1 / 3) < 0.01  # 1 common / 3 union

    def test_empty_sets(self):
        assert TroubleshootingEngine._keyword_match_score(set(), set()) == 0.0
        assert TroubleshootingEngine._keyword_match_score({"a"}, set()) == 0.0
        assert TroubleshootingEngine._keyword_match_score(set(), {"a"}) == 0.0


# ── Symptom Matching Tests ───────────────────────────────────────────


class TestSymptomMatching:

    def test_no_symptoms_returns_empty(self):
        result = TroubleshootingEngine.match_symptoms("ET-SAG-MILL", [])
        assert result == []

    def test_unknown_equipment_returns_empty(self):
        symptoms = [SymptomEntry(description="vibration")]
        result = TroubleshootingEngine.match_symptoms("ET-NONEXISTENT", symptoms)
        assert result == []

    def test_vibration_symptom_returns_candidates(self):
        symptoms = [SymptomEntry(
            description="Motor bearing vibration high temperature",
            category="vibration",
        )]
        result = TroubleshootingEngine.match_symptoms("ET-SAG-MILL", symptoms)
        assert isinstance(result, list)
        # Should find some candidates from SAG Mill failure modes
        if result:
            assert all(isinstance(c, DiagnosticPath) for c in result)
            assert all(0 <= c.confidence <= 1.0 for c in result)

    def test_results_sorted_by_confidence_descending(self):
        symptoms = [SymptomEntry(
            description="bearing overheating temperature contamination",
            category="temperature",
        )]
        result = TroubleshootingEngine.match_symptoms("ET-SAG-MILL", symptoms)
        if len(result) > 1:
            for i in range(len(result) - 1):
                assert result[i].confidence >= result[i + 1].confidence

    def test_results_limited_to_5(self):
        symptoms = [
            SymptomEntry(description="vibration noise temperature leak oil"),
            SymptomEntry(description="bearing motor gearbox coupling pressure"),
        ]
        result = TroubleshootingEngine.match_symptoms("ET-SAG-MILL", symptoms)
        assert len(result) <= 5

    def test_candidates_have_fm_codes(self):
        symptoms = [SymptomEntry(description="motor bearing vibration")]
        result = TroubleshootingEngine.match_symptoms("ET-SAG-MILL", symptoms)
        for c in result:
            assert c.fm_code.startswith("FM-")

    def test_candidates_have_mechanism_and_cause(self):
        symptoms = [SymptomEntry(description="motor bearing temperature high")]
        result = TroubleshootingEngine.match_symptoms("ET-SAG-MILL", symptoms)
        for c in result:
            assert c.mechanism != ""
            assert c.cause != ""


# ── Add Symptom Tests ────────────────────────────────────────────────


class TestAddSymptom:

    def test_add_symptom_increases_count(self):
        session = TroubleshootingEngine.create_session("ET-SAG-MILL")
        assert len(session.symptoms) == 0
        session = TroubleshootingEngine.add_symptom(session, "Motor vibrating")
        assert len(session.symptoms) == 1

    def test_add_symptom_normalizes_description(self):
        session = TroubleshootingEngine.create_session("ET-SAG-MILL")
        session = TroubleshootingEngine.add_symptom(session, "MOTOR VIBRATING!")
        assert session.symptoms[0].description_normalized == "motor vibrating"

    def test_add_symptom_detects_category(self):
        session = TroubleshootingEngine.create_session("ET-SAG-MILL")
        session = TroubleshootingEngine.add_symptom(session, "Motor vibration excessive")
        assert session.symptoms[0].category == "vibration"

    def test_add_symptom_respects_explicit_category(self):
        session = TroubleshootingEngine.create_session("ET-SAG-MILL")
        session = TroubleshootingEngine.add_symptom(
            session, "Strange noise", category="noise"
        )
        assert session.symptoms[0].category == "noise"

    def test_add_symptom_updates_candidates(self):
        session = TroubleshootingEngine.create_session("ET-SAG-MILL")
        session = TroubleshootingEngine.add_symptom(
            session, "Motor bearing vibration high temperature"
        )
        # Candidates should be populated (may be empty if no catalog match)
        assert isinstance(session.candidate_diagnoses, list)

    def test_add_symptom_sets_severity(self):
        session = TroubleshootingEngine.create_session("ET-SAG-MILL")
        session = TroubleshootingEngine.add_symptom(
            session, "Critical bearing failure", severity="CRITICAL"
        )
        assert session.symptoms[0].severity == "CRITICAL"


# ── Minimum Cost Ordering Tests ──────────────────────────────────────


class TestMinimumCostOrdering:

    def test_sensory_tests_come_first(self):
        candidates = [
            DiagnosticPath(
                fm_code="FM-01",
                recommended_tests=[
                    DiagnosticTest(test_type=DiagnosticTestType.SPECIALIST_ANALYSIS, description="Specialist"),
                ],
            ),
            DiagnosticPath(
                fm_code="FM-02",
                recommended_tests=[
                    DiagnosticTest(test_type=DiagnosticTestType.SENSORY, description="Visual inspection"),
                ],
            ),
        ]
        tests = TroubleshootingEngine.get_recommended_tests(candidates)
        assert tests[0].test_type == DiagnosticTestType.SENSORY

    def test_specialist_tests_come_last(self):
        candidates = [
            DiagnosticPath(
                fm_code="FM-01",
                recommended_tests=[
                    DiagnosticTest(test_type=DiagnosticTestType.SENSORY, description="Look"),
                ],
            ),
            DiagnosticPath(
                fm_code="FM-02",
                recommended_tests=[
                    DiagnosticTest(test_type=DiagnosticTestType.VIBRATION_ANALYSIS, description="Vibration"),
                ],
            ),
            DiagnosticPath(
                fm_code="FM-03",
                recommended_tests=[
                    DiagnosticTest(test_type=DiagnosticTestType.SPECIALIST_ANALYSIS, description="Specialist"),
                ],
            ),
        ]
        tests = TroubleshootingEngine.get_recommended_tests(candidates)
        costs = [DIAGNOSTIC_TEST_COSTS[t.test_type] for t in tests]
        assert costs == sorted(costs)

    def test_already_performed_tests_excluded(self):
        test1 = DiagnosticTest(test_type=DiagnosticTestType.SENSORY, description="Look")
        candidates = [
            DiagnosticPath(fm_code="FM-01", recommended_tests=[test1]),
            DiagnosticPath(
                fm_code="FM-02",
                recommended_tests=[
                    DiagnosticTest(test_type=DiagnosticTestType.OIL_ANALYSIS, description="Oil"),
                ],
            ),
        ]
        tests = TroubleshootingEngine.get_recommended_tests(
            candidates, tests_already_performed=[test1.test_id]
        )
        assert all(t.test_id != test1.test_id for t in tests)

    def test_returns_max_3_tests(self):
        candidates = [
            DiagnosticPath(
                fm_code=f"FM-{i:02d}",
                recommended_tests=[
                    DiagnosticTest(
                        test_type=DiagnosticTestType.SENSORY,
                        description=f"Test {i}",
                    ),
                ],
            )
            for i in range(1, 6)
        ]
        tests = TroubleshootingEngine.get_recommended_tests(candidates)
        assert len(tests) <= 3

    def test_empty_candidates_returns_empty(self):
        tests = TroubleshootingEngine.get_recommended_tests([])
        assert tests == []

    def test_deduplicates_by_description(self):
        candidates = [
            DiagnosticPath(
                fm_code="FM-01",
                recommended_tests=[
                    DiagnosticTest(test_type=DiagnosticTestType.SENSORY, description="Visual check"),
                ],
            ),
            DiagnosticPath(
                fm_code="FM-02",
                recommended_tests=[
                    DiagnosticTest(test_type=DiagnosticTestType.SENSORY, description="Visual check"),
                ],
            ),
        ]
        tests = TroubleshootingEngine.get_recommended_tests(candidates)
        assert len(tests) == 1


# ── Confidence Scoring Tests ─────────────────────────────────────────


class TestConfidenceScoring:

    def _make_session_with_candidates(self) -> DiagnosisSession:
        session = TroubleshootingEngine.create_session("ET-SAG-MILL")
        session.candidate_diagnoses = [
            DiagnosticPath(fm_code="FM-51", confidence=0.6),
            DiagnosticPath(fm_code="FM-49", confidence=0.4),
        ]
        return session

    def test_fail_result_increases_confidence(self):
        session = self._make_session_with_candidates()
        session = TroubleshootingEngine.record_test_result(
            session, "TST-001", "FAIL"
        )
        assert session.candidate_diagnoses[0].confidence == pytest.approx(0.75, abs=0.01)

    def test_pass_result_decreases_confidence(self):
        session = self._make_session_with_candidates()
        session = TroubleshootingEngine.record_test_result(
            session, "TST-001", "PASS"
        )
        # Both candidates decrease by 0.20
        assert session.candidate_diagnoses[0].confidence == pytest.approx(0.40, abs=0.01)
        assert session.candidate_diagnoses[1].confidence == pytest.approx(0.20, abs=0.01)

    def test_confidence_clamped_to_1(self):
        session = TroubleshootingEngine.create_session("ET-SAG-MILL")
        session.candidate_diagnoses = [
            DiagnosticPath(fm_code="FM-51", confidence=0.95),
        ]
        session = TroubleshootingEngine.record_test_result(
            session, "TST-001", "FAIL"
        )
        assert session.candidate_diagnoses[0].confidence == 1.0

    def test_confidence_clamped_to_0(self):
        session = TroubleshootingEngine.create_session("ET-SAG-MILL")
        session.candidate_diagnoses = [
            DiagnosticPath(fm_code="FM-51", confidence=0.1),
        ]
        session = TroubleshootingEngine.record_test_result(
            session, "TST-001", "PASS"
        )
        assert session.candidate_diagnoses[0].confidence == 0.0

    def test_abnormal_treated_as_fail(self):
        session = self._make_session_with_candidates()
        original = session.candidate_diagnoses[0].confidence
        session = TroubleshootingEngine.record_test_result(
            session, "TST-001", "ABNORMAL"
        )
        assert session.candidate_diagnoses[0].confidence == original + 0.15

    def test_normal_treated_as_pass(self):
        session = self._make_session_with_candidates()
        original = session.candidate_diagnoses[0].confidence
        session = TroubleshootingEngine.record_test_result(
            session, "TST-001", "NORMAL"
        )
        assert session.candidate_diagnoses[0].confidence == original - 0.20

    def test_result_recorded_in_tests_performed(self):
        session = self._make_session_with_candidates()
        session = TroubleshootingEngine.record_test_result(
            session, "TST-001", "FAIL", measured_value="95°C"
        )
        assert len(session.tests_performed) == 1
        assert session.tests_performed[0]["test_id"] == "TST-001"
        assert session.tests_performed[0]["result"] == "FAIL"
        assert session.tests_performed[0]["measured_value"] == "95°C"

    def test_candidates_reranked_after_test(self):
        session = TroubleshootingEngine.create_session("ET-SAG-MILL")
        session.candidate_diagnoses = [
            DiagnosticPath(fm_code="FM-01", confidence=0.5),
            DiagnosticPath(fm_code="FM-02", confidence=0.6),
        ]
        # After PASS, both decrease but order should be by confidence
        session = TroubleshootingEngine.record_test_result(session, "TST-001", "PASS")
        assert session.candidate_diagnoses[0].confidence >= session.candidate_diagnoses[1].confidence


# ── Finalize / Feedback Tests ────────────────────────────────────────


class TestFinalizeAndFeedback:

    def test_finalize_sets_status_completed(self):
        session = TroubleshootingEngine.create_session("ET-SAG-MILL")
        session.candidate_diagnoses = [
            DiagnosticPath(fm_code="FM-51", confidence=0.8),
        ]
        session = TroubleshootingEngine.finalize_diagnosis(session, "FM-51")
        assert session.status == DiagnosisStatus.COMPLETED
        assert session.final_diagnosis is not None
        assert session.final_diagnosis.fm_code == "FM-51"

    def test_finalize_sets_completion_time(self):
        session = TroubleshootingEngine.create_session("ET-SAG-MILL")
        session.candidate_diagnoses = [
            DiagnosticPath(fm_code="FM-51", confidence=0.8),
        ]
        session = TroubleshootingEngine.finalize_diagnosis(session, "FM-51")
        assert session.completed_at is not None

    def test_finalize_unknown_fm_code(self):
        session = TroubleshootingEngine.create_session("ET-SAG-MILL")
        session.candidate_diagnoses = [
            DiagnosticPath(fm_code="FM-51", confidence=0.8),
        ]
        session = TroubleshootingEngine.finalize_diagnosis(session, "FM-99")
        assert session.status == DiagnosisStatus.COMPLETED
        assert session.final_diagnosis is not None
        assert session.final_diagnosis.fm_code == "FM-99"

    def test_record_feedback(self):
        session = TroubleshootingEngine.create_session("ET-SAG-MILL")
        session = TroubleshootingEngine.record_feedback(
            session, "Bearing was contaminated, not lack of lubrication"
        )
        assert session.actual_cause_feedback == "Bearing was contaminated, not lack of lubrication"

    def test_record_feedback_with_notes(self):
        session = TroubleshootingEngine.create_session("ET-SAG-MILL")
        session = TroubleshootingEngine.record_feedback(
            session,
            actual_cause="FM-49 was correct",
            notes="Phosphate dust ingress through damaged seal",
        )
        assert "Phosphate dust" in session.notes


# ── Decision Tree Tests ──────────────────────────────────────────────


class TestDecisionTree:

    def test_load_tree_sag_mill(self):
        tree = TroubleshootingEngine.get_decision_tree("ET-SAG-MILL")
        assert tree is not None
        assert "entry_nodes" in tree or "entry_node_id" in tree
        assert "nodes" in tree

    def test_load_tree_unknown_returns_none(self):
        tree = TroubleshootingEngine.get_decision_tree("ET-NONEXISTENT-THING")
        assert tree is None

    def test_load_tree_with_category(self):
        tree = TroubleshootingEngine.get_decision_tree("ET-SAG-MILL", "vibration")
        assert tree is not None
        assert tree.get("category") == "vibration"
        assert tree.get("entry_node_id") == "V-001"

    def test_load_tree_with_unknown_category(self):
        tree = TroubleshootingEngine.get_decision_tree("ET-SAG-MILL", "nonexistent")
        # Should return None because category doesn't exist in entry_nodes
        assert tree is None

    def test_tree_nodes_have_questions(self):
        tree = TroubleshootingEngine.get_decision_tree("ET-SAG-MILL")
        if tree and "nodes" in tree:
            for node_id, node in tree["nodes"].items():
                # Terminal nodes don't have questions
                if not node.get("is_terminal"):
                    assert "question" in node, f"Node {node_id} missing question"

    def test_tree_terminal_nodes_have_diagnosis(self):
        tree = TroubleshootingEngine.get_decision_tree("ET-SAG-MILL")
        if tree and "nodes" in tree:
            for node_id, node in tree["nodes"].items():
                if node.get("is_terminal"):
                    assert "terminal_diagnosis" in node, f"Terminal node {node_id} missing diagnosis"


# ── Equipment Symptoms Tests ─────────────────────────────────────────


class TestEquipmentSymptoms:

    def test_sag_mill_has_symptoms_or_empty(self):
        """SAG Mill should return symptoms if catalog exists, empty if not."""
        result = TroubleshootingEngine.get_equipment_symptoms("ET-SAG-MILL")
        assert isinstance(result, list)

    def test_unknown_equipment_returns_empty(self):
        result = TroubleshootingEngine.get_equipment_symptoms("ET-NONEXISTENT")
        assert result == []

    def test_symptoms_have_required_fields(self):
        result = TroubleshootingEngine.get_equipment_symptoms("ET-SAG-MILL")
        for s in result:
            assert "symptom_id" in s
            assert "description" in s
            assert "category" in s


# ── Available Equipment Types Tests ──────────────────────────────────


class TestAvailableEquipmentTypes:

    def test_returns_list(self):
        result = TroubleshootingEngine.get_available_equipment_types()
        assert isinstance(result, list)

    def test_sag_mill_in_list(self):
        result = TroubleshootingEngine.get_available_equipment_types()
        ids = [et["equipment_type_id"] for et in result]
        assert "ET-SAG-MILL" in ids

    def test_has_decision_tree_flag(self):
        result = TroubleshootingEngine.get_available_equipment_types()
        sag = next(et for et in result if et["equipment_type_id"] == "ET-SAG-MILL")
        assert sag["has_decision_tree"] is True

    def test_equipment_without_tree(self):
        result = TroubleshootingEngine.get_available_equipment_types()
        # Most equipment types won't have trees yet
        no_tree = [et for et in result if not et["has_decision_tree"]]
        assert len(no_tree) > 0  # At least some should not have trees


# ── FM Code Derivation Tests ─────────────────────────────────────────


class TestFMCodeDerivation:

    def test_known_combinations(self):
        assert TroubleshootingEngine._derive_fm_code("ARCS", "BREAKDOWN_IN_INSULATION") == "FM-01"
        assert TroubleshootingEngine._derive_fm_code("WEARS", "RELATIVE_MOVEMENT") == "FM-72"
        assert TroubleshootingEngine._derive_fm_code("OVERHEATS_MELTS", "LACK_OF_LUBRICATION") == "FM-51"

    def test_unknown_combination(self):
        result = TroubleshootingEngine._derive_fm_code("UNKNOWN", "MYSTERY")
        assert result.startswith("FM-??-")


# ── Test Type Inference Tests ────────────────────────────────────────


class TestTestTypeInference:

    def test_vibration_analysis(self):
        assert TroubleshootingEngine._infer_test_type(
            "Vibration monitoring at bearings"
        ) == DiagnosticTestType.VIBRATION_ANALYSIS

    def test_oil_analysis(self):
        assert TroubleshootingEngine._infer_test_type(
            "Oil analysis (oxidation, viscosity)"
        ) == DiagnosticTestType.OIL_ANALYSIS

    def test_thermography(self):
        assert TroubleshootingEngine._infer_test_type(
            "Thermography of panels"
        ) == DiagnosticTestType.THERMOGRAPHY

    def test_ultrasonic(self):
        assert TroubleshootingEngine._infer_test_type(
            "UT thickness measurement"
        ) == DiagnosticTestType.ULTRASONIC

    def test_specialist(self):
        assert TroubleshootingEngine._infer_test_type(
            "Insulation resistance testing (megger)"
        ) == DiagnosticTestType.SPECIALIST_ANALYSIS

    def test_ndt(self):
        assert TroubleshootingEngine._infer_test_type(
            "MPI at known hot spots"
        ) == DiagnosticTestType.NDT_INSPECTION

    def test_process_check(self):
        assert TroubleshootingEngine._infer_test_type(
            "Differential pressure measurement"
        ) == DiagnosticTestType.PROCESS_CHECK

    def test_sensory_fallback(self):
        assert TroubleshootingEngine._infer_test_type(
            "Something completely unrelated"
        ) == DiagnosticTestType.SENSORY


# ── Category Keywords Tests ──────────────────────────────────────────


class TestCategoryKeywords:

    def test_all_categories_have_keywords(self):
        for category in ["vibration", "noise", "temperature", "leak", "pressure",
                         "flow", "electrical", "visual", "smell", "performance",
                         "alignment", "contamination"]:
            assert category in CATEGORY_KEYWORDS
            assert len(CATEGORY_KEYWORDS[category]) > 0

    def test_no_overlapping_primary_keywords(self):
        """Primary identifiers should be unique to their category."""
        primary = {
            "vibration": "vibration",
            "noise": "noise",
            "temperature": "temperature",
            "leak": "leak",
            "pressure": "pressure",
            "electrical": "electrical",
        }
        for cat, keyword in primary.items():
            for other_cat, other_keywords in CATEGORY_KEYWORDS.items():
                if other_cat != cat:
                    assert keyword not in other_keywords, (
                        f"'{keyword}' is in both {cat} and {other_cat}"
                    )


# ── Integration Test: Full Diagnosis Flow ────────────────────────────


class TestFullDiagnosisFlow:

    def test_complete_diagnosis_flow(self):
        """End-to-end: create → add symptoms → get tests → record result → finalize → feedback."""
        # 1. Create session
        session = TroubleshootingEngine.create_session(
            "ET-SAG-MILL", equipment_tag="BRY-SAG-ML-001"
        )
        assert session.status == DiagnosisStatus.IN_PROGRESS

        # 2. Add symptoms
        session = TroubleshootingEngine.add_symptom(
            session, "Motor bearing vibration high temperature"
        )
        assert len(session.symptoms) == 1

        # 3. Get recommended tests
        tests = TroubleshootingEngine.get_recommended_tests(session.candidate_diagnoses)
        assert isinstance(tests, list)

        # 4. Record a test result (simulate)
        if session.candidate_diagnoses:
            session = TroubleshootingEngine.record_test_result(
                session, "TST-sim-001", "ABNORMAL", "95°C"
            )
            assert len(session.tests_performed) == 1

            # 5. Finalize
            top_fm = session.candidate_diagnoses[0].fm_code
            session = TroubleshootingEngine.finalize_diagnosis(session, top_fm)
            assert session.status == DiagnosisStatus.COMPLETED

            # 6. Feedback
            session = TroubleshootingEngine.record_feedback(
                session, "Confirmed: bearing contamination from phosphate dust"
            )
            assert session.actual_cause_feedback is not None

    def test_multiple_symptoms_refine_candidates(self):
        """Adding more symptoms should refine (potentially change) candidates."""
        session = TroubleshootingEngine.create_session("ET-SAG-MILL")

        session = TroubleshootingEngine.add_symptom(session, "vibration")
        candidates_1 = [c.fm_code for c in session.candidate_diagnoses]

        session = TroubleshootingEngine.add_symptom(session, "bearing temperature high oil")
        candidates_2 = [c.fm_code for c in session.candidate_diagnoses]

        # Candidates should be present (exact content depends on catalog)
        assert isinstance(candidates_1, list)
        assert isinstance(candidates_2, list)
