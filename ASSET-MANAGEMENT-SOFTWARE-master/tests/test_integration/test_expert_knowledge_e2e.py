"""
Integration tests: Expert knowledge capture flywheel.
Escalation -> Consultation -> Contribution -> Promotion.
"""

import pytest
from datetime import datetime, timedelta

from tools.engines.expert_knowledge_engine import ExpertKnowledgeEngine
from tools.models.schemas import ConsultationStatus


pytestmark = pytest.mark.integration


def _sample_experts():
    """Build sample expert dicts."""
    return [
        {
            "expert_id": "EXP-001",
            "name": "Dr. Mahmoud",
            "equipment_expertise": ["SAG_MILL", "BALL_MILL"],
            "specialty_areas": ["vibration", "bearing"],
            "plant_familiarity": ["OCP-JFC1"],
            "years_experience": 30,
            "language": "fr",
            "is_retired": True,
            "availability_hours": 20,
            "hourly_rate_usd": 150.0,
        },
        {
            "expert_id": "EXP-002",
            "name": "Eng. Fatima",
            "equipment_expertise": ["PUMP", "COMPRESSOR"],
            "specialty_areas": ["seal", "leak"],
            "plant_familiarity": ["OCP-JFC1", "OCP-JFC2"],
            "years_experience": 25,
            "language": "fr",
            "is_retired": True,
            "availability_hours": 15,
            "hourly_rate_usd": 120.0,
        },
    ]


def _make_session(**overrides):
    """Build a minimal session dict for create_consultation."""
    data = {
        "session_id": "test-session",
        "equipment_type_id": "SAG_MILL",
        "equipment_tag": "BRY-SAG-ML-001",
        "plant_id": "OCP-JFC1",
        "technician_id": "TECH-001",
        "symptoms": [{"symptom": "high vibration", "severity": "HIGH"}],
        "candidate_diagnoses": [{"fm_code": "FM-01", "confidence": 0.6}],
    }
    data.update(overrides)
    return data


class TestExpertKnowledgeFlywheel:
    """Full expert knowledge capture lifecycle."""

    def test_match_expert_ranking(self):
        """match_expert returns ranked experts by relevance."""
        experts = _sample_experts()
        matches = ExpertKnowledgeEngine.match_expert(
            equipment_type_id="SAG_MILL",
            symptom_categories=["vibration", "bearing"],
            plant_id="OCP-JFC1",
            experts=experts,
        )
        assert len(matches) > 0
        # First match should be Dr. Mahmoud (SAG_MILL + vibration expert)
        assert matches[0]["expert_id"] == "EXP-001"

    def test_create_consultation(self):
        """create_consultation generates token and sets status."""
        consultation = ExpertKnowledgeEngine.create_consultation(
            session=_make_session(),
            expert_id="EXP-001",
            ai_suggestion="Possible bearing wear",
        )
        assert consultation["token"]
        assert len(consultation["token"]) > 0
        assert consultation["status"] == "REQUESTED"
        assert consultation["expert_id"] == "EXP-001"

    def test_token_validation(self):
        """validate_token works for valid token."""
        consultation = ExpertKnowledgeEngine.create_consultation(
            session=_make_session(),
            expert_id="EXP-001",
        )
        valid, msg = ExpertKnowledgeEngine.validate_token(consultation["token"], consultation)
        assert valid

    def test_token_validation_wrong_token(self):
        """validate_token rejects wrong token."""
        consultation = ExpertKnowledgeEngine.create_consultation(
            session=_make_session(),
            expert_id="EXP-001",
        )
        valid, msg = ExpertKnowledgeEngine.validate_token("wrong-token", consultation)
        assert not valid

    def test_record_response(self):
        """record_response updates consultation with expert input."""
        consultation = ExpertKnowledgeEngine.create_consultation(
            session=_make_session(),
            expert_id="EXP-001",
        )
        updated = ExpertKnowledgeEngine.record_expert_response(
            consultation=consultation,
            expert_guidance="Check bearing clearance and alignment. FM-01 is most likely.",
            fm_codes=["FM-01", "FM-03"],
            confidence=0.85,
        )
        assert updated["status"] == "RESPONDED"
        assert updated["expert_confidence"] == 0.85
        assert len(updated["expert_fm_codes"]) == 2

    def test_extract_contribution(self):
        """extract_contribution creates contribution from responded consultation."""
        consultation = ExpertKnowledgeEngine.create_consultation(
            session=_make_session(),
            expert_id="EXP-001",
        )
        consultation = ExpertKnowledgeEngine.record_expert_response(
            consultation=consultation,
            expert_guidance="Check FM-01 bearing wear and FM-03 misalignment",
            fm_codes=["FM-01", "FM-03"],
            confidence=0.9,
        )
        contribution = ExpertKnowledgeEngine.extract_contribution(consultation)
        assert contribution is not None
        assert contribution["consultation_id"] == consultation["consultation_id"]
        assert contribution["expert_id"] == "EXP-001"

    def test_validate_fm_codes(self):
        """validate_fm_codes identifies invalid codes."""
        results = ExpertKnowledgeEngine.validate_fm_codes(["FM-01", "FM-99", "INVALID"])
        # Returns list of (code, valid) tuples
        invalid = [(code, v) for code, v in results if not v]
        assert len(invalid) > 0

    def test_validate_fm_codes_all_valid(self):
        """validate_fm_codes returns all True for valid codes."""
        results = ExpertKnowledgeEngine.validate_fm_codes(["FM-01", "FM-02", "FM-03"])
        # All should be valid
        invalid = [(code, v) for code, v in results if not v]
        assert len(invalid) == 0

    def test_compensation_calculation(self):
        """calculate_compensation based on response time."""
        consultation = ExpertKnowledgeEngine.create_consultation(
            session=_make_session(),
            expert_id="EXP-001",
        )
        consultation = ExpertKnowledgeEngine.record_expert_response(
            consultation=consultation,
            expert_guidance="Detailed analysis here",
            fm_codes=["FM-01"],
            confidence=0.9,
        )
        compensation = ExpertKnowledgeEngine.calculate_compensation(
            consultations=[consultation],
            hourly_rate_usd=150.0,
        )
        assert isinstance(compensation, dict)

    def test_promote_to_symptom_catalog(self):
        """Contribution promotes to symptom catalog."""
        consultation = ExpertKnowledgeEngine.create_consultation(
            session=_make_session(symptoms=[{"symptom": "vibration"}]),
            expert_id="EXP-001",
        )
        consultation = ExpertKnowledgeEngine.record_expert_response(
            consultation=consultation,
            expert_guidance="FM-01 bearing wear causes vibration",
            fm_codes=["FM-01"],
            confidence=0.9,
        )
        contribution = ExpertKnowledgeEngine.extract_contribution(consultation)
        import tempfile, json
        from pathlib import Path
        # Create temp catalog file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([], f)
            catalog_path = Path(f.name)
        try:
            result = ExpertKnowledgeEngine.promote_to_symptom_catalog(contribution, catalog_path)
            assert result is not None
        finally:
            catalog_path.unlink(missing_ok=True)
