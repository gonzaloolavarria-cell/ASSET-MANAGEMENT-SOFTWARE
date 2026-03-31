"""Tests for sync service — delta calculation, conflict detection (GAP-W03)."""

import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from tools.models.schemas import (
    SyncEntityType,
    SyncPullRequest,
    SyncPushItem,
    SyncPushRequest,
    ConflictRecord,
)
from api.services.sync_service import (
    calculate_delta,
    pull_entities,
    apply_push,
    detect_conflicts,
    _create_conflict,
    _model_to_dict,
)


class TestCalculateDelta:
    """Tests for delta calculation."""

    def test_returns_pull_response(self):
        """calculate_delta should return a SyncPullResponse."""
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        result = calculate_delta(db, SyncEntityType.CAPTURES, datetime(2020, 1, 1))
        assert result.entity_type == SyncEntityType.CAPTURES
        assert result.items == []
        assert result.has_more is False

    def test_unsupported_entity_returns_empty(self):
        """Unsupported entity type (CHECKLIST_PROGRESS) returns empty."""
        db = MagicMock()
        result = calculate_delta(db, SyncEntityType.CHECKLIST_PROGRESS, datetime(2020, 1, 1))
        assert result.items == []

    def test_has_more_when_exceeds_limit(self):
        """has_more should be True when result count exceeds limit."""
        db = MagicMock()
        # Return limit+1 mock objects
        mock_rows = []
        for i in range(6):
            row = MagicMock()
            row.capture_id = f"cap-{i}"
            row.version = 1
            row.modified_at = datetime.now()
            row.__table__ = MagicMock()
            row.__table__.columns = []
            mock_rows.append(row)

        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_rows

        result = calculate_delta(db, SyncEntityType.CAPTURES, datetime(2020, 1, 1), limit=5)
        assert result.has_more is True
        assert len(result.items) == 5

    def test_no_has_more_within_limit(self):
        """has_more should be False when within limit."""
        db = MagicMock()
        mock_rows = []
        for i in range(3):
            row = MagicMock()
            row.capture_id = f"cap-{i}"
            row.version = 1
            row.modified_at = datetime.now()
            row.__table__ = MagicMock()
            row.__table__.columns = []
            mock_rows.append(row)

        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_rows

        result = calculate_delta(db, SyncEntityType.CAPTURES, datetime(2020, 1, 1), limit=5)
        assert result.has_more is False
        assert len(result.items) == 3


class TestPullEntities:
    """Tests for pull_entities (multi-entity pull)."""

    def test_pull_multiple_types(self):
        """Should return one response per entity type."""
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        db.query.return_value.limit.return_value.all.return_value = []

        request = SyncPullRequest(
            entity_types=[SyncEntityType.CAPTURES, SyncEntityType.HIERARCHY_NODES],
            since=datetime(2020, 1, 1),
        )
        results = pull_entities(db, request)
        assert len(results) == 2

    def test_pull_respects_limit(self):
        """Limit from request should be passed to calculate_delta."""
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        request = SyncPullRequest(
            entity_types=[SyncEntityType.CAPTURES],
            since=datetime(2020, 1, 1),
            limit=50,
        )
        results = pull_entities(db, request)
        assert len(results) == 1


class TestApplyPush:
    """Tests for apply_push."""

    def test_push_empty_batch(self):
        """Empty batch should return zero accepted."""
        db = MagicMock()
        request = SyncPushRequest(items=[], device_id="test-device")
        result = apply_push(db, request)
        assert result.accepted == 0
        assert result.conflicts == []
        assert result.server_ids == {}

    def test_push_creates_capture(self):
        """Pushing a capture create should be accepted."""
        db = MagicMock()
        db.commit = MagicMock()

        item = SyncPushItem(
            entity_type=SyncEntityType.CAPTURES,
            local_id="local-001",
            action="create",
            data={
                "technicianId": "TECH-001",
                "captureType": "TEXT",
                "language": "en",
                "rawText": "Bearing noise",
                "equipmentTag": "BRY-SAG-ML-001",
            },
            offline_created_at=datetime.now(),
        )
        request = SyncPushRequest(items=[item], device_id="test-device")
        result = apply_push(db, request)
        assert result.accepted == 1
        assert "local-001" in result.server_ids
        # db.add called for capture model + audit log entry
        assert db.add.call_count == 2
        db.commit.assert_called_once()

    def test_push_readonly_rejected(self):
        """Pushing to read-only entity should not be accepted."""
        db = MagicMock()
        item = SyncPushItem(
            entity_type=SyncEntityType.HIERARCHY_NODES,
            local_id="local-node-001",
            action="create",
            data={"name": "Test"},
            offline_created_at=datetime.now(),
        )
        request = SyncPushRequest(items=[item], device_id="test-device")
        result = apply_push(db, request)
        assert result.accepted == 0


class TestConflictDetection:
    """Tests for conflict detection."""

    def test_no_conflict_when_versions_match(self):
        """No conflict when client version >= server version."""
        item = SyncPushItem(
            entity_type=SyncEntityType.CAPTURES,
            local_id="local-001",
            action="update",
            data={"version": 2, "rawText": "updated"},
            offline_created_at=datetime.now(),
        )
        result = detect_conflicts(item, {"raw_text": "old"}, server_version=2, server_modified_at=datetime.now())
        assert result is None

    def test_conflict_when_server_newer(self):
        """Conflict when server version > client version."""
        item = SyncPushItem(
            entity_type=SyncEntityType.CAPTURES,
            local_id="local-001",
            action="update",
            data={"version": 1, "rawText": "my edit"},
            offline_created_at=datetime.now() - timedelta(hours=1),
        )
        result = detect_conflicts(
            item,
            {"raw_text": "server edit"},
            server_version=2,
            server_modified_at=datetime.now(),
        )
        assert result is not None
        assert isinstance(result, ConflictRecord)
        assert result.entity_type == SyncEntityType.CAPTURES

    def test_no_conflict_when_client_ahead(self):
        """No conflict when client version > server version."""
        item = SyncPushItem(
            entity_type=SyncEntityType.CAPTURES,
            local_id="local-001",
            action="update",
            data={"version": 3, "rawText": "latest"},
            offline_created_at=datetime.now(),
        )
        result = detect_conflicts(item, {"raw_text": "old"}, server_version=2, server_modified_at=datetime.now())
        assert result is None


class TestCreateConflict:
    """Tests for _create_conflict helper."""

    def test_creates_valid_conflict(self):
        now = datetime.now()
        conflict = _create_conflict(
            entity_type=SyncEntityType.CAPTURES,
            entity_id="cap-001",
            local_data={"raw_text": "local value"},
            server_data={"raw_text": "server value"},
            local_modified_at=now - timedelta(hours=1),
            server_modified_at=now,
        )
        assert conflict.entity_type == SyncEntityType.CAPTURES
        assert conflict.entity_id == "cap-001"
        assert conflict.field == "raw_text"
        assert conflict.local_value == "local value"
        assert conflict.server_value == "server value"

    def test_conflict_finds_first_diff(self):
        """Should identify the first differing field."""
        now = datetime.now()
        conflict = _create_conflict(
            entity_type=SyncEntityType.CAPTURES,
            entity_id="cap-001",
            local_data={"field_a": "same", "field_b": "different_local"},
            server_data={"field_a": "same", "field_b": "different_server"},
            local_modified_at=now,
            server_modified_at=now,
        )
        assert conflict.field == "field_b"

    def test_conflict_when_no_diff(self):
        """When no diff found, field should be 'unknown'."""
        now = datetime.now()
        conflict = _create_conflict(
            entity_type=SyncEntityType.CAPTURES,
            entity_id="cap-001",
            local_data={"field_a": "same"},
            server_data={"field_a": "same"},
            local_modified_at=now,
            server_modified_at=now,
        )
        assert conflict.field == "unknown"


class TestModelToDict:
    """Tests for _model_to_dict helper."""

    def test_converts_model_with_datetime(self):
        """Should convert datetime fields to ISO strings."""
        mock = MagicMock()
        now = datetime.now()
        mock.__table__ = MagicMock()

        col1 = MagicMock()
        col1.name = "id"
        col2 = MagicMock()
        col2.name = "created_at"
        mock.__table__.columns = [col1, col2]

        mock.id = "test-id"
        mock.created_at = now

        result = _model_to_dict(mock, SyncEntityType.CAPTURES)
        assert result["id"] == "test-id"
        assert result["created_at"] == now.isoformat()

    def test_converts_model_with_none(self):
        """Should handle None values."""
        mock = MagicMock()
        col1 = MagicMock()
        col1.name = "field_a"
        mock.__table__ = MagicMock()
        mock.__table__.columns = [col1]
        mock.field_a = None

        result = _model_to_dict(mock, SyncEntityType.CAPTURES)
        assert result["field_a"] is None
