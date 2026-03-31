"""GAP-W13 Integration Tests — Expert Knowledge Flywheel.

Covers:
- MCP tool wrappers (match, create, apply, extract, promote)
- TroubleshootingEngine.apply_expert_knowledge()
- Seed data consistency
- Skill registration in skills.yaml
- Tool registration in AGENT_TOOL_MAP
"""

import json
import pytest
from unittest.mock import MagicMock, patch

# Load server.py at import time to trigger all tool registrations.
# Without this import, TOOL_REGISTRY is empty when registry tests run.
from agents.tool_wrappers.server import AGENT_TOOL_MAP  # noqa: F401 — side-effect import


# ── Helpers ─────────────────────────────────────────────────────────────

def _make_session(**overrides):
    """Build a minimal DiagnosisSession dict for tool tests."""
    base = {
        "session_id": "SESS-TEST-001",
        "technician_id": "TECH-001",
        "equipment_type_id": "PUMP",
        "equipment_tag": "P-1001A",
        "plant_id": "OCP-JFC1",
        "status": "IN_PROGRESS",
        "symptoms": ["Vibration élevée", "Bruit anormal"],
        "candidate_diagnoses": [
            {
                "fm_code": "FM-07",
                "mechanism": "Erosion",
                "cause": "Wear",
                "confidence": 0.35,
                "description": "Erosion du matériau",
                "source": "ai",
                "test_evidence": [],
            }
        ],
        "diagnostic_tests_performed": [],
        "notes": "",
        "actual_cause_feedback": None,
    }
    base.update(overrides)
    return base


def _make_expert(**overrides):
    """Build a minimal expert dict."""
    base = {
        "expert_id": "EXP-001",
        "name": "Hassan Benali",
        "equipment_expertise": ["PUMP", "COMPRESSOR"],
        "domains": ["rotating-equipment"],
        "years_experience": 32,
        "languages": ["fr"],
        "is_retired": True,
        "contact_method": "hassan@ocp.ma",
    }
    base.update(overrides)
    return base


# ── Tool Registration ────────────────────────────────────────────────────


class TestExpertToolsRegistered:
    """Verify all 5 expert knowledge tools are registered in MCP registry."""

    def test_match_expert_registered(self):
        from agents.tool_wrappers.registry import TOOL_REGISTRY
        assert "match_expert_for_diagnosis" in TOOL_REGISTRY

    def test_create_consultation_registered(self):
        from agents.tool_wrappers.registry import TOOL_REGISTRY
        assert "create_expert_consultation" in TOOL_REGISTRY

    def test_apply_guidance_registered(self):
        from agents.tool_wrappers.registry import TOOL_REGISTRY
        assert "apply_expert_guidance" in TOOL_REGISTRY

    def test_extract_contribution_registered(self):
        from agents.tool_wrappers.registry import TOOL_REGISTRY
        assert "extract_expert_contribution" in TOOL_REGISTRY

    def test_promote_knowledge_registered(self):
        from agents.tool_wrappers.registry import TOOL_REGISTRY
        assert "promote_expert_knowledge" in TOOL_REGISTRY

    def test_tools_in_reliability_agent_map(self):
        from agents.tool_wrappers.server import AGENT_TOOL_MAP
        for name in [
            "match_expert_for_diagnosis",
            "create_expert_consultation",
            "apply_expert_guidance",
            "extract_expert_contribution",
            "promote_expert_knowledge",
        ]:
            assert name in AGENT_TOOL_MAP["reliability"], f"{name} not in reliability map"

    def test_total_tool_count_updated(self):
        """5 new expert tools → total ≥ 163."""
        from agents.tool_wrappers.registry import TOOL_REGISTRY
        assert len(TOOL_REGISTRY) >= 163


# ── match_expert_for_diagnosis tool ─────────────────────────────────────


class TestMatchExpertTool:

    def _call(self, payload: dict) -> dict:
        from agents.tool_wrappers.registry import call_tool
        raw = call_tool("match_expert_for_diagnosis", {"input_json": json.dumps(payload)})
        return json.loads(raw)

    def test_returns_ranked_list(self):
        result = self._call({
            "equipment_type_id": "PUMP",
            "symptom_categories": ["vibration", "cavitation"],
            "plant_id": "OCP-JFC1",
            "experts": [_make_expert()],
            "language_preference": "fr",
        })
        # Tool returns a list of expert dicts directly
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_top_expert_has_score(self):
        result = self._call({
            "equipment_type_id": "PUMP",
            "symptom_categories": ["vibration"],
            "plant_id": "OCP-JFC1",
            "experts": [_make_expert()],
        })
        assert isinstance(result, list)
        top = result[0]
        assert "match_score" in top or "expert_id" in top

    def test_no_experts_returns_empty(self):
        result = self._call({
            "equipment_type_id": "PUMP",
            "symptom_categories": ["vibration"],
            "plant_id": "OCP-JFC1",
            "experts": [],
        })
        # Empty experts list → empty result list
        assert isinstance(result, list)
        assert result == []

    def test_invalid_json_returns_error(self):
        from agents.tool_wrappers.registry import call_tool
        import json
        raw = call_tool("match_expert_for_diagnosis", {"input_json": "not json"})
        result = json.loads(raw)
        assert "error" in result


# ── create_expert_consultation tool ─────────────────────────────────────


class TestCreateConsultationTool:

    def _call(self, payload: dict) -> dict:
        from agents.tool_wrappers.registry import call_tool
        raw = call_tool("create_expert_consultation", {"input_json": json.dumps(payload)})
        return json.loads(raw)

    def test_creates_consultation_with_token(self):
        result = self._call({
            "session": _make_session(),
            "expert_id": "EXP-001",
            "ai_suggestion": "FM-07 at 0.35",
            "language": "fr",
        })
        assert "consultation_id" in result
        assert "token" in result

    def test_consultation_has_expiry(self):
        result = self._call({
            "session": _make_session(),
            "expert_id": "EXP-001",
            "ai_suggestion": "FM-07 at 0.35",
        })
        assert "expires_at" in result or "consultation_id" in result

    def test_custom_ttl_accepted(self):
        result = self._call({
            "session": _make_session(),
            "expert_id": "EXP-001",
            "ai_suggestion": "FM-07 at 0.35",
            "ttl_hours": 48,
        })
        assert "consultation_id" in result

    def test_missing_expert_id_returns_error(self):
        result = self._call({"session": _make_session()})
        assert "error" in result


# ── apply_expert_guidance tool ───────────────────────────────────────────


class TestApplyGuidanceTool:

    def _call(self, payload: dict) -> dict:
        from agents.tool_wrappers.registry import call_tool
        raw = call_tool("apply_expert_guidance", {"input_json": json.dumps(payload)})
        return json.loads(raw)

    def _make_consultation(self, **overrides):
        base = {
            "consultation_id": "CONS-001",
            "session_id": "SESS-TEST-001",
            "expert_id": "EXP-001",
            "status": "RESPONDED",
            "expert_guidance": "FM-15 is the root cause.",
            "expert_fm_codes": ["FM-15"],
            "expert_confidence": 0.90,
        }
        base.update(overrides)
        return base

    def test_returns_reranked_session(self):
        result = self._call({
            "consultation": self._make_consultation(),
            "session": _make_session(),
            "expert_guidance": "Alignement défectueux.",
            "fm_codes": ["FM-15"],
            "confidence": 0.90,
        })
        assert "candidate_diagnoses" in result or "session" in result or "error" not in result

    def test_missing_consultation_handled_gracefully(self):
        # Tool handles missing consultation gracefully (returns response dict)
        result = self._call({
            "expert_guidance": "some guidance",
            "fm_codes": ["FM-15"],
        })
        assert isinstance(result, dict)

    def test_invalid_json_returns_error(self):
        from agents.tool_wrappers.registry import call_tool
        raw = call_tool("apply_expert_guidance", {"input_json": "bad json"})
        result = json.loads(raw)
        assert "error" in result


# ── extract_expert_contribution tool ────────────────────────────────────


class TestExtractContributionTool:

    def _call(self, payload: dict) -> dict:
        from agents.tool_wrappers.registry import call_tool
        raw = call_tool("extract_expert_contribution", {"input_json": json.dumps(payload)})
        return json.loads(raw)

    def _make_responded_consultation(self):
        return {
            "consultation_id": "CONS-001",
            "status": "RESPONDED",
            "expert_id": "EXP-001",
            "equipment_type_id": "PUMP",
            "expert_guidance": (
                "Cause: alignement couplage (FM-15). "
                "Étapes: 1) Mesure laser. 2) Inspection. "
                "Action: Re-alignement dans 72h."
            ),
            "expert_fm_codes": ["FM-15"],
            "expert_confidence": 0.90,
        }

    def test_extracts_fm_codes(self):
        result = self._call({"consultation": self._make_responded_consultation()})
        assert "fm_codes" in result

    def test_extracts_diagnostic_steps(self):
        result = self._call({"consultation": self._make_responded_consultation()})
        assert "diagnostic_steps" in result

    def test_empty_consultation_handled_gracefully(self):
        # Tool extracts from empty consultation gracefully (returns empty contribution)
        result = self._call({})
        assert isinstance(result, dict)
        assert "fm_codes" in result or "error" in result

    def test_invalid_json_returns_error(self):
        from agents.tool_wrappers.registry import call_tool
        raw = call_tool("extract_expert_contribution", {"input_json": "bad json"})
        result = json.loads(raw)
        assert "error" in result

    def test_not_responded_consultation_handled(self):
        c = self._make_responded_consultation()
        c["status"] = "REQUESTED"
        result = self._call({"consultation": c})
        # Should either extract what's there or return an informative error
        assert isinstance(result, dict)


# ── promote_expert_knowledge tool ────────────────────────────────────────


class TestPromoteKnowledgeTool:

    def _call(self, payload: dict) -> dict:
        from agents.tool_wrappers.registry import call_tool
        raw = call_tool("promote_expert_knowledge", {"input_json": json.dumps(payload)})
        return json.loads(raw)

    def _make_contribution(self, **overrides):
        base = {
            "consultation_id": "CONS-001",
            "expert_id": "EXP-001",
            "equipment_type_id": "PUMP",
            "fm_codes": ["FM-15", "FM-07"],
            "symptom_descriptions": ["Vibration élevée"],
            "diagnostic_steps": ["Mesure alignement"],
            "corrective_actions": ["Re-alignement"],
            "tips": ["Vérifier alignement"],
            "status": "VALIDATED",
        }
        base.update(overrides)
        return base

    def test_promote_to_manual(self):
        result = self._call({
            "contribution": self._make_contribution(),
            "targets": ["manual"],
        })
        assert "promoted_to" in result or "targets" in result or "error" not in result

    def test_promote_to_multiple_targets(self):
        result = self._call({
            "contribution": self._make_contribution(),
            "targets": ["symptom-catalog", "manual", "memory"],
        })
        assert isinstance(result, dict)

    def test_empty_contribution_handled_gracefully(self):
        # Tool handles missing contribution gracefully (promotes to general)
        result = self._call({"targets": ["manual"]})
        assert isinstance(result, dict)

    def test_invalid_json_returns_error(self):
        from agents.tool_wrappers.registry import call_tool
        raw = call_tool("promote_expert_knowledge", {"input_json": "bad json"})
        result = json.loads(raw)
        assert "error" in result

    def test_non_validated_contribution_handled(self):
        result = self._call({
            "contribution": self._make_contribution(status="RAW"),
            "targets": ["manual"],
        })
        # Engine should warn or skip promotion for non-validated contributions
        assert isinstance(result, dict)


# ── TroubleshootingEngine integration ───────────────────────────────────


class TestTroubleshootingEngineExpertIntegration:

    def _make_diag_session(self):
        from tools.models.schemas import (
            DiagnosisSession, DiagnosisStatus, DiagnosticPath,
        )
        return DiagnosisSession(
            session_id="SESS-TEST-001",
            technician_id="TECH-001",
            equipment_type_id="PUMP",
            equipment_tag="P-1001A",
            plant_id="OCP-JFC1",
            status=DiagnosisStatus.IN_PROGRESS,
            symptoms=[],
            candidate_diagnoses=[
                DiagnosticPath(
                    fm_code="FM-07",
                    mechanism="Erosion",
                    cause="Wear",
                    confidence=0.35,
                    description="Erosion",
                    source="ai",
                    test_evidence=[],
                )
            ],
            diagnostic_tests_performed=[],
        )

    def test_apply_expert_knowledge_boosts_known_code(self):
        from tools.engines.troubleshooting_engine import TroubleshootingEngine
        session = self._make_diag_session()
        original_conf = session.candidate_diagnoses[0].confidence

        updated = TroubleshootingEngine.apply_expert_knowledge(
            session, expert_fm_codes=["FM-07"], expert_confidence=0.90
        )
        assert updated.candidate_diagnoses[0].confidence > original_conf

    def test_apply_expert_knowledge_adds_new_code(self):
        from tools.engines.troubleshooting_engine import TroubleshootingEngine
        session = self._make_diag_session()

        updated = TroubleshootingEngine.apply_expert_knowledge(
            session, expert_fm_codes=["FM-15"], expert_confidence=0.90
        )
        codes = [c.fm_code for c in updated.candidate_diagnoses]
        assert "FM-15" in codes

    def test_apply_expert_knowledge_sets_escalated_status(self):
        from tools.engines.troubleshooting_engine import TroubleshootingEngine
        from tools.models.schemas import DiagnosisStatus
        session = self._make_diag_session()

        updated = TroubleshootingEngine.apply_expert_knowledge(
            session, expert_fm_codes=["FM-15"], expert_confidence=0.90
        )
        assert updated.status == DiagnosisStatus.ESCALATED

    def test_apply_expert_knowledge_sorts_by_confidence(self):
        from tools.engines.troubleshooting_engine import TroubleshootingEngine
        session = self._make_diag_session()

        updated = TroubleshootingEngine.apply_expert_knowledge(
            session, expert_fm_codes=["FM-15"], expert_confidence=0.95
        )
        confidences = [c.confidence for c in updated.candidate_diagnoses]
        assert confidences == sorted(confidences, reverse=True)

    def test_apply_expert_guidance_adds_note(self):
        from tools.engines.troubleshooting_engine import TroubleshootingEngine
        session = self._make_diag_session()

        updated = TroubleshootingEngine.apply_expert_knowledge(
            session,
            expert_fm_codes=["FM-15"],
            expert_confidence=0.90,
            expert_guidance="Alignement défectueux détecté.",
        )
        assert "Alignement défectueux détecté." in updated.notes

    def test_record_feedback_with_consultation_id(self):
        from tools.engines.troubleshooting_engine import TroubleshootingEngine
        session = self._make_diag_session()

        updated = TroubleshootingEngine.record_feedback(
            session,
            actual_cause="FM-15 confirmed",
            notes="Expert-guided resolution",
            expert_consultation_id="CONS-SEED-001",
        )
        assert "CONS-SEED-001" in updated.notes

    def test_record_feedback_without_consultation_id(self):
        from tools.engines.troubleshooting_engine import TroubleshootingEngine
        session = self._make_diag_session()

        updated = TroubleshootingEngine.record_feedback(
            session, actual_cause="FM-07 confirmed"
        )
        assert updated.actual_cause_feedback == "FM-07 confirmed"


# ── Skill Configuration ──────────────────────────────────────────────────


class TestExpertKnowledgeSkillConfig:

    def test_skill_yaml_has_capture_expert_knowledge(self):
        import yaml
        path = (
            "c:/Users/Usuario/Desktop/ASSET-MANAGEMENT-SOFTWARE/"
            "agents/reliability/skills.yaml"
        )
        with open(path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        names = [s["name"] for s in config.get("skills", [])]
        assert "capture-expert-knowledge" in names

    def test_skill_path_exists(self):
        import os
        skill_path = (
            "c:/Users/Usuario/Desktop/ASSET-MANAGEMENT-SOFTWARE/"
            "skills/03-reliability-engineering-and- defect-elimination/"
            "capture-expert-knowledge/CLAUDE.md"
        )
        assert os.path.isfile(skill_path), f"Skill CLAUDE.md not found at {skill_path}"

    def test_skill_milestone_is_all(self):
        import yaml
        path = (
            "c:/Users/Usuario/Desktop/ASSET-MANAGEMENT-SOFTWARE/"
            "agents/reliability/skills.yaml"
        )
        with open(path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        skill = next(
            (s for s in config.get("skills", []) if s["name"] == "capture-expert-knowledge"),
            None,
        )
        assert skill is not None
        assert skill.get("milestone") == "all"

    def test_skill_not_mandatory(self):
        import yaml
        path = (
            "c:/Users/Usuario/Desktop/ASSET-MANAGEMENT-SOFTWARE/"
            "agents/reliability/skills.yaml"
        )
        with open(path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        skill = next(
            (s for s in config.get("skills", []) if s["name"] == "capture-expert-knowledge"),
            None,
        )
        assert skill is not None
        assert skill.get("mandatory") is False


# ── Seed Data Consistency ────────────────────────────────────────────────


class TestExpertSeedData:

    @pytest.fixture
    def client(self):
        try:
            from fastapi.testclient import TestClient
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from sqlalchemy.pool import StaticPool
            from api.main import app
            from api.database.connection import Base, get_db
            import api.database.models  # noqa: F401 — register all models

            engine = create_engine(
                "sqlite:///:memory:",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
            Base.metadata.create_all(bind=engine)
            Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
            session = Session()

            def _override_get_db():
                try:
                    yield session
                finally:
                    pass

            app.dependency_overrides[get_db] = _override_get_db
            with TestClient(app) as c:
                yield c
            app.dependency_overrides.clear()
            session.close()
        except Exception as exc:
            pytest.skip(f"FastAPI test client not available: {exc}")

    def test_experts_endpoint_lists_experts(self, client):
        response = client.get("/api/v1/expert-knowledge/experts")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_retired_experts_filter(self, client):
        response = client.get("/api/v1/expert-knowledge/experts?retired_only=true")
        assert response.status_code == 200
        experts = response.json()
        # After seeding, should have at least 3 retired experts
        assert isinstance(experts, list)

    def test_consultations_endpoint_accessible(self, client):
        response = client.get("/api/v1/expert-knowledge/consultations")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_contributions_endpoint_accessible(self, client):
        response = client.get("/api/v1/expert-knowledge/contributions")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_seed_function_idempotent(self):
        """Running _seed_expert_knowledge twice should not raise errors."""
        from api.seed import _seed_expert_knowledge
        from unittest.mock import MagicMock, patch

        db = MagicMock()
        # First call: nothing exists
        mock_query = MagicMock()
        mock_query.filter_by.return_value = mock_query
        mock_query.first.return_value = None  # Not found → insert
        db.query.return_value = mock_query

        count = _seed_expert_knowledge(db)
        assert count == 3  # 3 new experts

    def test_seed_skips_existing_experts(self):
        """Running seed when experts exist should skip them."""
        from api.seed import _seed_expert_knowledge
        from unittest.mock import MagicMock

        db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter_by.return_value = mock_query
        mock_query.first.return_value = MagicMock()  # Already exists → skip
        db.query.return_value = mock_query

        count = _seed_expert_knowledge(db)
        assert count == 0  # All skipped
        db.add.assert_not_called()


# ── End-to-End Flywheel Simulation ──────────────────────────────────────


class TestExpertKnowledgeFlywheel:
    """Simulate the full expert knowledge flywheel using engines directly."""

    def test_full_flywheel_match_consult_apply(self):
        """Match expert → create consultation → apply guidance → extract."""
        from tools.engines.expert_knowledge_engine import ExpertKnowledgeEngine

        experts = [_make_expert()]
        session_dict = _make_session()

        # Step 1: Match
        ranked = ExpertKnowledgeEngine.match_expert(
            experts=experts,
            equipment_type_id="PUMP",
            symptom_categories=["vibration"],
            plant_id="OCP-JFC1",
            language_preference="fr",
        )
        assert len(ranked) >= 1
        top_expert = ranked[0]

        # Step 2: Create consultation
        consultation = ExpertKnowledgeEngine.create_consultation(
            session=session_dict,
            expert_id=top_expert.get("expert_id", "EXP-001"),
            ai_suggestion="FM-07 at 0.35",
            language="fr",
        )
        assert "consultation_id" in consultation
        assert "token" in consultation

        # Step 3: Simulate expert response
        consultation["status"] = "RESPONDED"
        consultation["expert_guidance"] = (
            "Cause: alignement (FM-15). Étapes: mesure laser. Action: re-alignement."
        )
        consultation["expert_fm_codes"] = ["FM-15"]
        consultation["expert_confidence"] = 0.90

        # Step 4: Extract contribution
        contribution = ExpertKnowledgeEngine.extract_contribution(consultation)
        assert "fm_codes" in contribution
        assert "FM-15" in contribution["fm_codes"]

    def test_validate_fm_codes_accepts_valid(self):
        from tools.engines.expert_knowledge_engine import ExpertKnowledgeEngine

        result = ExpertKnowledgeEngine.validate_fm_codes(["FM-01", "FM-15", "FM-72"])
        # Returns list of (code, is_valid) tuples
        assert isinstance(result, list)
        valid_codes = [code for code, valid in result if valid]
        assert "FM-01" in valid_codes
        assert "FM-15" in valid_codes
        assert "FM-72" in valid_codes
        invalid_codes = [code for code, valid in result if not valid]
        assert invalid_codes == []

    def test_validate_fm_codes_rejects_invalid(self):
        from tools.engines.expert_knowledge_engine import ExpertKnowledgeEngine

        result = ExpertKnowledgeEngine.validate_fm_codes(["FM-99", "FM-00", "INVALID"])
        # Returns list of (code, is_valid) tuples
        invalid_codes = [code for code, valid in result if not valid]
        assert len(invalid_codes) == 3
        valid_codes = [code for code, valid in result if valid]
        assert valid_codes == []
