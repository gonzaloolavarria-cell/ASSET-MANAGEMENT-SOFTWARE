"""Tests for sync API endpoints (GAP-W03)."""

import pytest
from datetime import datetime, timedelta

from tools.models.schemas import (
    SyncEntityType,
    SyncPullRequest,
    SyncPushRequest,
    SyncPushItem,
    SyncPushResponse,
    SyncPullResponse,
    SyncDeltaItem,
    SyncConflictResolution,
    ConflictRecord,
)


class TestSyncPull:
    """Tests for POST /api/v1/sync/pull."""

    def test_pull_returns_list(self, client):
        body = {
            "entity_types": ["captures"],
            "since": "2020-01-01T00:00:00",
            "limit": 10,
        }
        resp = client.post("/api/v1/sync/pull", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["entity_type"] == "captures"

    def test_pull_multiple_entity_types(self, client):
        body = {
            "entity_types": ["captures", "hierarchy_nodes"],
            "since": "2020-01-01T00:00:00",
            "limit": 10,
        }
        resp = client.post("/api/v1/sync/pull", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        types_returned = {d["entity_type"] for d in data}
        assert types_returned == {"captures", "hierarchy_nodes"}

    def test_pull_has_server_timestamp(self, client):
        body = {
            "entity_types": ["captures"],
            "since": "2020-01-01T00:00:00",
        }
        resp = client.post("/api/v1/sync/pull", json=body)
        data = resp.json()
        assert data[0]["server_timestamp"] is not None

    def test_pull_invalid_entity_type(self, client):
        body = {
            "entity_types": ["nonexistent"],
            "since": "2020-01-01T00:00:00",
        }
        resp = client.post("/api/v1/sync/pull", json=body)
        assert resp.status_code == 422  # Validation error

    def test_pull_limit_validation(self, client):
        body = {
            "entity_types": ["captures"],
            "since": "2020-01-01T00:00:00",
            "limit": 0,
        }
        resp = client.post("/api/v1/sync/pull", json=body)
        assert resp.status_code == 422  # limit must be >= 1

    def test_pull_limit_max_validation(self, client):
        body = {
            "entity_types": ["captures"],
            "since": "2020-01-01T00:00:00",
            "limit": 5000,
        }
        resp = client.post("/api/v1/sync/pull", json=body)
        assert resp.status_code == 422  # limit must be <= 1000

    def test_pull_empty_result(self, client):
        """Pull from far future should return empty items."""
        body = {
            "entity_types": ["captures"],
            "since": "2099-01-01T00:00:00",
            "limit": 10,
        }
        resp = client.post("/api/v1/sync/pull", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["items"] == []
        assert data[0]["has_more"] is False


class TestSyncPush:
    """Tests for POST /api/v1/sync/push."""

    def test_push_empty_batch(self, client):
        body = {
            "items": [],
            "device_id": "test-device-001",
        }
        resp = client.post("/api/v1/sync/push", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["accepted"] == 0
        assert data["conflicts"] == []
        assert data["server_ids"] == {}

    def test_push_create_capture(self, client):
        body = {
            "items": [
                {
                    "entity_type": "captures",
                    "local_id": "local-cap-001",
                    "action": "create",
                    "data": {
                        "technicianId": "TECH-001",
                        "captureType": "TEXT",
                        "language": "en",
                        "rawText": "Bearing noise on drive end",
                        "equipmentTag": "BRY-SAG-ML-001",
                        "locationHint": "Zone Broyage",
                    },
                    "offline_created_at": "2026-03-11T10:30:00",
                }
            ],
            "device_id": "test-device-001",
        }
        resp = client.post("/api/v1/sync/push", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["accepted"] == 1
        assert "local-cap-001" in data["server_ids"]
        assert len(data["server_ids"]["local-cap-001"]) > 0

    def test_push_multiple_captures(self, client):
        body = {
            "items": [
                {
                    "entity_type": "captures",
                    "local_id": f"local-cap-{i}",
                    "action": "create",
                    "data": {
                        "technicianId": "TECH-001",
                        "captureType": "TEXT",
                        "language": "en",
                        "rawText": f"Test capture {i}",
                        "equipmentTag": "BRY-SAG-ML-001",
                    },
                    "offline_created_at": "2026-03-11T10:30:00",
                }
                for i in range(3)
            ],
            "device_id": "test-device-002",
        }
        resp = client.post("/api/v1/sync/push", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["accepted"] == 3
        assert len(data["server_ids"]) == 3

    def test_push_readonly_entity_rejected(self, client):
        """Pushing to read-only entity types should not accept."""
        body = {
            "items": [
                {
                    "entity_type": "hierarchy_nodes",
                    "local_id": "local-node-001",
                    "action": "create",
                    "data": {"name": "Test Node"},
                    "offline_created_at": "2026-03-11T10:30:00",
                }
            ],
            "device_id": "test-device-003",
        }
        resp = client.post("/api/v1/sync/push", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["accepted"] == 0

    def test_push_invalid_entity_type(self, client):
        body = {
            "items": [
                {
                    "entity_type": "nonexistent",
                    "local_id": "local-001",
                    "action": "create",
                    "data": {},
                    "offline_created_at": "2026-03-11T10:30:00",
                }
            ],
            "device_id": "test-device-004",
        }
        resp = client.post("/api/v1/sync/push", json=body)
        assert resp.status_code == 422


class TestSyncResolve:
    """Tests for POST /api/v1/sync/resolve."""

    def test_resolve_not_found(self, client):
        body = {
            "conflict_id": "nonexistent-conflict-id",
            "strategy": "LOCAL_WINS",
        }
        resp = client.post("/api/v1/sync/resolve", json=body)
        assert resp.status_code == 404

    def test_resolve_invalid_strategy(self, client):
        body = {
            "conflict_id": "some-conflict-id",
            "strategy": "INVALID",
        }
        resp = client.post("/api/v1/sync/resolve", json=body)
        assert resp.status_code == 400

    def test_resolve_valid_strategies(self, client):
        """Both LOCAL_WINS and SERVER_WINS should be accepted (404 since conflict doesn't exist)."""
        for strategy in ("LOCAL_WINS", "SERVER_WINS"):
            body = {
                "conflict_id": "some-conflict-id",
                "strategy": strategy,
            }
            resp = client.post("/api/v1/sync/resolve", json=body)
            # 404 because conflict doesn't exist, but strategy is valid
            assert resp.status_code == 404


class TestSyncModels:
    """Tests for sync Pydantic models."""

    def test_sync_entity_type_values(self):
        assert SyncEntityType.CAPTURES == "captures"
        assert SyncEntityType.WORK_REQUESTS == "work_requests"
        assert SyncEntityType.WORK_ORDERS == "work_orders"
        assert SyncEntityType.CHECKLIST_PROGRESS == "checklist_progress"
        assert SyncEntityType.HIERARCHY_NODES == "hierarchy_nodes"

    def test_sync_pull_request_defaults(self):
        req = SyncPullRequest(
            entity_types=[SyncEntityType.CAPTURES],
            since=datetime.now(),
        )
        assert req.limit == 100

    def test_sync_pull_response_defaults(self):
        resp = SyncPullResponse(
            entity_type=SyncEntityType.CAPTURES,
            items=[],
            server_timestamp=datetime.now(),
        )
        assert resp.has_more is False

    def test_sync_push_response_defaults(self):
        resp = SyncPushResponse()
        assert resp.accepted == 0
        assert resp.conflicts == []
        assert resp.server_ids == {}

    def test_conflict_record_auto_id(self):
        record = ConflictRecord(
            entity_type=SyncEntityType.CAPTURES,
            entity_id="cap-001",
            field="raw_text",
            local_value="old text",
            server_value="new text",
            local_modified_at=datetime.now(),
            server_modified_at=datetime.now(),
        )
        assert record.conflict_id is not None
        assert len(record.conflict_id) > 0

    def test_sync_delta_item(self):
        item = SyncDeltaItem(
            id="cap-001",
            action="created",
            data={"raw_text": "test"},
            version=1,
            modified_at=datetime.now(),
        )
        assert item.action == "created"
        assert item.version == 1

    def test_sync_push_item(self):
        item = SyncPushItem(
            entity_type=SyncEntityType.CAPTURES,
            local_id="local-001",
            action="create",
            data={"rawText": "test"},
            offline_created_at=datetime.now(),
        )
        assert item.action == "create"

    def test_conflict_resolution(self):
        res = SyncConflictResolution(
            conflict_id="conflict-001",
            strategy="LOCAL_WINS",
        )
        assert res.strategy == "LOCAL_WINS"
