"""API integration tests for deliverables router — GAP-W10.

Uses the conftest.py fixtures (in-memory SQLite, TestClient).
"""

import pytest


PREFIX = "/api/v1/deliverables"


def _make_deliverable(client, **overrides):
    """Helper to create a deliverable and return the response dict."""
    data = {
        "name": "Hierarchy Build",
        "category": "HIERARCHY",
        "milestone": 1,
        "estimated_hours": 2.0,
        "client_slug": "ocp",
        "project_slug": "jfc",
    }
    data.update(overrides)
    r = client.post(f"{PREFIX}/", json=data)
    assert r.status_code == 200, r.text
    return r.json()


class TestDeliverableCRUD:

    def test_create_deliverable(self, client):
        data = _make_deliverable(client)
        assert "deliverable_id" in data
        assert data["name"] == "Hierarchy Build"
        assert data["status"] == "DRAFT"

    def test_get_deliverable(self, client):
        created = _make_deliverable(client)
        r = client.get(f"{PREFIX}/{created['deliverable_id']}")
        assert r.status_code == 200
        d = r.json()
        assert d["name"] == "Hierarchy Build"
        assert d["category"] == "HIERARCHY"
        assert d["milestone"] == 1
        assert d["estimated_hours"] == 2.0
        assert d["client_slug"] == "ocp"

    def test_get_deliverable_not_found_404(self, client):
        r = client.get(f"{PREFIX}/nonexistent-id")
        assert r.status_code == 404

    def test_list_deliverables_empty(self, client):
        r = client.get(f"{PREFIX}/")
        assert r.status_code == 200
        assert r.json() == []

    def test_list_deliverables_filter_milestone(self, client):
        _make_deliverable(client, name="D1", milestone=1)
        _make_deliverable(client, name="D2", milestone=2)
        _make_deliverable(client, name="D3", milestone=1)

        r = client.get(f"{PREFIX}/", params={"milestone": 1})
        assert r.status_code == 200
        items = r.json()
        assert len(items) == 2
        assert all(d["milestone"] == 1 for d in items)

    def test_list_deliverables_filter_status(self, client):
        d1 = _make_deliverable(client, name="D1")
        # Transition D1 to IN_PROGRESS
        client.put(f"{PREFIX}/{d1['deliverable_id']}/transition", json={"status": "IN_PROGRESS"})
        _make_deliverable(client, name="D2")  # stays DRAFT

        r = client.get(f"{PREFIX}/", params={"status": "IN_PROGRESS"})
        assert r.status_code == 200
        items = r.json()
        assert len(items) == 1
        assert items[0]["status"] == "IN_PROGRESS"

    def test_update_deliverable(self, client):
        created = _make_deliverable(client)
        d_id = created["deliverable_id"]
        r = client.put(f"{PREFIX}/{d_id}", json={"consultant_notes": "Updated notes"})
        assert r.status_code == 200

        r2 = client.get(f"{PREFIX}/{d_id}")
        assert r2.json()["consultant_notes"] == "Updated notes"

    def test_update_nonexistent_returns_404(self, client):
        r = client.put(f"{PREFIX}/fake-id", json={"consultant_notes": "x"})
        assert r.status_code == 404


class TestStatusTransitions:

    def test_transition_draft_to_in_progress(self, client):
        created = _make_deliverable(client)
        d_id = created["deliverable_id"]
        r = client.put(f"{PREFIX}/{d_id}/transition", json={"status": "IN_PROGRESS"})
        assert r.status_code == 200
        assert r.json()["status"] == "IN_PROGRESS"

    def test_full_happy_path(self, client):
        """DRAFT -> IN_PROGRESS -> SUBMITTED -> UNDER_REVIEW -> APPROVED."""
        created = _make_deliverable(client)
        d_id = created["deliverable_id"]

        for target in ["IN_PROGRESS", "SUBMITTED", "UNDER_REVIEW", "APPROVED"]:
            r = client.put(f"{PREFIX}/{d_id}/transition", json={"status": target})
            assert r.status_code == 200
            assert r.json()["status"] == target

        # Verify detail has completed_at set
        r = client.get(f"{PREFIX}/{d_id}")
        assert r.json()["completed_at"] is not None

    def test_rejection_and_rework(self, client):
        """DRAFT -> IN_PROGRESS -> SUBMITTED -> UNDER_REVIEW -> REJECTED -> IN_PROGRESS."""
        created = _make_deliverable(client)
        d_id = created["deliverable_id"]

        for target in ["IN_PROGRESS", "SUBMITTED", "UNDER_REVIEW"]:
            client.put(f"{PREFIX}/{d_id}/transition", json={"status": target})

        r = client.put(
            f"{PREFIX}/{d_id}/transition",
            json={"status": "REJECTED", "feedback": "Needs more detail"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "REJECTED"

        # Check feedback stored
        detail = client.get(f"{PREFIX}/{d_id}").json()
        assert "Needs more detail" in detail.get("client_feedback", "")

        # Rework: back to IN_PROGRESS
        r = client.put(f"{PREFIX}/{d_id}/transition", json={"status": "IN_PROGRESS"})
        assert r.status_code == 200
        assert r.json()["status"] == "IN_PROGRESS"

    def test_invalid_transition_returns_409(self, client):
        created = _make_deliverable(client)
        d_id = created["deliverable_id"]
        r = client.put(f"{PREFIX}/{d_id}/transition", json={"status": "APPROVED"})
        assert r.status_code == 409

    def test_missing_status_field_returns_400(self, client):
        created = _make_deliverable(client)
        d_id = created["deliverable_id"]
        r = client.put(f"{PREFIX}/{d_id}/transition", json={"feedback": "oops"})
        assert r.status_code == 400


class TestTimeLogging:

    def test_log_time_updates_actual_hours(self, client):
        created = _make_deliverable(client, estimated_hours=8.0)
        d_id = created["deliverable_id"]

        r = client.post(f"{PREFIX}/{d_id}/time-log", json={
            "hours": 2.5,
            "activity_type": "analysis",
            "description": "Initial review",
        })
        assert r.status_code == 200
        log = r.json()
        assert log["hours"] == 2.5
        assert log["activity_type"] == "analysis"

        # Check actual_hours updated on deliverable
        detail = client.get(f"{PREFIX}/{d_id}").json()
        assert detail["actual_hours"] == 2.5

        # Log more time
        client.post(f"{PREFIX}/{d_id}/time-log", json={
            "hours": 1.5,
            "activity_type": "review",
            "description": "Peer review",
        })
        detail = client.get(f"{PREFIX}/{d_id}").json()
        assert detail["actual_hours"] == 4.0

    def test_list_time_logs(self, client):
        created = _make_deliverable(client)
        d_id = created["deliverable_id"]

        client.post(f"{PREFIX}/{d_id}/time-log", json={"hours": 1.0, "description": "Log 1"})
        client.post(f"{PREFIX}/{d_id}/time-log", json={"hours": 2.0, "description": "Log 2"})

        r = client.get(f"{PREFIX}/{d_id}/time-logs")
        assert r.status_code == 200
        logs = r.json()
        assert len(logs) == 2

    def test_log_time_nonexistent_deliverable_404(self, client):
        r = client.post(f"{PREFIX}/fake-id/time-log", json={"hours": 1.0})
        assert r.status_code == 404


class TestProjectSummary:

    def test_project_summary(self, client):
        _make_deliverable(client, name="D1", milestone=1, estimated_hours=2.0)
        _make_deliverable(client, name="D2", milestone=2, estimated_hours=8.0)

        r = client.get(f"{PREFIX}/summary/ocp/jfc")
        assert r.status_code == 200
        summary = r.json()
        assert summary["total_deliverables"] == 2
        assert summary["total_estimated_hours"] == 10.0
        assert summary["overall_completion_pct"] == 0.0  # none approved yet

    def test_summary_empty_project(self, client):
        r = client.get(f"{PREFIX}/summary/empty/project")
        assert r.status_code == 200
        summary = r.json()
        assert summary["total_deliverables"] == 0


class TestSeedFromPlan:

    def test_seed_from_plan(self, client):
        plan = {
            "stages": [
                {"id": "s1", "name": "hierarchy", "milestone": 1},
                {"id": "s2", "name": "criticality", "milestone": 1},
                {"id": "s3", "name": "fmeca", "milestone": 2},
            ]
        }
        r = client.post(f"{PREFIX}/seed-from-plan", json={
            "plan": plan,
            "client_slug": "ocp",
            "project_slug": "jfc",
        })
        assert r.status_code == 200
        result = r.json()
        assert result["created"] == 3
        assert len(result["deliverable_ids"]) == 3

        # Verify in DB
        r2 = client.get(f"{PREFIX}/", params={"client_slug": "ocp"})
        assert len(r2.json()) == 3

    def test_seed_missing_plan_returns_400(self, client):
        r = client.post(f"{PREFIX}/seed-from-plan", json={
            "client_slug": "ocp",
            "project_slug": "jfc",
        })
        assert r.status_code == 400
