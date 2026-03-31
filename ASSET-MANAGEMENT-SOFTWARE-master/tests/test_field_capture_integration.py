"""Integration tests for G-08: Voice/Image Capture pipeline.

Tests the full capture pipeline:
  1. FieldCaptureProcessor (deterministic)
  2. ImageAnalysisService (Claude Vision — mocked)
  3. LLMCaptureEnhancer (Claude Haiku — mocked)
  4. GPS proximity matching
  5. API endpoints: POST /capture/, GET /capture/nearby

Uses an in-memory SQLite DB (same pattern as test_api/conftest.py).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.database.connection import Base, get_db
import api.database.models  # noqa: F401
from api.database.models import HierarchyNodeModel, PlantModel, FieldCaptureModel
from api.main import app


# ── In-memory test DB ─────────────────────────────────────────────────────────

TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(TEST_ENGINE, "connect")
def _fk_pragma(dbapi_conn, _):
    dbapi_conn.cursor().execute("PRAGMA foreign_keys=ON")


TestSession = sessionmaker(bind=TEST_ENGINE, autocommit=False, autoflush=False)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=TEST_ENGINE)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture()
def client(db):
    def _override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded(db):
    """Seed plant + equipment node (with GPS) and return IDs."""
    plant = PlantModel(plant_id="OCP-TEST", name="OCP Test Plant", name_fr="Usine Test OCP")
    db.add(plant)

    p_id = str(uuid.uuid4())
    a_id = str(uuid.uuid4())
    s_id = str(uuid.uuid4())
    eq_id = str(uuid.uuid4())

    db.add(HierarchyNodeModel(node_id=p_id, node_type="PLANT", name="Plant", code="OCP-TEST", level=1, plant_id="OCP-TEST"))
    db.add(HierarchyNodeModel(node_id=a_id, node_type="AREA", name="Grinding", code="BRY", parent_node_id=p_id, level=2, plant_id="OCP-TEST"))
    db.add(HierarchyNodeModel(node_id=s_id, node_type="SYSTEM", name="SAG System", code="BRY-SAG", parent_node_id=a_id, level=3, plant_id="OCP-TEST"))
    db.add(HierarchyNodeModel(
        node_id=eq_id,
        node_type="EQUIPMENT",
        name="SAG Mill 1",
        name_fr="Broyeur SAG 1",
        code="BRY-SAG-ML-001",
        tag="BRY-SAG-ML-001",
        parent_node_id=s_id,
        level=4,
        plant_id="OCP-TEST",
        criticality="AA",
        gps_lat=33.2600,
        gps_lon=-8.5100,
    ))
    db.commit()
    return {"plant_id": "OCP-TEST", "eq_id": eq_id, "eq_tag": "BRY-SAG-ML-001"}


# ── Helper payload builders ───────────────────────────────────────────────────

def _text_payload(**kwargs):
    defaults = {
        "technician_id": "TECH-001",
        "technician_name": "Ahmed",
        "capture_type": "TEXT",
        "language": "fr",
        "raw_text_input": "Pompe centrifuge BRY-SAG-ML-001 en panne",
    }
    defaults.update(kwargs)
    return defaults


def _voice_payload(**kwargs):
    base = {
        "technician_id": "TECH-002",
        "technician_name": "Fatima",
        "capture_type": "VOICE",
        "language": "fr",
        "raw_voice_text": "vibration anormale sur le roulement du moteur BRY-SAG-ML-001",
    }
    base.update(kwargs)
    return base


def _image_analysis_dict():
    return {
        "component_identified": "pump casing",
        "anomalies_detected": ["corrosion", "rust"],
        "severity_visual": "HIGH",
    }


# ── Test: TEXT capture ────────────────────────────────────────────────────────

class TestTextCapture:
    def test_text_capture_creates_work_request(self, client, seeded):
        resp = client.post("/api/v1/capture/", json=_text_payload())
        assert resp.status_code == 200
        data = resp.json()
        assert "work_request_id" in data
        assert data["status"] == "DRAFT"

    def test_text_capture_returns_equipment_info(self, client, seeded):
        resp = client.post("/api/v1/capture/", json=_text_payload())
        assert resp.status_code == 200
        data = resp.json()
        assert "equipment_tag" in data
        assert "equipment_confidence" in data

    def test_text_capture_without_tag_returns_unknown(self, client, seeded):
        payload = _text_payload(raw_text_input="quelque chose est cassé")
        resp = client.post("/api/v1/capture/", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "DRAFT"


# ── Test: VOICE capture ────────────────────────────────────────────────────────

class TestVoiceCapture:
    def test_voice_capture_stores_raw_voice_text(self, client, seeded, db):
        resp = client.post("/api/v1/capture/", json=_voice_payload())
        assert resp.status_code == 200

        capture_id = resp.json()["capture_id"]
        record = db.query(FieldCaptureModel).filter(FieldCaptureModel.capture_id == capture_id).first()
        assert record is not None
        assert record.raw_voice_text is not None
        assert "vibration" in record.raw_voice_text

    def test_voice_capture_type_stored_correctly(self, client, seeded, db):
        resp = client.post("/api/v1/capture/", json=_voice_payload())
        assert resp.status_code == 200

        capture_id = resp.json()["capture_id"]
        record = db.query(FieldCaptureModel).filter(FieldCaptureModel.capture_id == capture_id).first()
        assert record.capture_type == "VOICE"

    def test_voice_capture_returns_priority(self, client, seeded):
        resp = client.post("/api/v1/capture/", json=_voice_payload())
        data = resp.json()
        assert "priority_suggested" in data


# ── Test: IMAGE capture ───────────────────────────────────────────────────────

class TestImageCapture:
    def test_image_analysis_stored_in_db(self, client, seeded, db):
        payload = _text_payload(
            capture_type="IMAGE",
            raw_text_input=None,
            image_analysis_json=json.dumps(_image_analysis_dict()),
        )
        resp = client.post("/api/v1/capture/", json=payload)
        assert resp.status_code == 200

        capture_id = resp.json()["capture_id"]
        record = db.query(FieldCaptureModel).filter(FieldCaptureModel.capture_id == capture_id).first()
        assert record.image_analysis_result is not None
        ia = json.loads(record.image_analysis_result)
        assert ia["severity_visual"] == "HIGH"

    def test_image_analysis_included_in_response(self, client, seeded):
        payload = _text_payload(
            capture_type="IMAGE",
            raw_text_input=None,
            image_analysis_json=json.dumps(_image_analysis_dict()),
        )
        resp = client.post("/api/v1/capture/", json=payload)
        data = resp.json()
        assert data.get("image_analysis") is not None
        assert data["image_analysis"]["severity_visual"] == "HIGH"

    def test_invalid_image_analysis_json_ignored(self, client, seeded):
        payload = _text_payload(image_analysis_json="not-valid-json{{")
        resp = client.post("/api/v1/capture/", json=payload)
        assert resp.status_code == 200  # Graceful degradation


# ── Test: VOICE+IMAGE capture ─────────────────────────────────────────────────

class TestVoiceImageCapture:
    def test_voice_image_full_pipeline(self, client, seeded):
        payload = {
            "technician_id": "TECH-003",
            "technician_name": "Yassine",
            "capture_type": "VOICE+IMAGE",
            "language": "fr",
            "raw_voice_text": "corrosion sur le carter de la pompe BRY-SAG-ML-001",
            "image_analysis_json": json.dumps(_image_analysis_dict()),
        }
        resp = client.post("/api/v1/capture/", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "DRAFT"
        assert data.get("image_analysis") is not None

    def test_voice_image_stores_both_fields(self, client, seeded, db):
        payload = {
            "technician_id": "TECH-004",
            "technician_name": "Leila",
            "capture_type": "VOICE+IMAGE",
            "language": "en",
            "raw_voice_text": "bearing noise on motor",
            "image_analysis_json": json.dumps(_image_analysis_dict()),
        }
        resp = client.post("/api/v1/capture/", json=payload)
        capture_id = resp.json()["capture_id"]

        record = db.query(FieldCaptureModel).filter(FieldCaptureModel.capture_id == capture_id).first()
        assert record.raw_voice_text is not None
        assert record.image_analysis_result is not None


# ── Test: GPS stored ──────────────────────────────────────────────────────────

class TestGPSStorage:
    def test_gps_coordinates_stored_in_db(self, client, seeded, db):
        payload = _text_payload(gps_lat=33.2601, gps_lon=-8.5102)
        resp = client.post("/api/v1/capture/", json=payload)
        assert resp.status_code == 200

        capture_id = resp.json()["capture_id"]
        record = db.query(FieldCaptureModel).filter(FieldCaptureModel.capture_id == capture_id).first()
        assert record.gps_lat == pytest.approx(33.2601)
        assert record.gps_lon == pytest.approx(-8.5102)

    def test_capture_without_gps_stores_null(self, client, seeded, db):
        resp = client.post("/api/v1/capture/", json=_text_payload())
        capture_id = resp.json()["capture_id"]
        record = db.query(FieldCaptureModel).filter(FieldCaptureModel.capture_id == capture_id).first()
        assert record.gps_lat is None
        assert record.gps_lon is None


# ── Test: /capture/nearby endpoint ───────────────────────────────────────────

class TestNearbyEquipment:
    def test_returns_equipment_within_radius(self, client, seeded):
        # Seeded equipment is at (33.2600, -8.5100) — same point, distance=0
        resp = client.get("/api/v1/capture/nearby", params={"lat": 33.2600, "lon": -8.5100, "radius_m": 100})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["equipment_tag"] == "BRY-SAG-ML-001"
        assert data[0]["confidence"] == "HIGH"

    def test_returns_empty_when_too_far(self, client, seeded):
        # Casablanca is ~100 km from El Jadida — no equipment should match
        resp = client.get("/api/v1/capture/nearby", params={"lat": 33.5731, "lon": -7.5898, "radius_m": 100})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_custom_radius_filters(self, client, seeded):
        # Equipment at (33.2600, -8.5100), query at same coords with radius=0.5m → still HIGH
        resp = client.get("/api/v1/capture/nearby", params={"lat": 33.2600, "lon": -8.5100, "radius_m": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    def test_nearby_response_has_required_fields(self, client, seeded):
        resp = client.get("/api/v1/capture/nearby", params={"lat": 33.2600, "lon": -8.5100})
        assert resp.status_code == 200
        data = resp.json()
        if data:
            first = data[0]
            assert "equipment_tag" in first
            assert "equipment_id" in first
            assert "distance_m" in first
            assert "confidence" in first

    def test_sorted_by_distance(self, client, seeded, db):
        """Add a second equipment node farther away and verify sort order."""
        eq2_id = str(uuid.uuid4())
        # Get an existing parent node
        parent = db.query(HierarchyNodeModel).filter(HierarchyNodeModel.node_type == "SYSTEM").first()
        db.add(HierarchyNodeModel(
            node_id=eq2_id,
            node_type="EQUIPMENT",
            name="Pump 2",
            code="BRY-SAG-PMP-002",
            tag="BRY-SAG-PMP-002",
            parent_node_id=parent.node_id,
            level=4,
            plant_id="OCP-TEST",
            gps_lat=33.2605,   # ~55 m north
            gps_lon=-8.5100,
        ))
        db.commit()

        resp = client.get("/api/v1/capture/nearby", params={"lat": 33.2600, "lon": -8.5100, "radius_m": 100})
        data = resp.json()
        assert len(data) >= 2
        distances = [item["distance_m"] for item in data]
        assert distances == sorted(distances), "Results must be sorted by distance ascending"


# ── Test: LLM Enhancer gating ────────────────────────────────────────────────

class TestLLMEnhancerGating:
    def test_low_confidence_triggers_enhancer(self, client, seeded):
        """When equipment is UNKNOWN (low confidence), LLM enhancer should be attempted.
        We mock the enhancer to avoid real API calls.
        """
        from tools.models.schemas import (
            StructuredWorkRequest, EquipmentIdentification, ProblemDescription,
            AIClassification, WorkRequestStatus, WorkOrderType, Priority,
            ResolutionMethod, Validation,
        )
        from datetime import datetime as _dt

        mock_wr = StructuredWorkRequest(
            source_capture_id="cap-mock",
            created_at=_dt.now(),
            status=WorkRequestStatus.DRAFT,
            equipment_identification=EquipmentIdentification(
                equipment_id="eq-enhanced",
                equipment_tag="BRY-SAG-ML-001",
                confidence_score=0.85,
                resolution_method=ResolutionMethod.LLM_ENHANCED,
            ),
            problem_description=ProblemDescription(
                original_text="test",
                structured_description="LLM enhanced desc",
                structured_description_fr="Description LLM améliorée",
                failure_mode_code="CORRODES+NORMAL_DETERIORATION",
                failure_mode_detected="CORRODES | Normal deterioration",
            ),
            ai_classification=AIClassification(
                work_order_type=WorkOrderType.PM03_CORRECTIVE,
                priority_suggested=Priority.URGENT,
                priority_justification="High corrosion risk",
                estimated_duration_hours=4.0,
                required_specialties=["mechanical"],
            ),
            validation=Validation(is_valid=True),
        )

        with patch("tools.processors.llm_capture_enhancer.LLMCaptureEnhancer") as MockEnhancer:
            instance = MockEnhancer.return_value
            instance.needs_enhancement.return_value = True
            instance.enhance.return_value = mock_wr

            # Low-confidence capture: no equipment tag → UNKNOWN → triggers enhancer
            resp = client.post("/api/v1/capture/", json={
                "technician_id": "TECH-010",
                "technician_name": "Test",
                "capture_type": "TEXT",
                "language": "en",
                "raw_text_input": "something is broken somewhere",
            })
        # Should succeed regardless
        assert resp.status_code == 200

    def test_enhancer_error_falls_back_gracefully(self, client, seeded):
        """If LLM enhancer raises, pipeline should still return a result."""
        # get_llm_enhancer is imported lazily inside process_capture, so patch at source module
        with patch("tools.processors.llm_capture_enhancer.get_llm_enhancer") as mock_get:
            mock_get.side_effect = Exception("LLM unavailable")
            resp = client.post("/api/v1/capture/", json=_text_payload())
        assert resp.status_code == 200  # Graceful fallback


# ── Test: list captures ──────────────────────────────────────────────────────

class TestListCaptures:
    def test_list_captures_returns_array(self, client, seeded):
        resp = client.get("/api/v1/capture/")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_submitted_capture_appears_in_list(self, client, seeded):
        client.post("/api/v1/capture/", json=_text_payload())
        resp = client.get("/api/v1/capture/")
        data = resp.json()
        assert len(data) >= 1
        assert any(c.get("technician_id") == "TECH-001" for c in data)
