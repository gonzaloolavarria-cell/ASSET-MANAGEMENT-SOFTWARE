"""Tests for GAP-W13: Expert Knowledge API endpoints.

Covers all 16 endpoints: consultations, portal, contributions,
experts, and notifications.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from api.database.models import (
    ExpertCardModel,
    ExpertConsultationModel,
    ExpertContributionModel,
    NotificationModel,
)


# ── Helpers ───────────────────────────────────────────────────────────

PREFIX = "/api/v1/expert-knowledge"


def _seed_expert(db: Session, **overrides) -> ExpertCardModel:
    """Insert an ExpertCardModel and return it."""
    defaults = dict(
        expert_id=f"EXP-{uuid.uuid4().hex[:8]}",
        user_id=f"USR-{uuid.uuid4().hex[:6]}",
        name="Ahmed Benali",
        role="RETIRED_EXPERT",
        plant_id="OCP-JFC",
        domains=["MECHANICAL"],
        equipment_expertise=["ET-SAG-MILL"],
        certifications=["OEM-CERT"],
        years_experience=25,
        resolution_count=10,
        contact_method="email",
        languages=["FR", "EN"],
        is_retired=True,
        hourly_rate_usd=50.0,
        availability_hours="MON-FRI 09:00-17:00",
        preferred_contact="IN_APP",
    )
    defaults.update(overrides)
    model = ExpertCardModel(**defaults)
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


def _seed_consultation(db: Session, expert_id: str = "", **overrides) -> ExpertConsultationModel:
    """Insert an ExpertConsultationModel and return it."""
    token = uuid.uuid4().hex
    defaults = dict(
        consultation_id=f"CON-{uuid.uuid4().hex[:8]}",
        session_id=f"SESS-{uuid.uuid4().hex[:6]}",
        expert_id=expert_id or f"EXP-{uuid.uuid4().hex[:8]}",
        technician_id="TECH-001",
        equipment_type_id="ET-SAG-MILL",
        equipment_tag="BRY-SAG-ML-001",
        plant_id="OCP-JFC",
        symptoms_snapshot='["vibration", "temperature"]',
        candidates_snapshot='[{"fm_code": "FM-47", "confidence": 0.65}]',
        ai_suggestion="Check bearing alignment",
        status="REQUESTED",
        token=token,
        token_expires_at=datetime.now() + timedelta(hours=24),
        requested_at=datetime.now(),
        language="fr",
    )
    defaults.update(overrides)
    model = ExpertConsultationModel(**defaults)
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


def _seed_contribution(db: Session, **overrides) -> ExpertContributionModel:
    """Insert an ExpertContributionModel and return it."""
    defaults = dict(
        contribution_id=f"CTR-{uuid.uuid4().hex[:8]}",
        consultation_id=f"CON-{uuid.uuid4().hex[:8]}",
        expert_id=f"EXP-{uuid.uuid4().hex[:8]}",
        equipment_type_id="ET-SAG-MILL",
        fm_codes='["FM-47"]',
        symptom_descriptions='["Excessive vibration on drive end"]',
        diagnostic_steps='["Check bearing alignment", "Measure vibration spectrum"]',
        corrective_actions='["Replace bearing", "Realign coupling"]',
        tips="Always check oil temperature first",
        status="RAW",
    )
    defaults.update(overrides)
    model = ExpertContributionModel(**defaults)
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


# ══════════════════════════════════════════════════════════════════════
# Consultation Endpoints
# ══════════════════════════════════════════════════════════════════════


class TestCreateConsultation:
    def test_creates_consultation(self, client, db_session):
        expert = _seed_expert(db_session)
        body = {
            "session": {
                "session_id": "SESS-001",
                "technician_id": "TECH-001",
                "equipment_type_id": "ET-SAG-MILL",
                "equipment_tag": "BRY-SAG-ML-001",
                "plant_id": "OCP-JFC",
                "symptoms": ["vibration"],
                "candidates": [{"fm_code": "FM-47", "confidence": 0.65}],
            },
            "expert_id": expert.expert_id,
            "ai_suggestion": "Check bearing alignment",
            "language": "fr",
        }
        resp = client.post(f"{PREFIX}/consultations", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["expert_id"] == expert.expert_id
        assert data["status"] == "REQUESTED"
        assert data["token"] is not None
        assert data["language"] == "fr"


class TestGetConsultation:
    def test_get_existing(self, client, db_session):
        con = _seed_consultation(db_session)
        resp = client.get(f"{PREFIX}/consultations/{con.consultation_id}")
        assert resp.status_code == 200
        assert resp.json()["consultation_id"] == con.consultation_id

    def test_get_missing_returns_404(self, client):
        resp = client.get(f"{PREFIX}/consultations/NONEXISTENT")
        assert resp.status_code == 404


class TestListConsultations:
    def test_list_empty(self, client):
        resp = client.get(f"{PREFIX}/consultations")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_with_data(self, client, db_session):
        _seed_consultation(db_session, expert_id="EXP-A")
        _seed_consultation(db_session, expert_id="EXP-B")
        resp = client.get(f"{PREFIX}/consultations")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_filter_by_expert(self, client, db_session):
        _seed_consultation(db_session, expert_id="EXP-A")
        _seed_consultation(db_session, expert_id="EXP-B")
        resp = client.get(f"{PREFIX}/consultations", params={"expert_id": "EXP-A"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["expert_id"] == "EXP-A"

    def test_filter_by_status(self, client, db_session):
        _seed_consultation(db_session, status="REQUESTED")
        _seed_consultation(db_session, status="RESPONDED")
        resp = client.get(f"{PREFIX}/consultations", params={"status": "RESPONDED"})
        assert len(resp.json()) == 1


class TestMarkViewed:
    def test_mark_viewed(self, client, db_session):
        con = _seed_consultation(db_session)
        resp = client.put(f"{PREFIX}/consultations/{con.consultation_id}/view")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "VIEWED"
        assert data["viewed_at"] is not None

    def test_mark_viewed_missing(self, client):
        resp = client.put(f"{PREFIX}/consultations/MISSING/view")
        assert resp.status_code == 404


class TestSubmitResponse:
    def test_submit_response(self, client, db_session):
        con = _seed_consultation(db_session, status="VIEWED", viewed_at=datetime.now())
        body = {
            "expert_guidance": "Check the bearing preload on drive end. FM-47 is likely.",
            "fm_codes": ["FM-47"],
            "confidence": 0.85,
        }
        resp = client.put(
            f"{PREFIX}/consultations/{con.consultation_id}/respond",
            json=body,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "RESPONDED"
        assert data["expert_guidance"] == body["expert_guidance"]
        assert data["expert_confidence"] == 0.85

    def test_submit_response_missing(self, client):
        resp = client.put(
            f"{PREFIX}/consultations/MISSING/respond",
            json={"expert_guidance": "test", "confidence": 0.5},
        )
        assert resp.status_code == 404


class TestCloseConsultation:
    def test_close(self, client, db_session):
        con = _seed_consultation(db_session, status="RESPONDED")
        resp = client.put(
            f"{PREFIX}/consultations/{con.consultation_id}/close",
            json={"notes": "Issue resolved"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "CLOSED"

    def test_close_missing(self, client):
        resp = client.put(f"{PREFIX}/consultations/MISSING/close", json={})
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════
# Portal Endpoint
# ══════════════════════════════════════════════════════════════════════


class TestPortalAccess:
    def test_valid_token(self, client, db_session):
        con = _seed_consultation(db_session)
        resp = client.get(f"{PREFIX}/portal/{con.token}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["consultation_id"] == con.consultation_id

    def test_invalid_token(self, client):
        resp = client.get(f"{PREFIX}/portal/invalid-token-abc123")
        assert resp.status_code == 404

    def test_expired_token(self, client, db_session):
        con = _seed_consultation(
            db_session,
            token_expires_at=datetime.now() - timedelta(hours=1),
        )
        resp = client.get(f"{PREFIX}/portal/{con.token}")
        assert resp.status_code == 403


# ══════════════════════════════════════════════════════════════════════
# Contribution Endpoints
# ══════════════════════════════════════════════════════════════════════


class TestCreateContribution:
    def test_create_from_responded_consultation(self, client, db_session):
        con = _seed_consultation(
            db_session,
            status="RESPONDED",
            expert_guidance="Check bearing. FM-47 confirmed.",
            expert_fm_codes='["FM-47"]',
        )
        resp = client.post(
            f"{PREFIX}/contributions",
            json={"consultation_id": con.consultation_id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["consultation_id"] == con.consultation_id
        assert data["status"] == "RAW"

    def test_create_from_non_responded_fails(self, client, db_session):
        con = _seed_consultation(db_session, status="REQUESTED")
        resp = client.post(
            f"{PREFIX}/contributions",
            json={"consultation_id": con.consultation_id},
        )
        assert resp.status_code == 400


class TestListContributions:
    def test_list_empty(self, client):
        resp = client.get(f"{PREFIX}/contributions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_with_filter(self, client, db_session):
        _seed_contribution(db_session, status="RAW")
        _seed_contribution(db_session, status="VALIDATED")
        resp = client.get(f"{PREFIX}/contributions", params={"status": "RAW"})
        assert len(resp.json()) == 1


class TestValidateContribution:
    def test_validate(self, client, db_session):
        ctr = _seed_contribution(db_session, status="RAW")
        body = {"fm_codes": ["FM-47"], "validated_by": "eng-001"}
        resp = client.put(
            f"{PREFIX}/contributions/{ctr.contribution_id}/validate",
            json=body,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "VALIDATED"
        assert data["validated_by"] == "eng-001"

    def test_validate_missing(self, client):
        resp = client.put(
            f"{PREFIX}/contributions/MISSING/validate",
            json={"fm_codes": ["FM-01"], "validated_by": "eng"},
        )
        assert resp.status_code == 404


class TestPromoteContribution:
    def test_promote_validated(self, client, db_session, tmp_path, monkeypatch):
        ctr = _seed_contribution(db_session, status="VALIDATED", validated_by="eng-001")
        # Redirect promotion targets to tmp dirs to avoid side effects
        monkeypatch.setattr(
            "api.services.expert_knowledge_service._SYMPTOM_CATALOG",
            tmp_path / "symptom-catalog.json",
        )
        monkeypatch.setattr(
            "api.services.expert_knowledge_service._TREES_DIR",
            tmp_path / "trees",
        )
        monkeypatch.setattr(
            "api.services.expert_knowledge_service._MANUALS_DIR",
            tmp_path / "manuals",
        )
        monkeypatch.setattr(
            "api.services.expert_knowledge_service._MEMORY_DIR",
            tmp_path / "memory",
        )
        body = {"targets": ["manual", "memory"]}
        resp = client.put(
            f"{PREFIX}/contributions/{ctr.contribution_id}/promote",
            json=body,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "PROMOTED"
        assert "manual" in data["promoted_targets"]

    def test_promote_non_validated_fails(self, client, db_session):
        ctr = _seed_contribution(db_session, status="RAW")
        resp = client.put(
            f"{PREFIX}/contributions/{ctr.contribution_id}/promote",
            json={"targets": ["manual"]},
        )
        assert resp.status_code == 400


# ══════════════════════════════════════════════════════════════════════
# Expert Endpoints
# ══════════════════════════════════════════════════════════════════════


class TestListExperts:
    def test_list_empty(self, client):
        resp = client.get(f"{PREFIX}/experts")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_all(self, client, db_session):
        _seed_expert(db_session, is_retired=True)
        _seed_expert(db_session, is_retired=False)
        resp = client.get(f"{PREFIX}/experts")
        assert len(resp.json()) == 2

    def test_retired_only(self, client, db_session):
        _seed_expert(db_session, expert_id="EXP-RET", is_retired=True)
        _seed_expert(db_session, expert_id="EXP-ACT", is_retired=False)
        resp = client.get(f"{PREFIX}/experts", params={"retired_only": True})
        data = resp.json()
        assert len(data) == 1
        assert data[0]["is_retired"] is True


class TestRegisterExpert:
    def test_register(self, client):
        body = {
            "user_id": "USR-NEW",
            "name": "Mohammed Alaoui",
            "role": "RETIRED_EXPERT",
            "plant_id": "OCP-JFC",
            "domains": ["ELECTRICAL"],
            "equipment_expertise": ["ET-MOTOR"],
            "years_experience": 30,
            "is_retired": True,
            "hourly_rate_usd": 60.0,
            "languages": ["FR", "AR"],
        }
        resp = client.post(f"{PREFIX}/experts", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Mohammed Alaoui"
        assert data["is_retired"] is True
        assert data["expert_id"]  # auto-generated


class TestExpertCompensation:
    def test_compensation_with_consultations(self, client, db_session):
        expert = _seed_expert(db_session)
        _seed_consultation(
            db_session,
            expert_id=expert.expert_id,
            status="RESPONDED",
            response_time_minutes=45.0,
        )
        resp = client.get(f"{PREFIX}/experts/{expert.expert_id}/compensation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["expert_id"] == expert.expert_id
        assert "total_consultations" in data

    def test_compensation_unknown_expert(self, client):
        resp = client.get(f"{PREFIX}/experts/NONEXISTENT/compensation")
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════
# Notification Endpoints
# ══════════════════════════════════════════════════════════════════════


class TestGetNotifications:
    def test_get_notifications(self, client, db_session):
        notif = NotificationModel(
            notification_type="EXPERT_CONSULTATION",
            level="INFO",
            plant_id="OCP-JFC",
            title="New consultation",
            message="Please review",
            recipient_id="EXP-001",
            consultation_id="CON-001",
            channel="IN_APP",
        )
        db_session.add(notif)
        db_session.commit()

        resp = client.get(f"{PREFIX}/notifications/EXP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["recipient_id"] == "EXP-001"

    def test_get_notifications_empty(self, client):
        resp = client.get(f"{PREFIX}/notifications/NOBODY")
        assert resp.status_code == 200
        assert resp.json() == []


class TestMarkNotificationRead:
    def test_mark_read(self, client, db_session):
        notif = NotificationModel(
            notification_type="EXPERT_CONSULTATION",
            level="INFO",
            plant_id="OCP-JFC",
            title="New consultation",
            message="Please review",
            recipient_id="EXP-001",
            consultation_id="CON-001",
            channel="IN_APP",
        )
        db_session.add(notif)
        db_session.commit()
        db_session.refresh(notif)

        resp = client.put(f"{PREFIX}/notifications/{notif.notification_id}/read")
        assert resp.status_code == 200
        data = resp.json()
        assert data["acknowledged"] is True

    def test_mark_read_missing(self, client):
        resp = client.put(f"{PREFIX}/notifications/MISSING-ID/read")
        assert resp.status_code == 404
