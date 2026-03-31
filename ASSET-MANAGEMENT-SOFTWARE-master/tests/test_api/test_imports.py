"""API tests for imports router (G-18 / Phase B)."""

from __future__ import annotations

import csv
import io

import openpyxl
import pytest

from api.database.models import ImportHistoryModel


# ── Helpers ────────────────────────────────────────────────────────────

def _make_xlsx(rows: list[dict]) -> bytes:
    """Create a minimal .xlsx file in memory from a list of dicts."""
    wb = openpyxl.Workbook()
    ws = wb.active
    if not rows:
        return _wb_bytes(wb)
    headers = list(rows[0].keys())
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h) for h in headers])
    return _wb_bytes(wb)


def _wb_bytes(wb) -> bytes:
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _make_csv(rows: list[dict]) -> bytes:
    if not rows:
        return b""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


VALID_HIERARCHY_ROWS = [
    {"equipment_id": "EQ-001", "description": "SAG Mill", "equipment_type": "ROTATING"},
    {"equipment_id": "EQ-002", "description": "Slurry Pump", "equipment_type": "ROTATING"},
]

INVALID_HIERARCHY_ROWS = [
    {"description": "Missing ID"},  # missing equipment_id
    {"equipment_id": "EQ-003", "equipment_type": "ROTATING"},  # missing description
]


# ── Test: GET /import/sources ────────────────────────────────────────

class TestListSources:
    def test_returns_list(self, client):
        resp = client.get("/api/v1/import/sources")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_contains_expected_sources(self, client):
        resp = client.get("/api/v1/import/sources")
        data = resp.json()
        assert "EQUIPMENT_HIERARCHY" in data
        assert "FAILURE_HISTORY" in data
        assert "MAINTENANCE_PLAN" in data


# ── Test: GET /import/history ────────────────────────────────────────

class TestImportHistory:
    def test_empty_history(self, client):
        resp = client.get("/api/v1/import/history")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_history_after_import(self, client, db_session):
        """After importing a file, GET /history should return 1 entry."""
        xlsx_bytes = _make_xlsx(VALID_HIERARCHY_ROWS)
        client.post(
            "/api/v1/import/file",
            files={"file": ("hierarchy.xlsx", xlsx_bytes, "application/octet-stream")},
            data={"source": "EQUIPMENT_HIERARCHY", "plant_id": "OCP-TEST"},
        )
        resp = client.get("/api/v1/import/history?plant_id=OCP-TEST")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["source"] == "EQUIPMENT_HIERARCHY"
        assert data[0]["filename"] == "hierarchy.xlsx"

    def test_history_filter_by_source(self, client, db_session):
        xlsx = _make_xlsx(VALID_HIERARCHY_ROWS)
        client.post(
            "/api/v1/import/file",
            files={"file": ("h.xlsx", xlsx, "application/octet-stream")},
            data={"source": "EQUIPMENT_HIERARCHY", "plant_id": "OCP-TEST"},
        )
        resp = client.get("/api/v1/import/history?source=FAILURE_HISTORY")
        assert resp.json() == []

    def test_history_limit(self, client, db_session):
        xlsx = _make_xlsx(VALID_HIERARCHY_ROWS)
        for i in range(5):
            client.post(
                "/api/v1/import/file",
                files={"file": (f"h{i}.xlsx", xlsx, "application/octet-stream")},
                data={"source": "EQUIPMENT_HIERARCHY", "plant_id": "OCP-TEST"},
            )
        resp = client.get("/api/v1/import/history?limit=2")
        assert len(resp.json()) == 2

    def test_history_invalid_limit(self, client):
        resp = client.get("/api/v1/import/history?limit=0")
        assert resp.status_code == 422


# ── Test: POST /import/file ──────────────────────────────────────────

class TestImportFile:
    def test_import_xlsx_success(self, client, db_session):
        xlsx_bytes = _make_xlsx(VALID_HIERARCHY_ROWS)
        resp = client.post(
            "/api/v1/import/file",
            files={"file": ("hierarchy.xlsx", xlsx_bytes, "application/octet-stream")},
            data={"source": "EQUIPMENT_HIERARCHY", "plant_id": "OCP-TEST"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["total_rows"] == 2
        assert data["valid_rows"] == 2
        assert data["error_rows"] == 0
        assert "import_id" in data

    def test_import_csv_success(self, client, db_session):
        csv_bytes = _make_csv(VALID_HIERARCHY_ROWS)
        resp = client.post(
            "/api/v1/import/file",
            files={"file": ("hierarchy.csv", csv_bytes, "text/csv")},
            data={"source": "EQUIPMENT_HIERARCHY", "plant_id": "OCP-TEST"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["valid_rows"] == 2

    def test_import_partial_invalid_rows(self, client, db_session):
        """Mix of valid + invalid rows → status=partial."""
        rows = VALID_HIERARCHY_ROWS + INVALID_HIERARCHY_ROWS
        xlsx_bytes = _make_xlsx(rows)
        resp = client.post(
            "/api/v1/import/file",
            files={"file": ("mixed.xlsx", xlsx_bytes, "application/octet-stream")},
            data={"source": "EQUIPMENT_HIERARCHY", "plant_id": "OCP-TEST"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "partial"
        assert data["valid_rows"] > 0
        assert data["error_rows"] > 0

    def test_import_invalid_source(self, client, db_session):
        xlsx_bytes = _make_xlsx(VALID_HIERARCHY_ROWS)
        resp = client.post(
            "/api/v1/import/file",
            files={"file": ("h.xlsx", xlsx_bytes, "application/octet-stream")},
            data={"source": "NOT_A_REAL_SOURCE", "plant_id": "OCP-TEST"},
        )
        assert resp.status_code == 422

    def test_import_unsupported_extension(self, client, db_session):
        resp = client.post(
            "/api/v1/import/file",
            files={"file": ("data.pdf", b"%PDF-1.4", "application/pdf")},
            data={"source": "EQUIPMENT_HIERARCHY", "plant_id": "OCP-TEST"},
        )
        assert resp.status_code == 422

    def test_import_empty_file(self, client, db_session):
        resp = client.post(
            "/api/v1/import/file",
            files={"file": ("empty.csv", b"", "text/csv")},
            data={"source": "EQUIPMENT_HIERARCHY", "plant_id": "OCP-TEST"},
        )
        assert resp.status_code == 422

    def test_import_persists_to_db(self, client, db_session):
        xlsx_bytes = _make_xlsx(VALID_HIERARCHY_ROWS)
        resp = client.post(
            "/api/v1/import/file",
            files={"file": ("h.xlsx", xlsx_bytes, "application/octet-stream")},
            data={"source": "EQUIPMENT_HIERARCHY", "plant_id": "OCP-TEST"},
        )
        import_id = resp.json()["import_id"]
        row = db_session.query(ImportHistoryModel).filter_by(import_id=import_id).first()
        assert row is not None
        assert row.plant_id == "OCP-TEST"
        assert row.source == "EQUIPMENT_HIERARCHY"
        assert row.status == "success"

    def test_import_with_imported_by(self, client, db_session):
        xlsx_bytes = _make_xlsx(VALID_HIERARCHY_ROWS)
        resp = client.post(
            "/api/v1/import/file",
            files={"file": ("h.xlsx", xlsx_bytes, "application/octet-stream")},
            data={
                "source": "EQUIPMENT_HIERARCHY",
                "plant_id": "OCP-TEST",
                "imported_by": "test_user",
            },
        )
        import_id = resp.json()["import_id"]
        row = db_session.query(ImportHistoryModel).filter_by(import_id=import_id).first()
        assert row.imported_by == "test_user"

    def test_import_returns_errors_for_invalid_rows(self, client, db_session):
        xlsx_bytes = _make_xlsx(INVALID_HIERARCHY_ROWS)
        resp = client.post(
            "/api/v1/import/file",
            files={"file": ("bad.xlsx", xlsx_bytes, "application/octet-stream")},
            data={"source": "EQUIPMENT_HIERARCHY", "plant_id": "OCP-TEST"},
        )
        data = resp.json()
        assert data["error_rows"] > 0
        assert isinstance(data["errors"], list)
        assert len(data["errors"]) > 0
        assert "message" in data["errors"][0]

    def test_import_file_size_recorded(self, client, db_session):
        xlsx_bytes = _make_xlsx(VALID_HIERARCHY_ROWS)
        resp = client.post(
            "/api/v1/import/file",
            files={"file": ("h.xlsx", xlsx_bytes, "application/octet-stream")},
            data={"source": "EQUIPMENT_HIERARCHY", "plant_id": "OCP-TEST"},
        )
        assert resp.status_code == 200
        assert resp.json()["file_size_kb"] is not None
