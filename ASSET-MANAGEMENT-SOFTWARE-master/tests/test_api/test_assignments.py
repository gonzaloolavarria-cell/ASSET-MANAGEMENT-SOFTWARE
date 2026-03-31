"""API tests for assignments router (GAP-W09)."""

from __future__ import annotations

import json

import pytest

from api.database.models import WorkforceModel


@pytest.fixture
def seeded_assignment_client(client, db_session):
    """Client with workforce including competency data."""
    workers = [
        WorkforceModel(
            worker_id="W-A01",
            name="García Senior",
            specialty="FITTER",
            shift="MORNING",
            plant_id="TEST-PLANT",
            available=True,
            certifications=["SAFETY_ADV", "CONFINED_SPACE"],
            competency_level="A",
            years_experience=15,
            equipment_expertise=["SAG_MILL", "CONVEYOR"],
            safety_training_current=True,
            competencies=[
                {"specialty": "FITTER", "equipment_type": "SAG_MILL", "level": "A", "certified": True},
                {"specialty": "FITTER", "equipment_type": "CONVEYOR", "level": "B"},
            ],
        ),
        WorkforceModel(
            worker_id="W-B01",
            name="López Standard",
            specialty="FITTER",
            shift="MORNING",
            plant_id="TEST-PLANT",
            available=True,
            certifications=["SAFETY_BASIC"],
            competency_level="B",
            years_experience=7,
            equipment_expertise=["CONVEYOR"],
            safety_training_current=True,
            competencies=[
                {"specialty": "FITTER", "equipment_type": "CONVEYOR", "level": "B"},
            ],
        ),
        WorkforceModel(
            worker_id="W-C01",
            name="Sánchez Electrician",
            specialty="ELECTRICIAN",
            shift="MORNING",
            plant_id="TEST-PLANT",
            available=True,
            certifications=["SAFETY_ADV", "HV_CERT"],
            competency_level="A",
            years_experience=20,
            equipment_expertise=["MOTOR", "TRANSFORMER"],
            safety_training_current=True,
            competencies=[
                {"specialty": "ELECTRICIAN", "equipment_type": "MOTOR", "level": "A", "certified": True},
            ],
        ),
        WorkforceModel(
            worker_id="W-OFF",
            name="Martínez Absent",
            specialty="FITTER",
            shift="MORNING",
            plant_id="TEST-PLANT",
            available=False,
            certifications=[],
            competency_level="C",
            years_experience=1,
        ),
    ]
    for w in workers:
        db_session.add(w)
    db_session.commit()

    return client


SAMPLE_TASKS = [
    {
        "task_id": "T-001",
        "work_package_id": "WP-001",
        "name": "PM SAG Mill Bearings",
        "competency_requirements": [
            {
                "specialty": "FITTER",
                "min_level": "A",
                "equipment_type": "SAG_MILL",
                "requires_certification": True,
            }
        ],
        "estimated_hours": 4.0,
        "priority": 5,
    },
    {
        "task_id": "T-002",
        "work_package_id": "WP-001",
        "name": "Inspect Conveyor Belt",
        "competency_requirements": [
            {
                "specialty": "FITTER",
                "min_level": "B",
                "equipment_type": "CONVEYOR",
            }
        ],
        "estimated_hours": 2.0,
        "priority": 3,
    },
]


class TestListTechnicians:
    def test_list_all(self, seeded_assignment_client):
        resp = seeded_assignment_client.get("/api/v1/assignments/technicians")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 4

    def test_filter_by_plant(self, seeded_assignment_client):
        resp = seeded_assignment_client.get(
            "/api/v1/assignments/technicians?plant_id=TEST-PLANT"
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 4

    def test_filter_by_shift(self, seeded_assignment_client):
        resp = seeded_assignment_client.get(
            "/api/v1/assignments/technicians?shift=MORNING"
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 4

    def test_filter_by_specialty(self, seeded_assignment_client):
        resp = seeded_assignment_client.get(
            "/api/v1/assignments/technicians?specialty=ELECTRICIAN"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Sánchez Electrician"

    def test_filter_no_match(self, seeded_assignment_client):
        resp = seeded_assignment_client.get(
            "/api/v1/assignments/technicians?plant_id=NONEXISTENT"
        )
        assert resp.status_code == 200
        assert resp.json() == []


class TestOptimizeAssignments:
    def test_optimize_success(self, seeded_assignment_client):
        resp = seeded_assignment_client.post(
            "/api/v1/assignments/optimize",
            json={
                "tasks": SAMPLE_TASKS,
                "plant_id": "TEST-PLANT",
                "date": "2026-03-15",
                "shift": "MORNING",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["assigned_tasks"] == 2
        assert data["total_technicians"] == 4
        assert len(data["assignments"]) == 2

    def test_optimize_empty_tasks(self, seeded_assignment_client):
        resp = seeded_assignment_client.post(
            "/api/v1/assignments/optimize",
            json={
                "tasks": [],
                "plant_id": "TEST-PLANT",
                "date": "2026-03-15",
                "shift": "MORNING",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["assigned_tasks"] == 0

    def test_optimize_missing_field(self, seeded_assignment_client):
        resp = seeded_assignment_client.post(
            "/api/v1/assignments/optimize",
            json={"tasks": SAMPLE_TASKS},  # Missing plant_id, date, shift
        )
        assert resp.status_code == 422

    def test_optimize_has_match_scores(self, seeded_assignment_client):
        resp = seeded_assignment_client.post(
            "/api/v1/assignments/optimize",
            json={
                "tasks": SAMPLE_TASKS,
                "plant_id": "TEST-PLANT",
                "date": "2026-03-15",
                "shift": "MORNING",
            },
        )
        data = resp.json()
        for a in data["assignments"]:
            assert 0 <= a["match_score"] <= 100
            assert isinstance(a["match_reasons"], list)


class TestReoptimize:
    def test_reoptimize_with_absence(self, seeded_assignment_client):
        # First optimize
        resp1 = seeded_assignment_client.post(
            "/api/v1/assignments/optimize",
            json={
                "tasks": SAMPLE_TASKS,
                "plant_id": "TEST-PLANT",
                "date": "2026-03-15",
                "shift": "MORNING",
            },
        )
        original = resp1.json()

        # Re-optimize with one absent
        resp2 = seeded_assignment_client.post(
            "/api/v1/assignments/reoptimize",
            json={
                "existing_assignments": original["assignments"],
                "absent_worker_ids": ["W-A01"],
                "tasks": SAMPLE_TASKS,
                "plant_id": "TEST-PLANT",
                "date": "2026-03-15",
                "shift": "MORNING",
            },
        )
        assert resp2.status_code == 200
        data = resp2.json()
        assigned_ids = {a["worker_id"] for a in data["assignments"]}
        assert "W-A01" not in assigned_ids


class TestSummary:
    def test_summary_endpoint(self, seeded_assignment_client):
        # First optimize
        resp1 = seeded_assignment_client.post(
            "/api/v1/assignments/optimize",
            json={
                "tasks": SAMPLE_TASKS,
                "plant_id": "TEST-PLANT",
                "date": "2026-03-15",
                "shift": "MORNING",
            },
        )
        summary_data = resp1.json()

        resp2 = seeded_assignment_client.post(
            "/api/v1/assignments/summary",
            json=summary_data,
        )
        assert resp2.status_code == 200
        data = resp2.json()
        assert "technician_assignments" in data
        assert "crew" in data
