"""Tests for GAP-W13: Expert Knowledge Engine.

Covers: expert matching, consultation lifecycle, knowledge extraction,
validation, promotion, compensation, and FM code validation.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tools.engines.expert_knowledge_engine import ExpertKnowledgeEngine


# ── Fixtures ─────────────────────────────────────────────────────────


def _make_expert(
    expert_id: str = "",
    domains: list[str] | None = None,
    equipment_expertise: list[str] | None = None,
    years_experience: int = 10,
    resolution_count: int = 5,
    languages: list[str] | None = None,
    is_retired: bool = True,
) -> dict:
    return {
        "expert_id": expert_id or str(uuid.uuid4()),
        "user_id": f"user-{uuid.uuid4().hex[:6]}",
        "name": f"Expert-{uuid.uuid4().hex[:4]}",
        "role": "RETIRED_EXPERT",
        "plant_id": "OCP-JFC",
        "domains": domains or ["MECHANICAL"],
        "equipment_expertise": equipment_expertise or ["ET-SAG-MILL"],
        "certifications": ["OEM-CERT"],
        "years_experience": years_experience,
        "resolution_count": resolution_count,
        "last_active": None,
        "contact_method": "email",
        "languages": languages or ["FR", "EN"],
        "is_retired": is_retired,
        "hourly_rate_usd": 50.0,
    }


def _make_session(
    equipment_type_id: str = "ET-SAG-MILL",
    symptoms: list[dict] | None = None,
    candidates: list[dict] | None = None,
) -> dict:
    return {
        "session_id": f"DIAG-{uuid.uuid4().hex[:8].upper()}",
        "equipment_type_id": equipment_type_id,
        "equipment_tag": "BRY-SAG-ML-001",
        "plant_id": "OCP-JFC",
        "technician_id": "tech-001",
        "status": "IN_PROGRESS",
        "symptoms": symptoms or [{"description": "Excessive vibration", "category": "vibration"}],
        "candidate_diagnoses": candidates or [
            {"fm_code": "FM-47", "confidence": 0.65, "mechanism": "LOOSENS", "cause": "VIBRATION"},
        ],
    }


def _make_consultation(
    status: str = "REQUESTED",
    token: str | None = None,
    viewed_at: str | None = None,
    expires_hours: int = 24,
) -> dict:
    now = datetime.now()
    return {
        "consultation_id": f"CONS-{uuid.uuid4().hex[:8].upper()}",
        "session_id": "DIAG-TEST0001",
        "expert_id": "expert-001",
        "technician_id": "tech-001",
        "equipment_type_id": "ET-SAG-MILL",
        "equipment_tag": "BRY-SAG-ML-001",
        "plant_id": "OCP-JFC",
        "symptoms_snapshot": [{"description": "vibration"}],
        "candidates_snapshot": [{"fm_code": "FM-47", "confidence": 0.65}],
        "ai_suggestion": "Check bearing clearance",
        "expert_guidance": "",
        "expert_fm_codes": [],
        "expert_confidence": 0.0,
        "status": status,
        "token": token or uuid.uuid4().hex,
        "token_expires_at": (now + timedelta(hours=expires_hours)).isoformat(),
        "requested_at": now.isoformat(),
        "viewed_at": viewed_at,
        "responded_at": None,
        "closed_at": None,
        "response_time_minutes": 0.0,
        "compensation_status": "PENDING",
        "language": "fr",
        "notes": "",
    }


def _make_contribution(
    fm_codes: list[str] | None = None,
    status: str = "RAW",
) -> dict:
    return {
        "contribution_id": f"EKNT-{uuid.uuid4().hex[:8].upper()}",
        "consultation_id": "CONS-TEST0001",
        "expert_id": "expert-001",
        "equipment_type_id": "ET-SAG-MILL",
        "fm_codes": fm_codes or ["FM-47"],
        "symptom_descriptions": ["Excessive vibration on drive end"],
        "diagnostic_steps": ["Check bearing clearance", "Measure vibration spectrum"],
        "corrective_actions": ["Replace drive end bearing"],
        "tips": "At OCP, SAG Mill bearings wear faster due to ore hardness",
        "status": status,
        "validated_by": "",
        "validated_at": None,
        "promoted_at": None,
        "promoted_targets": [],
        "created_at": datetime.now().isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════
# Expert Matching
# ══════════════════════════════════════════════════════════════════════


class TestExpertMatching:
    def test_match_expert_equipment_expertise_boost(self):
        experts = [
            _make_expert(expert_id="E1", equipment_expertise=["ET-SAG-MILL"], years_experience=5),
            _make_expert(expert_id="E2", equipment_expertise=["ET-PUMP"], years_experience=20),
        ]
        result = ExpertKnowledgeEngine.match_expert(
            "ET-SAG-MILL", ["vibration"], "OCP-JFC", experts,
        )
        assert result[0]["expert_id"] == "E1"
        assert result[0]["match_score"] > result[1]["match_score"]

    def test_match_expert_domain_match(self):
        experts = [
            _make_expert(expert_id="E1", domains=["ELECTRICAL"]),
            _make_expert(expert_id="E2", domains=["MECHANICAL"]),
        ]
        result = ExpertKnowledgeEngine.match_expert(
            "ET-SAG-MILL", ["vibration"], "OCP-JFC", experts,
        )
        # vibration maps to MECHANICAL
        mech = next(e for e in result if e["expert_id"] == "E2")
        elec = next(e for e in result if e["expert_id"] == "E1")
        assert mech["match_score"] > elec["match_score"]

    def test_match_expert_language_preference(self):
        experts = [
            _make_expert(expert_id="E1", languages=["FR"]),
            _make_expert(expert_id="E2", languages=["EN"]),
        ]
        result = ExpertKnowledgeEngine.match_expert(
            "ET-SAG-MILL", ["vibration"], "OCP-JFC", experts, language_preference="en",
        )
        en_expert = next(e for e in result if e["expert_id"] == "E2")
        fr_expert = next(e for e in result if e["expert_id"] == "E1")
        assert en_expert["match_score"] > fr_expert["match_score"]

    def test_match_expert_empty_list_returns_empty(self):
        result = ExpertKnowledgeEngine.match_expert(
            "ET-SAG-MILL", ["vibration"], "OCP-JFC", [],
        )
        assert result == []

    def test_match_expert_top_3_limit(self):
        experts = [_make_expert(expert_id=f"E{i}") for i in range(10)]
        result = ExpertKnowledgeEngine.match_expert(
            "ET-SAG-MILL", ["vibration"], "OCP-JFC", experts,
        )
        assert len(result) <= 3

    def test_match_expert_returns_match_score_field(self):
        experts = [_make_expert()]
        result = ExpertKnowledgeEngine.match_expert(
            "ET-SAG-MILL", ["vibration"], "OCP-JFC", experts,
        )
        assert "match_score" in result[0]
        assert 0.0 <= result[0]["match_score"] <= 1.0

    def test_match_expert_experience_boost(self):
        experts = [
            _make_expert(expert_id="E1", years_experience=30),
            _make_expert(expert_id="E2", years_experience=5),
        ]
        result = ExpertKnowledgeEngine.match_expert(
            "ET-SAG-MILL", ["vibration"], "OCP-JFC", experts,
        )
        senior = next(e for e in result if e["expert_id"] == "E1")
        junior = next(e for e in result if e["expert_id"] == "E2")
        assert senior["match_score"] >= junior["match_score"]


# ══════════════════════════════════════════════════════════════════════
# Consultation Lifecycle
# ══════════════════════════════════════════════════════════════════════


class TestConsultationLifecycle:
    def test_create_consultation_sets_token_and_expiry(self):
        session = _make_session()
        result = ExpertKnowledgeEngine.create_consultation(session, "expert-001")
        assert result["token"]
        assert len(result["token"]) == 32
        assert result["token_expires_at"]
        assert result["status"] == "REQUESTED"

    def test_create_consultation_captures_snapshot(self):
        session = _make_session()
        result = ExpertKnowledgeEngine.create_consultation(session, "expert-001")
        assert len(result["symptoms_snapshot"]) == 1
        assert len(result["candidates_snapshot"]) == 1

    def test_validate_token_valid(self):
        consultation = _make_consultation()
        valid, error = ExpertKnowledgeEngine.validate_token(
            consultation["token"], consultation,
        )
        assert valid is True
        assert error == ""

    def test_validate_token_expired(self):
        consultation = _make_consultation(expires_hours=-1)
        valid, error = ExpertKnowledgeEngine.validate_token(
            consultation["token"], consultation,
        )
        assert valid is False
        assert "expired" in error.lower()

    def test_validate_token_wrong_token(self):
        consultation = _make_consultation()
        valid, error = ExpertKnowledgeEngine.validate_token("wrong-token", consultation)
        assert valid is False
        assert "invalid" in error.lower()

    def test_validate_token_already_responded(self):
        consultation = _make_consultation(status="RESPONDED")
        valid, error = ExpertKnowledgeEngine.validate_token(
            consultation["token"], consultation,
        )
        assert valid is False
        assert "responded" in error.lower()

    def test_mark_viewed(self):
        consultation = _make_consultation()
        result = ExpertKnowledgeEngine.mark_viewed(consultation)
        assert result["status"] == "VIEWED"
        assert result["viewed_at"] is not None

    def test_record_response_computes_time(self):
        viewed = datetime.now() - timedelta(minutes=30)
        consultation = _make_consultation(
            status="VIEWED",
            viewed_at=viewed.isoformat(),
        )
        result = ExpertKnowledgeEngine.record_expert_response(
            consultation, "Check the bearing", fm_codes=["FM-47"], confidence=0.8,
        )
        assert result["status"] == "RESPONDED"
        assert result["response_time_minutes"] > 25

    def test_record_response_sets_status_responded(self):
        consultation = _make_consultation(status="VIEWED")
        result = ExpertKnowledgeEngine.record_expert_response(
            consultation, "Replace the bearing",
        )
        assert result["status"] == "RESPONDED"
        assert result["expert_guidance"] == "Replace the bearing"

    def test_close_consultation(self):
        consultation = _make_consultation(status="RESPONDED")
        result = ExpertKnowledgeEngine.close_consultation(consultation, notes="Resolved")
        assert result["status"] == "CLOSED"
        assert result["closed_at"] is not None
        assert "Resolved" in result["notes"]

    def test_expire_consultation(self):
        consultation = _make_consultation(expires_hours=-1)
        result = ExpertKnowledgeEngine.expire_consultation(consultation)
        assert result["status"] == "EXPIRED"

    def test_expire_consultation_no_effect_if_not_past(self):
        consultation = _make_consultation(expires_hours=24)
        result = ExpertKnowledgeEngine.expire_consultation(consultation)
        assert result["status"] == "REQUESTED"


# ══════════════════════════════════════════════════════════════════════
# Knowledge Extraction
# ══════════════════════════════════════════════════════════════════════


class TestKnowledgeExtraction:
    def test_extract_contribution_parses_fm_codes(self):
        consultation = _make_consultation(status="RESPONDED")
        consultation["expert_guidance"] = "The issue is FM-47 or possibly FM-64."
        consultation["expert_fm_codes"] = ["FM-47"]
        result = ExpertKnowledgeEngine.extract_contribution(consultation)
        assert "FM-47" in result["fm_codes"]
        assert "FM-64" in result["fm_codes"]

    def test_extract_contribution_identifies_symptoms(self):
        consultation = _make_consultation(status="RESPONDED")
        consultation["expert_guidance"] = (
            "The vibration is coming from the drive end. "
            "High temperature near the bearing."
        )
        result = ExpertKnowledgeEngine.extract_contribution(consultation)
        assert len(result["symptom_descriptions"]) > 0

    def test_extract_contribution_identifies_diagnostic_steps(self):
        consultation = _make_consultation(status="RESPONDED")
        consultation["expert_guidance"] = (
            "1. Check the bearing clearance\n"
            "2. Measure vibration spectrum\n"
            "3. Inspect oil condition"
        )
        result = ExpertKnowledgeEngine.extract_contribution(consultation)
        assert len(result["diagnostic_steps"]) == 3

    def test_extract_contribution_identifies_corrective_actions(self):
        consultation = _make_consultation(status="RESPONDED")
        consultation["expert_guidance"] = (
            "Replace the bearing immediately. "
            "Inspect the shaft alignment after replacement."
        )
        result = ExpertKnowledgeEngine.extract_contribution(consultation)
        assert len(result["corrective_actions"]) > 0

    def test_extract_contribution_sets_raw_status(self):
        consultation = _make_consultation(status="RESPONDED")
        consultation["expert_guidance"] = "Check FM-47"
        result = ExpertKnowledgeEngine.extract_contribution(consultation)
        assert result["status"] == "RAW"

    def test_extract_contribution_has_contribution_id(self):
        consultation = _make_consultation(status="RESPONDED")
        consultation["expert_guidance"] = "Some guidance"
        result = ExpertKnowledgeEngine.extract_contribution(consultation)
        assert result["contribution_id"].startswith("EKNT-")


# ══════════════════════════════════════════════════════════════════════
# Contribution Validation
# ══════════════════════════════════════════════════════════════════════


class TestContributionValidation:
    def test_validate_contribution_valid_fm_codes(self):
        contribution = _make_contribution()
        result = ExpertKnowledgeEngine.validate_contribution(
            contribution, fm_codes=["FM-47", "FM-64"], validated_by="eng-001",
        )
        assert result["status"] == "VALIDATED"
        assert result["validated_by"] == "eng-001"
        assert "FM-47" in result["fm_codes"]

    def test_validate_contribution_invalid_fm_code_rejected(self):
        contribution = _make_contribution()
        result = ExpertKnowledgeEngine.validate_contribution(
            contribution, fm_codes=["FM-99"], validated_by="eng-001",
        )
        assert result["status"] == "REJECTED"

    def test_validate_sets_status_validated(self):
        contribution = _make_contribution()
        result = ExpertKnowledgeEngine.validate_contribution(
            contribution, fm_codes=["FM-01"], validated_by="eng-001",
        )
        assert result["status"] == "VALIDATED"
        assert result["validated_at"] is not None


# ══════════════════════════════════════════════════════════════════════
# FM Code Validation
# ══════════════════════════════════════════════════════════════════════


class TestFMCodeValidation:
    def test_valid_fm_codes(self):
        result = ExpertKnowledgeEngine.validate_fm_codes(["FM-01", "FM-72"])
        assert all(valid for _, valid in result)

    def test_invalid_fm_code(self):
        result = ExpertKnowledgeEngine.validate_fm_codes(["FM-00", "FM-73", "FM-99"])
        assert all(not valid for _, valid in result)

    def test_mixed_valid_invalid(self):
        result = ExpertKnowledgeEngine.validate_fm_codes(["FM-01", "FM-99", "FM-50"])
        assert result[0] == ("FM-01", True)
        assert result[1] == ("FM-99", False)
        assert result[2] == ("FM-50", True)


# ══════════════════════════════════════════════════════════════════════
# Knowledge Promotion
# ══════════════════════════════════════════════════════════════════════


class TestKnowledgePromotion:
    def test_promote_to_symptom_catalog_appends_entry(self, tmp_path):
        catalog_path = tmp_path / "symptom-catalog.json"
        catalog_path.write_text("[]", encoding="utf-8")

        contribution = _make_contribution()
        result = ExpertKnowledgeEngine.promote_to_symptom_catalog(contribution, catalog_path)
        assert result["entries_added"] > 0

        # Verify catalog updated
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        assert len(catalog) > 0
        assert catalog[0]["source"].startswith("expert-")

    def test_promote_to_symptom_catalog_preserves_existing(self, tmp_path):
        catalog_path = tmp_path / "symptom-catalog.json"
        existing = [{"symptom_id": "SYM-EXISTING", "fm_codes": ["FM-01"]}]
        catalog_path.write_text(json.dumps(existing), encoding="utf-8")

        contribution = _make_contribution()
        ExpertKnowledgeEngine.promote_to_symptom_catalog(contribution, catalog_path)

        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        assert catalog[0]["symptom_id"] == "SYM-EXISTING"
        assert len(catalog) > 1

    def test_promote_to_manual_creates_file(self, tmp_path):
        contribution = _make_contribution()
        result = ExpertKnowledgeEngine.promote_to_manual(contribution, tmp_path)
        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "Expert Knowledge" in content
        assert "FM-47" in content

    def test_promote_to_manual_appends_existing(self, tmp_path):
        eq_dir = tmp_path / "ET-SAG-MILL"
        eq_dir.mkdir()
        (eq_dir / "expert-knowledge.md").write_text("# Existing content\n", encoding="utf-8")

        contribution = _make_contribution()
        result = ExpertKnowledgeEngine.promote_to_manual(contribution, tmp_path)
        content = result.read_text(encoding="utf-8")
        assert "# Existing content" in content
        assert "FM-47" in content

    def test_promote_to_memory_creates_pattern(self, tmp_path):
        contribution = _make_contribution()
        ExpertKnowledgeEngine.promote_to_memory(contribution, tmp_path)
        patterns_path = tmp_path / "reliability-engineering" / "patterns.md"
        assert patterns_path.exists()
        content = patterns_path.read_text(encoding="utf-8")
        assert "EXPERT-" in content

    def test_promote_to_decision_tree(self, tmp_path):
        trees_dir = tmp_path / "trees"
        trees_dir.mkdir()

        contribution = _make_contribution()
        result = ExpertKnowledgeEngine.promote_to_decision_tree(contribution, trees_dir)
        assert result is True

        tree_path = trees_dir / "tree-sag-mill.json"
        assert tree_path.exists()
        tree = json.loads(tree_path.read_text(encoding="utf-8"))
        assert "nodes" in tree
        assert len(tree["nodes"]) > 0

    def test_promote_to_decision_tree_no_equipment_returns_false(self, tmp_path):
        contribution = _make_contribution()
        contribution["equipment_type_id"] = ""
        result = ExpertKnowledgeEngine.promote_to_decision_tree(contribution, tmp_path)
        assert result is False


# ══════════════════════════════════════════════════════════════════════
# Compensation
# ══════════════════════════════════════════════════════════════════════


class TestCompensation:
    def test_calculate_compensation_single_consultation(self):
        consultations = [
            {"status": "RESPONDED", "response_time_minutes": 30.0},
        ]
        result = ExpertKnowledgeEngine.calculate_compensation(consultations, hourly_rate_usd=60.0)
        assert result["total_consultations"] == 1
        assert result["total_response_minutes"] == 30.0
        assert result["total_due_usd"] == 30.0  # 0.5 hours * 60

    def test_calculate_compensation_multiple_consultations(self):
        consultations = [
            {"status": "RESPONDED", "response_time_minutes": 60.0},
            {"status": "CLOSED", "response_time_minutes": 30.0},
            {"status": "REQUESTED", "response_time_minutes": 0.0},  # not counted
        ]
        result = ExpertKnowledgeEngine.calculate_compensation(consultations)
        assert result["total_consultations"] == 2
        assert result["total_response_minutes"] == 90.0

    def test_calculate_compensation_zero_hours(self):
        result = ExpertKnowledgeEngine.calculate_compensation([])
        assert result["total_consultations"] == 0
        assert result["total_due_usd"] == 0.0


# ══════════════════════════════════════════════════════════════════════
# Pydantic Model Validation
# ══════════════════════════════════════════════════════════════════════


class TestPydanticModels:
    def test_expert_consultation_model(self):
        from tools.models.schemas import ExpertConsultation
        c = ExpertConsultation(session_id="DIAG-001", expert_id="E-001")
        assert c.consultation_id.startswith("CONS-")
        assert c.status.value == "REQUESTED"
        assert len(c.token) == 32

    def test_expert_contribution_model(self):
        from tools.models.schemas import ExpertContribution
        c = ExpertContribution(consultation_id="CONS-001")
        assert c.contribution_id.startswith("EKNT-")
        assert c.status.value == "RAW"

    def test_compensation_summary_model(self):
        from tools.models.schemas import CompensationSummary
        s = CompensationSummary(expert_id="E-001", period="2026-03")
        assert s.hourly_rate_usd == 50.0
        assert s.total_due_usd == 0.0

    def test_expert_card_retirement_fields(self):
        from tools.models.schemas import ExpertCard, ExpertDomain, StakeholderRole, Language
        e = ExpertCard(
            user_id="u-001",
            name="Test Expert",
            role=StakeholderRole.RETIRED_EXPERT,
            plant_id="OCP-JFC",
            domains=[ExpertDomain.MECHANICAL],
            is_retired=True,
            hourly_rate_usd=75.0,
        )
        assert e.is_retired is True
        assert e.hourly_rate_usd == 75.0
        assert e.preferred_contact == "IN_APP"

    def test_consultation_status_enum(self):
        from tools.models.schemas import ConsultationStatus
        assert ConsultationStatus.REQUESTED.value == "REQUESTED"
        assert ConsultationStatus.EXPIRED.value == "EXPIRED"
        assert len(ConsultationStatus) == 7

    def test_contribution_status_enum(self):
        from tools.models.schemas import ContributionStatus
        assert ContributionStatus.RAW.value == "RAW"
        assert ContributionStatus.PROMOTED.value == "PROMOTED"
        assert len(ContributionStatus) == 4

    def test_compensation_status_enum(self):
        from tools.models.schemas import CompensationStatus
        assert len(CompensationStatus) == 3

    def test_stakeholder_role_has_retired_expert(self):
        from tools.models.schemas import StakeholderRole
        assert StakeholderRole.RETIRED_EXPERT.value == "RETIRED_EXPERT"
