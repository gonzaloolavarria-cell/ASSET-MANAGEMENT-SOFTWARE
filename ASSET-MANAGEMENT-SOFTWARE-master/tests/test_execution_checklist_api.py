"""Tests for Execution Checklist API layer (GAP-W06, Session 2).

Covers:
- ORM model creation and JSON column storage
- Service functions: generate, get, list, complete_step, skip_step, close
- Router endpoints via TestClient
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime


# ════════════════════════════════════════════════════════════════════════
# SECTION 1: ORM MODEL TESTS
# ════════════════════════════════════════════════════════════════════════

class TestExecutionChecklistModel:

    def test_import_model(self):
        from api.database.models import ExecutionChecklistModel
        assert ExecutionChecklistModel.__tablename__ == "execution_checklists"

    def test_model_has_required_columns(self):
        from api.database.models import ExecutionChecklistModel
        mapper = ExecutionChecklistModel.__table__.columns
        expected = [
            "checklist_id", "work_package_id", "work_package_name",
            "work_package_code", "equipment_tag", "equipment_name",
            "steps", "safety_section", "pre_task_notes", "post_task_notes",
            "status", "assigned_to", "supervisor", "supervisor_signature",
            "closure_summary", "created_at", "started_at", "completed_at", "closed_at",
        ]
        col_names = [c.name for c in mapper]
        for col in expected:
            assert col in col_names, f"Missing column: {col}"

    def test_model_default_status(self):
        from api.database.models import ExecutionChecklistModel
        col = ExecutionChecklistModel.__table__.columns["status"]
        assert col.default.arg == "DRAFT"

    def test_model_json_columns(self):
        from api.database.models import ExecutionChecklistModel
        from sqlalchemy import JSON
        table = ExecutionChecklistModel.__table__
        json_cols = [c.name for c in table.columns if isinstance(c.type, JSON)]
        assert "steps" in json_cols
        assert "safety_section" in json_cols
        assert "closure_summary" in json_cols

    def test_model_indexes(self):
        from api.database.models import ExecutionChecklistModel
        index_names = [idx.name for idx in ExecutionChecklistModel.__table__.indexes]
        assert "ix_exec_checklists_wp" in index_names
        assert "ix_exec_checklists_status" in index_names
        assert "ix_exec_checklists_assigned" in index_names


# ════════════════════════════════════════════════════════════════════════
# SECTION 2: SERVICE TESTS (with mocked DB)
# ════════════════════════════════════════════════════════════════════════

def _mock_db():
    """Create a mock database session."""
    db = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    db.add = MagicMock()
    return db


def _sample_work_package():
    return {
        "work_package_id": "WP-001",
        "name": "PUMP OVERHAUL",
        "code": "WP-PUMP-001",
        "constraint": "ONLINE",
        "allocated_tasks": [],
    }


class TestExecutionChecklistService:

    def test_import_service(self):
        from api.services import execution_checklist_service
        assert hasattr(execution_checklist_service, "generate_checklist")
        assert hasattr(execution_checklist_service, "get_checklist")
        assert hasattr(execution_checklist_service, "list_checklists")
        assert hasattr(execution_checklist_service, "complete_step")
        assert hasattr(execution_checklist_service, "skip_step")
        assert hasattr(execution_checklist_service, "get_next_steps")
        assert hasattr(execution_checklist_service, "close_checklist")

    def test_generate_checklist_calls_engine(self):
        from api.services import execution_checklist_service
        db = _mock_db()

        # Mock refresh to populate fields from the added object
        def refresh_side_effect(obj):
            if not hasattr(obj, '_refreshed'):
                obj._refreshed = True

        db.refresh.side_effect = refresh_side_effect

        with patch.object(db, 'query') as mock_query:
            result = execution_checklist_service.generate_checklist(
                db,
                work_package=_sample_work_package(),
                tasks=[],
                equipment_name="SAG Mill",
                equipment_tag="TAG-001",
            )
        assert result["work_package_id"] == "WP-001"
        assert result["equipment_tag"] == "TAG-001"
        assert result["status"] == "DRAFT"
        # db.add called twice: once for the model, once for the audit log
        assert db.add.call_count == 2
        db.commit.assert_called_once()

    def test_checklist_to_dict_keys(self):
        from api.services.execution_checklist_service import _checklist_to_dict
        from api.database.models import ExecutionChecklistModel
        obj = ExecutionChecklistModel(
            checklist_id="CL-1",
            work_package_id="WP-1",
            work_package_name="TEST WP",
            work_package_code="WP-CODE",
            equipment_tag="TAG-1",
            equipment_name="Pump",
            status="DRAFT",
        )
        d = _checklist_to_dict(obj)
        assert d["checklist_id"] == "CL-1"
        assert d["work_package_id"] == "WP-1"
        assert "steps" in d
        assert "status" in d

    def test_get_checklist_not_found(self):
        from api.services import execution_checklist_service
        db = _mock_db()
        db.query.return_value.filter.return_value.first.return_value = None
        result = execution_checklist_service.get_checklist(db, "nonexistent")
        assert result is None

    def test_list_checklists_with_filters(self):
        from api.services import execution_checklist_service
        db = _mock_db()
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []

        result = execution_checklist_service.list_checklists(
            db, work_package_id="WP-1", status="DRAFT"
        )
        assert result == []


# ════════════════════════════════════════════════════════════════════════
# SECTION 3: ROUTER TESTS
# ════════════════════════════════════════════════════════════════════════

class TestExecutionChecklistRouter:

    def test_import_router(self):
        from api.routers.execution_checklists import router
        assert router.prefix == "/execution-checklists"
        assert "execution-checklists" in router.tags

    def test_router_has_all_endpoints(self):
        from api.routers.execution_checklists import router
        routes = [r.path for r in router.routes]
        prefix = "/execution-checklists"
        assert f"{prefix}/" in routes
        assert f"{prefix}/{{checklist_id}}" in routes
        assert f"{prefix}/{{checklist_id}}/steps/{{step_id}}/complete" in routes
        assert f"{prefix}/{{checklist_id}}/steps/{{step_id}}/skip" in routes
        assert f"{prefix}/{{checklist_id}}/next-steps" in routes
        assert f"{prefix}/{{checklist_id}}/close" in routes

    def test_router_endpoint_methods(self):
        from api.routers.execution_checklists import router
        method_map = {}
        for route in router.routes:
            methods = getattr(route, "methods", set())
            # Collect all methods per path (POST and GET on same "/" path)
            path = route.path
            if path not in method_map:
                method_map[path] = set()
            method_map[path].update(methods)

        prefix = "/execution-checklists"
        assert "POST" in method_map.get(f"{prefix}/", set())
        assert "GET" in method_map.get(f"{prefix}/", set())
        assert "GET" in method_map.get(f"{prefix}/{{checklist_id}}", set())
        assert "POST" in method_map.get(f"{prefix}/{{checklist_id}}/steps/{{step_id}}/complete", set())
        assert "POST" in method_map.get(f"{prefix}/{{checklist_id}}/steps/{{step_id}}/skip", set())
        assert "GET" in method_map.get(f"{prefix}/{{checklist_id}}/next-steps", set())
        assert "POST" in method_map.get(f"{prefix}/{{checklist_id}}/close", set())


# ════════════════════════════════════════════════════════════════════════
# SECTION 4: ROUTER REGISTRATION
# ════════════════════════════════════════════════════════════════════════

class TestRouterRegistration:

    def test_execution_checklists_in_main_app(self):
        """Verify execution checklists router is registered in the FastAPI app."""
        from api.main import app
        routes = [r.path for r in app.routes]
        # Check that execution-checklists prefix exists
        ec_routes = [r for r in routes if "execution-checklists" in r]
        assert len(ec_routes) > 0, "execution-checklists routes not found in app"

    def test_root_endpoint_includes_module(self):
        """Verify execution-checklists is listed in the root endpoint modules."""
        from api.main import app
        # Find the root endpoint handler
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "execution-checklists" in data["modules"]


# ════════════════════════════════════════════════════════════════════════
# SECTION 5: INTEGRATION SMOKE TESTS (TestClient)
# ════════════════════════════════════════════════════════════════════════

class TestExecutionChecklistIntegration:

    @pytest.fixture(autouse=True)
    def _setup_client(self):
        from api.main import app
        from fastapi.testclient import TestClient
        self.client = TestClient(app)

    def test_generate_checklist_endpoint(self):
        wp = _sample_work_package()
        resp = self.client.post("/api/v1/execution-checklists/", json={
            "work_package": wp,
            "tasks": [],
            "equipment_name": "SAG Mill",
            "equipment_tag": "TAG-001",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["work_package_id"] == "WP-001"
        assert data["status"] == "DRAFT"
        assert "checklist_id" in data

    def test_list_checklists_endpoint(self):
        resp = self.client.get("/api/v1/execution-checklists/")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_checklist_not_found(self):
        resp = self.client.get("/api/v1/execution-checklists/nonexistent-id")
        assert resp.status_code == 404

    def test_generate_and_get_checklist(self):
        wp = _sample_work_package()
        create_resp = self.client.post("/api/v1/execution-checklists/", json={
            "work_package": wp,
            "tasks": [],
            "equipment_name": "Crusher",
            "equipment_tag": "CR-001",
        })
        assert create_resp.status_code == 200
        cl_id = create_resp.json()["checklist_id"]

        get_resp = self.client.get(f"/api/v1/execution-checklists/{cl_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["checklist_id"] == cl_id

    def test_get_next_steps_endpoint(self):
        wp = _sample_work_package()
        create_resp = self.client.post("/api/v1/execution-checklists/", json={
            "work_package": wp,
            "tasks": [],
            "equipment_name": "Conveyor",
            "equipment_tag": "CV-001",
        })
        cl_id = create_resp.json()["checklist_id"]

        resp = self.client.get(f"/api/v1/execution-checklists/{cl_id}/next-steps")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_complete_step_gate_blocked(self):
        """Completing a step with unsatisfied predecessors returns 409."""
        # Generate offline WP to get steps with predecessors
        wp = {
            "work_package_id": "WP-GATE",
            "name": "GATE TEST",
            "code": "WP-GT",
            "constraint": "OFFLINE",
            "allocated_tasks": [{"task_id": "T1", "operation_number": 10}],
        }
        tasks = [{
            "task_id": "T1",
            "name": "Replace bearing",
            "task_type": "REPLACE",
            "constraint": "OFFLINE",
        }]
        create_resp = self.client.post("/api/v1/execution-checklists/", json={
            "work_package": wp,
            "tasks": tasks,
            "equipment_name": "Motor",
            "equipment_tag": "MT-001",
        })
        data = create_resp.json()
        steps = data["steps"]

        # Find a step that has predecessors (should be blocked)
        blocked_steps = [s for s in steps if s.get("predecessor_step_ids")]
        if blocked_steps:
            step = blocked_steps[0]
            resp = self.client.post(
                f"/api/v1/execution-checklists/{data['checklist_id']}/steps/{step['step_id']}/complete",
                json={"completed_by": "tester"},
            )
            assert resp.status_code == 409

    def test_skip_gate_step_returns_409(self):
        """Skipping a gate step returns 409."""
        wp = {
            "work_package_id": "WP-SKIP",
            "name": "SKIP TEST",
            "code": "WP-SK",
            "constraint": "ONLINE",
            "allocated_tasks": [],
        }
        create_resp = self.client.post("/api/v1/execution-checklists/", json={
            "work_package": wp,
            "tasks": [],
            "equipment_name": "Pump",
            "equipment_tag": "PMP-001",
        })
        data = create_resp.json()
        gate_steps = [s for s in data["steps"] if s.get("is_gate")]
        if gate_steps:
            gate = gate_steps[0]
            resp = self.client.post(
                f"/api/v1/execution-checklists/{data['checklist_id']}/steps/{gate['step_id']}/skip",
                json={"reason": "test", "authorized_by": "supervisor"},
            )
            assert resp.status_code == 409

    def test_close_uncompleted_checklist_returns_409(self):
        """Closing a DRAFT checklist returns 409."""
        wp = _sample_work_package()
        create_resp = self.client.post("/api/v1/execution-checklists/", json={
            "work_package": wp,
            "tasks": [],
            "equipment_name": "Valve",
            "equipment_tag": "VLV-001",
        })
        cl_id = create_resp.json()["checklist_id"]
        resp = self.client.post(
            f"/api/v1/execution-checklists/{cl_id}/close",
            json={"supervisor": "John", "supervisor_notes": "test"},
        )
        assert resp.status_code == 409

    def test_list_with_filters(self):
        resp = self.client.get(
            "/api/v1/execution-checklists/",
            params={"status": "DRAFT"},
        )
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════════
# SECTION 6: SKILL REGISTRATION
# ════════════════════════════════════════════════════════════════════════

class TestSkillRegistration:

    def test_skill_file_exists(self):
        from pathlib import Path
        skill_path = Path("skills/02-work-planning/generate-execution-checklists/CLAUDE.md")
        assert skill_path.exists(), f"Skill file missing: {skill_path}"

    def test_skill_registered_in_planning_yaml(self):
        import yaml
        from pathlib import Path
        with open(Path("agents/planning/skills.yaml"), "r") as f:
            config = yaml.safe_load(f)
        skill_names = [s["name"] for s in config["skills"]]
        assert "generate-execution-checklists" in skill_names

    def test_skill_has_frontmatter(self):
        from pathlib import Path
        content = Path("skills/02-work-planning/generate-execution-checklists/CLAUDE.md").read_text()
        assert content.startswith("---")
        assert "name: generate-execution-checklists" in content
