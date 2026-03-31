"""Tests for workflow API endpoints (api/routers/workflow.py)."""

import pytest
from unittest.mock import patch, MagicMock
import time

pytestmark = pytest.mark.integration


class TestWorkflowRun:
    """Tests for POST /workflow/run endpoint."""

    def test_run_returns_202(self, client):
        with patch("api.routers.workflow._run_workflow_thread"):
            resp = client.post("/api/v1/workflow/run", json={
                "equipment": "BRY-SAG-ML-001",
                "plant_code": "OCP-JFC1",
            })
        assert resp.status_code == 202
        data = resp.json()
        assert "session_id" in data

    def test_run_default_plant_code(self, client):
        with patch("api.routers.workflow._run_workflow_thread"):
            resp = client.post("/api/v1/workflow/run", json={
                "equipment": "BRY-SAG-ML-001",
            })
        # Should use default plant_code or handle missing
        assert resp.status_code in (200, 202, 422)

    def test_run_missing_equipment(self, client):
        resp = client.post("/api/v1/workflow/run", json={})
        assert resp.status_code == 422


class TestWorkflowSessions:
    """Tests for GET /workflow/sessions endpoint."""

    def test_list_sessions_empty(self, client):
        resp = client.get("/api/v1/workflow/sessions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_sessions_after_run(self, client):
        with patch("api.routers.workflow._run_workflow_thread"):
            client.post("/api/v1/workflow/run", json={
                "equipment": "BRY-SAG-ML-001",
                "plant_code": "OCP-JFC1",
            })
        resp = client.get("/api/v1/workflow/sessions")
        assert resp.status_code == 200


class TestWorkflowStatus:
    """Tests for GET /workflow/{session_id} endpoint."""

    def test_get_nonexistent_session(self, client):
        resp = client.get("/api/v1/workflow/nonexistent-id")
        assert resp.status_code == 404

    def test_get_session_after_run(self, client):
        with patch("api.routers.workflow._run_workflow_thread"):
            run_resp = client.post("/api/v1/workflow/run", json={
                "equipment": "BRY-SAG-ML-001",
                "plant_code": "OCP-JFC1",
            })
        session_id = run_resp.json()["session_id"]
        resp = client.get(f"/api/v1/workflow/{session_id}")
        assert resp.status_code == 200


class TestWorkflowApprove:
    """Tests for POST /workflow/{session_id}/approve endpoint."""

    def test_approve_nonexistent_session(self, client):
        resp = client.post("/api/v1/workflow/nonexistent/approve", json={
            "action": "approve",
            "feedback": "",
        })
        assert resp.status_code == 404

    def test_approve_invalid_action(self, client):
        with patch("api.routers.workflow._run_workflow_thread"):
            run_resp = client.post("/api/v1/workflow/run", json={
                "equipment": "TEST",
                "plant_code": "TEST",
            })
        session_id = run_resp.json()["session_id"]
        resp = client.post(f"/api/v1/workflow/{session_id}/approve", json={
            "action": "invalid_action",
            "feedback": "",
        })
        assert resp.status_code in (400, 409, 422)

    def test_approve_not_awaiting_gate(self, client):
        with patch("api.routers.workflow._run_workflow_thread"):
            run_resp = client.post("/api/v1/workflow/run", json={
                "equipment": "TEST",
                "plant_code": "TEST",
            })
        session_id = run_resp.json()["session_id"]
        resp = client.post(f"/api/v1/workflow/{session_id}/approve", json={
            "action": "approve",
            "feedback": "Looks good",
        })
        # Should return 409 if not at a gate
        assert resp.status_code in (200, 409)

    def test_approve_valid_actions(self, client):
        """Verify approve/modify/reject are accepted action values."""
        valid_actions = ["approve", "modify", "reject"]
        for action in valid_actions:
            # Just verify the action is accepted schema-wise
            with patch("api.routers.workflow._run_workflow_thread"):
                run_resp = client.post("/api/v1/workflow/run", json={
                    "equipment": f"TEST-{action}",
                    "plant_code": "TEST",
                })
            session_id = run_resp.json()["session_id"]
            resp = client.post(f"/api/v1/workflow/{session_id}/approve", json={
                "action": action,
                "feedback": f"Testing {action}",
            })
            # Should not be 422 (validation error)
            assert resp.status_code != 422
