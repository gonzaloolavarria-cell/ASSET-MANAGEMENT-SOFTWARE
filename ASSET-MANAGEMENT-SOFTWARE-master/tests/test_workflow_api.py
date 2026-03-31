"""Tests for G-17: Workflow API endpoints (POST /workflow/run, GET, POST /approve).

Strategy:
- Tests that check HTTP contract (status codes, validation) use _make_record() to
  inject session records directly, avoiding real workflow thread execution.
- The threading.Event gate synchronization is tested directly in one integration test.
- POST /workflow/run is smoke-tested for correct response shape only (thread runs in
  background and will fail gracefully due to missing API key — that's acceptable).
"""

from __future__ import annotations

import threading
import time
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routers.workflow import _SESSIONS, _SessionRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_sessions():
    """Reset global session registry between tests."""
    _SESSIONS.clear()
    yield
    _SESSIONS.clear()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Helper: inject a pre-built session record (avoids starting real thread)
# ---------------------------------------------------------------------------


def _make_record(status: str = "RUNNING", milestone: int = 0, equipment: str = "SAG Mill Test") -> _SessionRecord:
    sid = str(uuid.uuid4())
    r = _SessionRecord(sid, equipment, "OCP-TEST")
    r.status = status
    r.current_milestone = milestone
    _SESSIONS[sid] = r
    return r


# ---------------------------------------------------------------------------
# POST /workflow/run
# ---------------------------------------------------------------------------


class TestStartWorkflow:

    def test_returns_202_with_session_id(self, client):
        """POST /workflow/run returns 202 and a valid UUID session_id."""
        # Patch StrategyWorkflow at its source so the lazy import in the thread
        # gets the mock instead of the real class (which needs ANTHROPIC_API_KEY).
        with patch("agents.orchestration.workflow.StrategyWorkflow") as MockWF:
            mock_wf = MagicMock()
            mock_session = MagicMock()
            mock_session.get_entity_counts.return_value = {"nodes": 5}
            mock_session.sap_upload_package = None
            mock_wf.run.return_value = mock_session
            mock_wf.milestones = []
            MockWF.return_value = mock_wf

            resp = client.post("/api/v1/workflow/run", json={
                "equipment": "SAG Mill Test",
                "plant_code": "OCP-TEST",
            })

        assert resp.status_code == 202
        data = resp.json()
        assert "session_id" in data
        assert data["status"] == "STARTING"
        # UUID format: 8-4-4-4-12
        assert len(data["session_id"]) == 36

    def test_missing_equipment_returns_422(self, client):
        """equipment field is required — missing it should return 422."""
        resp = client.post("/api/v1/workflow/run", json={"plant_code": "OCP"})
        assert resp.status_code == 422

    def test_session_registered_in_store(self, client):
        """After POST, a session record exists in _SESSIONS."""
        with patch("agents.orchestration.workflow.StrategyWorkflow") as MockWF:
            mock_wf = MagicMock()
            mock_wf.run.return_value = MagicMock(
                get_entity_counts=lambda: {}, sap_upload_package=None
            )
            mock_wf.milestones = []
            MockWF.return_value = mock_wf

            resp = client.post("/api/v1/workflow/run", json={
                "equipment": "Ball Mill BM-201",
                "plant_code": "OCP-JFC",
            })

        session_id = resp.json()["session_id"]
        assert session_id in _SESSIONS
        assert _SESSIONS[session_id].equipment == "Ball Mill BM-201"
        assert _SESSIONS[session_id].plant_code == "OCP-JFC"


# ---------------------------------------------------------------------------
# GET /workflow/{session_id}
# ---------------------------------------------------------------------------


class TestGetWorkflowStatus:

    def test_unknown_session_returns_404(self, client):
        resp = client.get(f"/api/v1/workflow/{uuid.uuid4()}")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_running_session_returns_correct_shape(self, client):
        record = _make_record(status="RUNNING", milestone=1)
        resp = client.get(f"/api/v1/workflow/{record.session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "RUNNING"
        assert data["current_milestone"] == 1
        assert data["equipment"] == "SAG Mill Test"
        assert data["plant_code"] == "OCP-TEST"
        assert "session_id" in data
        assert "started_at" in data

    def test_awaiting_approval_includes_gate_summary(self, client):
        record = _make_record(status="AWAITING_APPROVAL", milestone=2)
        record.gate_summary = "=== M2: FMECA ===\n0 errors, 2 warnings"
        resp = client.get(f"/api/v1/workflow/{record.session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "AWAITING_APPROVAL"
        assert data["current_milestone"] == 2
        assert "M2" in data["gate_summary"]

    def test_completed_session_has_entity_counts(self, client):
        record = _make_record(status="COMPLETED")
        record.entity_counts = {"nodes": 10, "failure_modes": 5}
        resp = client.get(f"/api/v1/workflow/{record.session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "COMPLETED"
        assert data["entity_counts"]["nodes"] == 10

    def test_failed_session_has_error_message(self, client):
        record = _make_record(status="FAILED")
        record.error = "ANTHROPIC_API_KEY not set"
        resp = client.get(f"/api/v1/workflow/{record.session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "FAILED"
        assert "ANTHROPIC_API_KEY" in data["error"]


# ---------------------------------------------------------------------------
# POST /workflow/{session_id}/approve
# ---------------------------------------------------------------------------


class TestApproveGate:

    def test_approve_action_fires_gate_event(self, client):
        """Posting approve sets gate action and fires the threading.Event."""
        record = _make_record(status="AWAITING_APPROVAL", milestone=1)
        record.gate_summary = "M1 gate summary"

        resp = client.post(f"/api/v1/workflow/{record.session_id}/approve", json={
            "action": "approve",
            "feedback": "",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "approve"
        assert data["milestone"] == 1
        # Verify internal state
        assert record._gate_action == "approve"
        assert record._gate_event.is_set()

    def test_modify_action_stores_feedback(self, client):
        record = _make_record(status="AWAITING_APPROVAL", milestone=2)

        resp = client.post(f"/api/v1/workflow/{record.session_id}/approve", json={
            "action": "modify",
            "feedback": "Add more failure modes to the FMECA",
        })

        assert resp.status_code == 200
        assert record._gate_action == "modify"
        assert record._gate_feedback == "Add more failure modes to the FMECA"

    def test_reject_action(self, client):
        record = _make_record(status="AWAITING_APPROVAL", milestone=3)

        resp = client.post(f"/api/v1/workflow/{record.session_id}/approve", json={
            "action": "reject",
            "feedback": "Strategy not aligned with OCP standards",
        })

        assert resp.status_code == 200
        assert record._gate_action == "reject"

    def test_invalid_action_returns_422(self, client):
        """action must be one of: approve | modify | reject."""
        record = _make_record(status="AWAITING_APPROVAL", milestone=1)
        resp = client.post(f"/api/v1/workflow/{record.session_id}/approve", json={
            "action": "skip",  # invalid
            "feedback": "",
        })
        assert resp.status_code == 422

    def test_approve_when_not_awaiting_returns_409(self, client):
        """Cannot approve a session that is still RUNNING."""
        record = _make_record(status="RUNNING", milestone=1)
        resp = client.post(f"/api/v1/workflow/{record.session_id}/approve", json={
            "action": "approve",
        })
        assert resp.status_code == 409
        assert "not awaiting approval" in resp.json()["detail"].lower()

    def test_approve_completed_session_returns_409(self, client):
        """Cannot approve a session that is already COMPLETED."""
        record = _make_record(status="COMPLETED")
        resp = client.post(f"/api/v1/workflow/{record.session_id}/approve", json={
            "action": "approve",
        })
        assert resp.status_code == 409

    def test_unknown_session_returns_404(self, client):
        resp = client.post(f"/api/v1/workflow/{uuid.uuid4()}/approve", json={
            "action": "approve",
        })
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /workflow/sessions
# ---------------------------------------------------------------------------


class TestListSessions:

    def test_empty_returns_empty_list(self, client):
        resp = client.get("/api/v1/workflow/sessions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_multiple_sessions_all_returned(self, client):
        _make_record(status="COMPLETED", equipment="SAG Mill")
        _make_record(status="RUNNING", equipment="Ball Mill")
        resp = client.get("/api/v1/workflow/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        statuses = {s["status"] for s in data}
        assert statuses == {"COMPLETED", "RUNNING"}


# ---------------------------------------------------------------------------
# Integration: threading gate synchronization
# ---------------------------------------------------------------------------


class TestGateSynchronization:

    def test_workflow_thread_blocks_until_approved(self, client):
        """Simulate the api_approval_fn pause/resume via threading.Event.

        This validates the core G-17 mechanism: a background thread pauses at
        a gate, the HTTP layer unblocks it by setting the event, and the thread
        reads the correct action.
        """
        record = _SessionRecord("sync-gate-test", "Crusher", "OCP-JFC")
        _SESSIONS["sync-gate-test"] = record

        gate_results: dict = {}

        def simulated_api_gate_fn():
            """Simulate what _run_workflow_thread does at a gate."""
            record.status = "AWAITING_APPROVAL"
            record.current_milestone = 2
            record.gate_summary = "M2 presented — 0 errors"
            record._gate_event.clear()
            record._gate_event.wait(timeout=5)  # block until approved
            gate_results["action"] = record._gate_action
            gate_results["feedback"] = record._gate_feedback

        thread = threading.Thread(target=simulated_api_gate_fn, daemon=True)
        thread.start()

        # Thread must be blocked (give it time to reach wait())
        time.sleep(0.1)
        assert record.status == "AWAITING_APPROVAL"
        assert not record._gate_event.is_set()

        # Submit approval via the API
        resp = client.post("/api/v1/workflow/sync-gate-test/approve", json={
            "action": "modify",
            "feedback": "Please add PdM tasks",
        })
        assert resp.status_code == 200

        # Thread should unblock and complete
        thread.join(timeout=3)
        assert not thread.is_alive(), "Thread did not unblock after approval"
        assert gate_results["action"] == "modify"
        assert gate_results["feedback"] == "Please add PdM tasks"
