"""Tests for Troubleshooting API — GAP-W02."""


class TestTroubleshootingAPI:

    def test_create_session(self, client):
        response = client.post("/api/v1/troubleshooting/sessions", json={
            "equipment_type_id": "ET-SAG-MILL",
            "equipment_tag": "BRY-SAG-ML-001",
            "plant_id": "TEST-PLANT",
            "technician_id": "TECH-001",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"].startswith("DIAG-")
        assert data["equipment_type_id"] == "ET-SAG-MILL"
        assert data["status"] == "IN_PROGRESS"

    def test_get_session(self, client):
        create_resp = client.post("/api/v1/troubleshooting/sessions", json={
            "equipment_type_id": "ET-SAG-MILL",
        })
        session_id = create_resp.json()["session_id"]
        get_resp = client.get(f"/api/v1/troubleshooting/sessions/{session_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["session_id"] == session_id

    def test_get_session_not_found(self, client):
        resp = client.get("/api/v1/troubleshooting/sessions/DIAG-NONEXIST")
        assert resp.status_code == 404

    def test_add_symptom(self, client):
        create_resp = client.post("/api/v1/troubleshooting/sessions", json={
            "equipment_type_id": "ET-SAG-MILL",
        })
        session_id = create_resp.json()["session_id"]
        symptom_resp = client.post(
            f"/api/v1/troubleshooting/sessions/{session_id}/symptoms",
            json={
                "description": "Excessive vibration from drive end",
                "category": "vibration",
                "severity": "HIGH",
            },
        )
        assert symptom_resp.status_code == 200
        data = symptom_resp.json()
        assert len(data["symptoms"]) == 1
        assert data["symptoms"][0]["category"] == "vibration"

    def test_add_symptom_not_found(self, client):
        resp = client.post(
            "/api/v1/troubleshooting/sessions/DIAG-NONEXIST/symptoms",
            json={"description": "vibration"},
        )
        assert resp.status_code == 404

    def test_record_test_result(self, client):
        create_resp = client.post("/api/v1/troubleshooting/sessions", json={
            "equipment_type_id": "ET-SAG-MILL",
        })
        session_id = create_resp.json()["session_id"]
        # Add symptom first
        client.post(
            f"/api/v1/troubleshooting/sessions/{session_id}/symptoms",
            json={"description": "Excessive vibration", "category": "vibration"},
        )
        # Record test
        test_resp = client.post(
            f"/api/v1/troubleshooting/sessions/{session_id}/tests",
            json={
                "test_id": "TST-001",
                "result": "ABNORMAL",
                "measured_value": "12.5 mm/s RMS",
            },
        )
        assert test_resp.status_code == 200
        data = test_resp.json()
        assert len(data["tests_performed"]) == 1

    def test_finalize_diagnosis(self, client):
        create_resp = client.post("/api/v1/troubleshooting/sessions", json={
            "equipment_type_id": "ET-SAG-MILL",
        })
        session_id = create_resp.json()["session_id"]
        client.post(
            f"/api/v1/troubleshooting/sessions/{session_id}/symptoms",
            json={"description": "Excessive vibration", "category": "vibration"},
        )
        fin_resp = client.put(
            f"/api/v1/troubleshooting/sessions/{session_id}/finalize",
            json={"selected_fm_code": "FM-71"},
        )
        assert fin_resp.status_code == 200
        data = fin_resp.json()
        assert data["status"] == "COMPLETED"

    def test_record_feedback(self, client):
        create_resp = client.post("/api/v1/troubleshooting/sessions", json={
            "equipment_type_id": "ET-SAG-MILL",
        })
        session_id = create_resp.json()["session_id"]
        client.post(
            f"/api/v1/troubleshooting/sessions/{session_id}/symptoms",
            json={"description": "Vibration", "category": "vibration"},
        )
        client.put(
            f"/api/v1/troubleshooting/sessions/{session_id}/finalize",
            json={"selected_fm_code": "FM-71"},
        )
        fb_resp = client.put(
            f"/api/v1/troubleshooting/sessions/{session_id}/feedback",
            json={
                "actual_cause": "Bearing inner race spalling due to metal-to-metal contact",
                "notes": "Confirmed via vibration spectrum analysis",
            },
        )
        assert fb_resp.status_code == 200
        data = fb_resp.json()
        assert data["actual_cause_feedback"] is not None

    def test_get_equipment_symptoms(self, client):
        resp = client.get("/api/v1/troubleshooting/equipment/ET-SAG-MILL/symptoms")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_get_equipment_tree(self, client):
        resp = client.get("/api/v1/troubleshooting/equipment/ET-SAG-MILL/tree")
        assert resp.status_code == 200
        data = resp.json()
        assert "entry_nodes" in data or "entry_node_id" in data or "_meta" in data

    def test_get_equipment_tree_not_found(self, client):
        resp = client.get("/api/v1/troubleshooting/equipment/ET-NONEXISTENT/tree")
        assert resp.status_code == 404

    def test_get_equipment_tree_with_category(self, client):
        resp = client.get(
            "/api/v1/troubleshooting/equipment/ET-SAG-MILL/tree",
            params={"category": "vibration"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] == "vibration"

    def test_full_lifecycle(self, client):
        """End-to-end: create → symptom → test → finalize → feedback."""
        # Create
        r = client.post("/api/v1/troubleshooting/sessions", json={
            "equipment_type_id": "ET-SAG-MILL",
            "equipment_tag": "BRY-SAG-ML-001",
            "technician_id": "TECH-001",
        })
        sid = r.json()["session_id"]

        # Add symptoms
        client.post(f"/api/v1/troubleshooting/sessions/{sid}/symptoms", json={
            "description": "Excessive vibration from drive end bearing",
            "category": "vibration", "severity": "HIGH",
        })
        r2 = client.post(f"/api/v1/troubleshooting/sessions/{sid}/symptoms", json={
            "description": "Grinding noise at low speed",
            "category": "noise", "severity": "MEDIUM",
        })
        assert len(r2.json()["symptoms"]) == 2

        # Record test
        client.post(f"/api/v1/troubleshooting/sessions/{sid}/tests", json={
            "test_id": "TST-VIB-001", "result": "ABNORMAL",
            "measured_value": "12.5 mm/s RMS",
        })

        # Finalize
        fin = client.put(f"/api/v1/troubleshooting/sessions/{sid}/finalize", json={
            "selected_fm_code": "FM-71",
        })
        assert fin.json()["status"] == "COMPLETED"

        # Feedback
        fb = client.put(f"/api/v1/troubleshooting/sessions/{sid}/feedback", json={
            "actual_cause": "Metal to metal contact — bearing inner race spalling",
        })
        assert fb.json()["actual_cause_feedback"] is not None

        # Verify final state
        final = client.get(f"/api/v1/troubleshooting/sessions/{sid}")
        assert final.json()["status"] == "COMPLETED"
        assert final.json()["final_fm_code"] == "FM-71"
