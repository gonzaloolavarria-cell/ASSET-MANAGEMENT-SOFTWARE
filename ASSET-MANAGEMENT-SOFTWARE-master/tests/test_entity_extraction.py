"""Tests for _extract_entities_from_response and _extract_entities_from_tool_results in workflow.py."""

import json
import pytest
from unittest.mock import MagicMock

from agents.orchestration.workflow import (
    _extract_entities_from_response,
    _extract_entities_from_tool_results,
    _sanitize_entities,
    _ensure_ancestor_nodes,
)


class TestFencedJsonBlock:
    """Priority 1: ```json ... ``` fenced blocks."""

    def test_simple_fenced_block(self):
        response = 'Some text\n```json\n{"nodes": [1, 2]}\n```\nMore text'
        assert _extract_entities_from_response(response) == {"nodes": [1, 2]}

    def test_picks_largest_fenced_block(self):
        response = (
            '```json\n{"a": 1}\n```\n'
            'text in between\n'
            '```json\n{"hierarchy_nodes": [{"id": "1"}, {"id": "2"}], "extra": true}\n```\n'
        )
        result = _extract_entities_from_response(response)
        assert "hierarchy_nodes" in result
        assert len(result["hierarchy_nodes"]) == 2

    def test_fenced_block_with_whitespace(self):
        response = '```json\n\n  {"key": "val"}  \n\n```'
        assert _extract_entities_from_response(response) == {"key": "val"}

    def test_fenced_block_invalid_json_falls_through(self):
        response = '```json\n{broken json\n```\ntext with {"fallback": true} end'
        result = _extract_entities_from_response(response)
        assert result == {"fallback": True}


class TestIncrementalDecoder:
    """Priority 2: JSONDecoder scan for first valid object."""

    def test_json_embedded_in_text(self):
        response = 'Here is the result: {"nodes": [1]} and some trailing text.'
        assert _extract_entities_from_response(response) == {"nodes": [1]}

    def test_multiple_json_objects_picks_first(self):
        response = 'First: {"a": 1} Second: {"b": 2}'
        assert _extract_entities_from_response(response) == {"a": 1}

    def test_nested_braces(self):
        response = 'Result: {"outer": {"inner": [1, 2]}} done'
        result = _extract_entities_from_response(response)
        assert result == {"outer": {"inner": [1, 2]}}

    def test_greedy_regex_bug_fixed(self):
        """The old greedy regex would match from first { to last } corrupting JSON.
        The new incremental decoder handles this correctly."""
        response = 'Text { not json } more text {"valid": true} end } junk'
        result = _extract_entities_from_response(response)
        # Should NOT fail — the incremental decoder skips invalid `{ not json }`
        # and finds `{"valid": true}`
        assert result == {"valid": True}

    def test_multiline_json_object(self):
        obj = {"hierarchy_nodes": [{"node_id": "N1", "level": 1}]}
        response = f"Analysis complete.\n\n{json.dumps(obj, indent=2)}\n\nEnd of report."
        assert _extract_entities_from_response(response) == obj


class TestRawJsonFallback:
    """Priority 3: entire response is JSON."""

    def test_pure_json_response(self):
        obj = {"tasks": [{"id": "T1"}]}
        response = json.dumps(obj)
        assert _extract_entities_from_response(response) == obj


class TestEdgeCases:
    def test_empty_response(self):
        assert _extract_entities_from_response("") == {}

    def test_no_json_at_all(self):
        assert _extract_entities_from_response("Just plain text with no JSON.") == {}

    def test_json_array_not_dict(self):
        """Arrays should be skipped — we need a dict."""
        response = '[1, 2, 3]'
        assert _extract_entities_from_response(response) == {}

    def test_very_long_response_with_json_at_end(self):
        padding = "x" * 10000
        response = f"{padding}\n```json\n" + '{"found": true}\n```'
        assert _extract_entities_from_response(response) == {"found": True}

    def test_realistic_agent_response(self):
        """Simulate a real agent response with explanation + fenced JSON."""
        response = (
            "I have analyzed the SAG Mill and built the hierarchy.\n\n"
            "The equipment has 3 levels with 12 components.\n\n"
            "```json\n"
            "{\n"
            '  "hierarchy_nodes": [\n'
            '    {"node_id": "JFC-L1", "node_type": "PLANT", "name": "JFC Plant", '
            '"name_fr": "Usine JFC", "code": "JFC", "level": 1, "parent_node_id": null}\n'
            "  ],\n"
            '  "criticality_assessments": [\n'
            '    {"assessment_id": "CA-1", "node_id": "JFC-L6-001", "risk_class": "A", '
            '"assessed_at": "2026-01-01T00:00:00", "assessed_by": "reliability_agent"}\n'
            "  ]\n"
            "}\n"
            "```\n\n"
            "All 12 components have been assessed for criticality."
        )
        result = _extract_entities_from_response(response)
        assert "hierarchy_nodes" in result
        assert "criticality_assessments" in result
        assert result["hierarchy_nodes"][0]["node_type"] == "PLANT"


# ── Helper to build a mock agent with tool results ──────────────


def _make_agent_with_tool_results(tool_results: list[dict]):
    """Create a mock agent whose history contains the given tool results."""
    agent = MagicMock()
    turn = MagicMock()
    turn.tool_results = [
        {"result": json.dumps(tr), "tool_name": tr.get("_tool", "test")}
        for tr in tool_results
    ]
    turn.tool_calls = []
    agent.history = [turn]
    return agent


# ── Entity double-counting prevention tests ──────────────────────


class TestEntityDoubleCounting:
    """Verify negative-exclusion checks prevent cross-contamination."""

    def test_criticality_not_double_counted_as_hierarchy(self):
        """A dict with both node_id and assessment_id should only be criticality."""
        ca = {
            "assessment_id": "CA-001",
            "node_id": "MI-001",
            "risk_class": "A",
            "overall_score": 75,
            "assessed_at": "2026-01-01T00:00:00",
            "assessed_by": "reliability_agent",
        }
        agent = _make_agent_with_tool_results([ca])
        keys = ["hierarchy_nodes", "criticality_assessments"]
        result = _extract_entities_from_tool_results(agent, keys)

        assert "criticality_assessments" in result
        assert len(result["criticality_assessments"]) == 1
        assert result["criticality_assessments"][0]["assessment_id"] == "CA-001"
        # Must NOT appear in hierarchy_nodes
        assert "hierarchy_nodes" not in result or len(result.get("hierarchy_nodes", [])) == 0

    def test_functional_failure_not_double_counted_as_function(self):
        """A dict with failure_id + function_id should only be functional_failures."""
        ff = {
            "failure_id": "FF-001",
            "function_id": "F-001",
            "failure_type": "TOTAL",
            "description": "Unable to pump",
        }
        agent = _make_agent_with_tool_results([ff])
        keys = ["functions", "functional_failures", "failure_modes"]
        result = _extract_entities_from_tool_results(agent, keys)

        assert "functional_failures" in result
        assert len(result["functional_failures"]) == 1
        # Must NOT appear in functions
        assert "functions" not in result or len(result.get("functions", [])) == 0

    def test_mixed_tool_results_m1(self):
        """Simulate real M1: hierarchy tool returns nodes, then 14 assess_criticality calls."""
        hierarchy_result = {
            "hierarchy_nodes": [
                {"node_id": f"N-{i:03d}", "name": f"Node {i}", "level": (i % 6) + 1}
                for i in range(21)
            ]
        }
        assessments = [
            {
                "assessment_id": f"CA-{i:03d}",
                "node_id": f"N-{i+7:03d}",
                "risk_class": "A" if i % 2 == 0 else "B",
                "overall_score": 60 + i,
                "assessed_at": "2026-01-01T00:00:00",
                "assessed_by": "reliability_agent",
            }
            for i in range(14)
        ]

        # Build agent with one hierarchy tool result + 14 individual assessment results
        agent = MagicMock()
        turns = []
        # Turn 1: hierarchy result
        t1 = MagicMock()
        t1.tool_results = [{"result": json.dumps(hierarchy_result), "tool_name": "build_hierarchy_from_vendor"}]
        t1.tool_calls = [{"name": "build_hierarchy_from_vendor"}]
        turns.append(t1)
        # Turn 2+: individual assessment results
        for ca in assessments:
            t = MagicMock()
            t.tool_results = [{"result": json.dumps(ca), "tool_name": "assess_criticality"}]
            t.tool_calls = [{"name": "assess_criticality"}]
            turns.append(t)
        agent.history = turns

        keys = ["hierarchy_nodes", "criticality_assessments"]
        result = _extract_entities_from_tool_results(agent, keys)

        # Hierarchy should have exactly 21 nodes (from the array), not 35
        assert len(result.get("hierarchy_nodes", [])) == 21
        # Criticality should have exactly 14 assessments
        assert len(result.get("criticality_assessments", [])) == 14

    def test_work_package_not_counted_as_task(self):
        """A dict with wp_id + task_id should be work_packages, not maintenance_tasks."""
        wp = {
            "wp_id": "WP-001",
            "task_id": "T-001",
            "name": "PM Work Package",
            "task_ids": ["T-001", "T-002"],
        }
        agent = _make_agent_with_tool_results([wp])
        keys = ["maintenance_tasks", "work_packages"]
        result = _extract_entities_from_tool_results(agent, keys)

        assert "work_packages" in result
        assert len(result["work_packages"]) == 1
        assert "maintenance_tasks" not in result or len(result.get("maintenance_tasks", [])) == 0


# ── Post-extraction sanitization tests ───────────────────────────


class TestSanitizeEntities:
    """Verify _sanitize_entities cleans up cross-contaminated entities."""

    def test_sanitize_assessments_out_of_hierarchy_nodes(self):
        """Assessments mixed into hierarchy_nodes get moved to criticality_assessments."""
        entities = {
            "hierarchy_nodes": [
                {"node_id": "N-001", "node_type": "EQUIPMENT", "name": "SAG Mill", "level": 4},
                {"node_id": "N-002", "node_type": "SUB_ASSEMBLY", "name": "Drive", "level": 5},
                # These are assessments that snuck in because they have node_id
                {"assessment_id": "CA-001", "node_id": "N-001", "risk_class": "A", "overall_score": 20},
                {"assessment_id": "CA-002", "node_id": "N-002", "risk_class": "B", "overall_score": 12},
            ],
            "criticality_assessments": [
                {"assessment_id": "CA-001", "node_id": "N-001", "risk_class": "A", "overall_score": 20},
            ],
        }
        result = _sanitize_entities(entities, ["hierarchy_nodes", "criticality_assessments"])

        # hierarchy_nodes should only have real nodes
        assert len(result["hierarchy_nodes"]) == 2
        assert all("node_type" in n for n in result["hierarchy_nodes"])
        assert all("assessment_id" not in n for n in result["hierarchy_nodes"])

        # criticality_assessments should have 2 (1 existing + 1 deduped rescue)
        # CA-001 already existed, CA-002 is new
        assert len(result["criticality_assessments"]) == 2
        ca_ids = {a["assessment_id"] for a in result["criticality_assessments"]}
        assert ca_ids == {"CA-001", "CA-002"}

    def test_sanitize_real_v4_scenario(self):
        """Simulate the exact v4 session: 21 real nodes + 14 assessments in hierarchy_nodes."""
        real_nodes = [
            {"node_id": f"N-{i:03d}", "node_type": "EQUIPMENT", "name": f"Node {i}", "level": 4}
            for i in range(21)
        ]
        stray_assessments = [
            {"assessment_id": f"CA-{i:03d}", "node_id": f"N-{i:03d}", "risk_class": "A", "overall_score": 15}
            for i in range(14)
        ]
        entities = {
            "hierarchy_nodes": real_nodes + stray_assessments,
            "criticality_assessments": list(stray_assessments),  # already there too
        }
        result = _sanitize_entities(entities, ["hierarchy_nodes", "criticality_assessments"])

        assert len(result["hierarchy_nodes"]) == 21
        # Deduplication means we don't add duplicates
        assert len(result["criticality_assessments"]) == 14

    def test_sanitize_failures_out_of_functions(self):
        """functional_failures mixed into functions get separated."""
        entities = {
            "functions": [
                {"function_id": "F-001", "node_id": "N-001", "description": "Pump fluid"},
                {"failure_id": "FF-001", "function_id": "F-001", "description": "No flow"},
            ],
            "functional_failures": [],
        }
        result = _sanitize_entities(entities, ["functions", "functional_failures"])
        assert len(result["functions"]) == 1
        assert result["functions"][0]["function_id"] == "F-001"
        assert len(result["functional_failures"]) == 1
        assert result["functional_failures"][0]["failure_id"] == "FF-001"

    def test_sanitize_work_packages_out_of_tasks(self):
        """work_packages mixed into maintenance_tasks get separated."""
        entities = {
            "maintenance_tasks": [
                {"task_id": "T-001", "task_type": "INSPECT", "description": "Inspect"},
                {"wp_id": "WP-001", "task_ids": ["T-001"], "name": "PM Package"},
            ],
        }
        result = _sanitize_entities(entities, ["maintenance_tasks", "work_packages"])
        assert len(result["maintenance_tasks"]) == 1
        assert result["maintenance_tasks"][0]["task_id"] == "T-001"
        assert len(result["work_packages"]) == 1
        assert result["work_packages"][0]["wp_id"] == "WP-001"

    def test_sanitize_noop_when_clean(self):
        """Clean entities are not modified."""
        entities = {
            "hierarchy_nodes": [
                {"node_id": "N-001", "node_type": "EQUIPMENT", "name": "Mill", "level": 4},
            ],
            "criticality_assessments": [
                {"assessment_id": "CA-001", "node_id": "N-001", "risk_class": "A"},
            ],
        }
        result = _sanitize_entities(entities, ["hierarchy_nodes", "criticality_assessments"])
        assert len(result["hierarchy_nodes"]) == 1
        assert len(result["criticality_assessments"]) == 1


# ── Ancestor node generation tests ──────────────────────────────


class TestEnsureAncestorNodes:
    """Verify L1-L3 synthetic ancestors are generated when missing."""

    def test_adds_l1_l2_l3_when_missing(self):
        """L4+ nodes from build_from_vendor get L1-L3 ancestors."""
        nodes = [
            {"node_id": "E1", "node_type": "EQUIPMENT", "name": "SAG Mill",
             "level": 4, "tag": "GRD-SAG-ML-001", "parent_node_id": None},
            {"node_id": "SA1", "node_type": "SUB_ASSEMBLY", "name": "Drive",
             "level": 5, "tag": "GRD-SAG-ML-001-DRV", "parent_node_id": "E1"},
        ]
        result = _ensure_ancestor_nodes(nodes, "OCP-JFC", "SAG Mill 001")

        # Should have 3 added + 2 original = 5 nodes
        assert len(result) == 5

        # Check L1/L2/L3 exist
        levels = {n.get("level") for n in result}
        assert {1, 2, 3, 4, 5} == levels

        # L4 should now have parent_node_id pointing to L3
        l4 = [n for n in result if n.get("level") == 4][0]
        assert l4["parent_node_id"] is not None
        assert l4["parent_node_id"].startswith("SYN-L3-")

        # Parent chain: L3→L2→L1
        l3 = [n for n in result if n.get("level") == 3][0]
        l2 = [n for n in result if n.get("level") == 2][0]
        l1 = [n for n in result if n.get("level") == 1][0]
        assert l3["parent_node_id"] == l2["node_id"]
        assert l2["parent_node_id"] == l1["node_id"]
        assert l1["parent_node_id"] is None

    def test_noop_when_ancestors_exist(self):
        """If L1-L3 already exist, no synthetic nodes added."""
        nodes = [
            {"node_id": "P1", "level": 1, "name": "Plant"},
            {"node_id": "A1", "level": 2, "name": "Area"},
            {"node_id": "S1", "level": 3, "name": "System"},
            {"node_id": "E1", "level": 4, "name": "Equipment", "parent_node_id": "S1"},
        ]
        result = _ensure_ancestor_nodes(nodes, "OCP-JFC", "SAG Mill")
        assert len(result) == 4  # No change

    def test_preserves_existing_parent_node_id(self):
        """If L4 already has parent_node_id, don't overwrite it."""
        nodes = [
            {"node_id": "E1", "level": 4, "name": "Mill", "tag": "GRD-001",
             "parent_node_id": "EXISTING-PARENT"},
        ]
        result = _ensure_ancestor_nodes(nodes, "OCP-JFC", "SAG Mill")
        l4 = [n for n in result if n.get("level") == 4][0]
        # parent_node_id should remain "EXISTING-PARENT" since it was set
        assert l4["parent_node_id"] == "EXISTING-PARENT"
