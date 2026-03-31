"""Tests for import MCP tool wrappers (G-18 / Phase B)."""

from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest

# Import triggers @tool decorator registration
import agents.tool_wrappers.import_tools  # noqa: F401
from agents.tool_wrappers.registry import call_tool, TOOL_REGISTRY


class TestListImportSources:
    def test_tool_registered(self):
        assert "list_import_sources" in TOOL_REGISTRY

    def test_returns_json_list(self):
        result = call_tool("list_import_sources", {})
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) > 0

    def test_contains_expected_sources(self):
        result = call_tool("list_import_sources", {})
        data = json.loads(result)
        assert "EQUIPMENT_HIERARCHY" in data
        assert "FAILURE_HISTORY" in data
        assert "MAINTENANCE_PLAN" in data
        assert "CRITICALITY_ASSESSMENT" in data

    def test_no_error_key(self):
        result = call_tool("list_import_sources", {})
        data = json.loads(result)
        assert "error" not in data


class TestImportDataFileToolRegistered:
    def test_tool_registered(self):
        assert "import_data_file" in TOOL_REGISTRY

    def test_tool_has_description(self):
        info = TOOL_REGISTRY["import_data_file"]
        assert "PERSIST" in info["description"]
        assert "import_id" in info["description"]

    def test_missing_required_fields_returns_error(self):
        result = call_tool("import_data_file", {"input_json": json.dumps({})})
        data = json.loads(result)
        # Should return error (missing source/plant_id/file_b64)
        assert "error" in data


class TestGetImportHistoryToolRegistered:
    def test_tool_registered(self):
        assert "get_import_history" in TOOL_REGISTRY

    def test_tool_has_description(self):
        info = TOOL_REGISTRY["get_import_history"]
        assert "history" in info["description"].lower()

    def test_connection_error_returns_error(self):
        """When API is not running, should return an error dict, not raise."""
        with patch("httpx.get", side_effect=httpx.ConnectError("Connection refused")):
            result = call_tool("get_import_history", {"input_json": json.dumps({"plant_id": "TEST"})})
        data = json.loads(result)
        # Connection refused → error
        assert "error" in data
