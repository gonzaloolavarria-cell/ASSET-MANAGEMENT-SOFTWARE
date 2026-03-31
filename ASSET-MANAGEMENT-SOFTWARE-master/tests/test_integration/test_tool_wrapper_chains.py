"""
Integration tests: MCP tool wrapper chains.
Tools called in sequence mimicking agent workflows.
"""

import json
import pytest

import agents.tool_wrappers.server  # noqa: F401 -- trigger registration
from agents.tool_wrappers.registry import call_tool


pytestmark = pytest.mark.integration


class TestHierarchyToolChain:
    """Hierarchy -> Criticality tool chain."""

    def test_assess_criticality_chain(self):
        """Criticality assessment via tool wrapper."""
        result = call_tool("assess_criticality", {"input_json": json.dumps({
            "node_id": "test-node",
            "criteria_scores": [
                {"category": "SAFETY", "consequence_level": 4},
                {"category": "HEALTH", "consequence_level": 3},
                {"category": "ENVIRONMENT", "consequence_level": 3},
                {"category": "PRODUCTION", "consequence_level": 5},
                {"category": "OPERATING_COST", "consequence_level": 4},
                {"category": "CAPITAL_COST", "consequence_level": 4},
                {"category": "SCHEDULE", "consequence_level": 3},
                {"category": "REVENUE", "consequence_level": 5},
                {"category": "COMMUNICATIONS", "consequence_level": 2},
                {"category": "COMPLIANCE", "consequence_level": 3},
                {"category": "REPUTATION", "consequence_level": 3},
            ],
            "probability": 4,
        })})
        data = json.loads(result)
        assert "overall_score" in data or "risk_class" in data

    def test_validate_hierarchy_chain(self):
        """Validation tool on hierarchy data."""
        result = call_tool("run_full_validation", {"input_json": json.dumps({
            "hierarchy_nodes": [
                {"node_id": "n1", "node_type": "PLANT", "name": "Test",
                 "name_fr": "Test", "code": "TST", "level": 1},
            ],
        })})
        assert result is not None

    def test_get_equipment_types(self):
        """Equipment types retrieval."""
        result = call_tool("get_equipment_types", {"input_json": json.dumps({})})
        data = json.loads(result)
        assert isinstance(data, (list, dict))


class TestFMECAToolChain:
    """FMECA -> RCM tool chain."""

    def test_rcm_decide_cbm_path(self):
        """RCM decision for CBM-feasible failure mode."""
        result = call_tool("rcm_decide", {"input_json": json.dumps({
            "is_hidden": False,
            "failure_consequence": "EVIDENT_OPERATIONAL",
            "cbm_technically_feasible": True,
            "cbm_economically_viable": True,
            "ft_feasible": True,
            "failure_pattern": "B_AGE",
        })})
        data = json.loads(result)
        assert data.get("strategy_type") == "CONDITION_BASED"

    def test_validate_fm_combinations(self):
        """FM combination validation tool."""
        result = call_tool("validate_fm_combinations", {"input_json": json.dumps({
            "combinations": [
                {"mechanism": "WEARS", "cause": "RELATIVE_MOVEMENT"},
                {"mechanism": "BURNS_OUT", "cause": "OVERLOADING"},
            ],
        })})
        assert result is not None

    def test_rcm_decide_hidden_failure(self):
        """RCM decision for hidden failure mode."""
        result = call_tool("rcm_decide", {"input_json": json.dumps({
            "is_hidden": True,
            "failure_consequence": "HIDDEN_SAFETY",
            "cbm_technically_feasible": False,
            "cbm_economically_viable": False,
            "ft_feasible": True,
        })})
        data = json.loads(result)
        assert "strategy_type" in data


class TestFinancialToolChain:
    """Financial calculation tool chain."""

    def test_roi_tool(self):
        """ROI calculation via tool."""
        result = call_tool("calculate_roi", {"input_json": json.dumps({
            "investment_cost": 100000,
            "annual_avoided_downtime_hours": 48,
            "hourly_production_value": 5000,
            "analysis_horizon_years": 5,
            "discount_rate": 0.08,
        })})
        data = json.loads(result)
        assert "npv" in data

    def test_budget_tool(self):
        """Budget tracking via tool."""
        result = call_tool("track_budget", {"input_json": json.dumps({
            "plant_id": "OCP-JFC1",
            "items": [
                {"category": "LABOR", "planned_amount": 50000, "actual_amount": 45000},
                {"category": "MATERIALS", "planned_amount": 30000, "actual_amount": 35000},
            ],
        })})
        data = json.loads(result)
        assert "total_planned" in data

    def test_quality_score_tool(self):
        """Quality score via tool."""
        result = call_tool("score_deliverable_quality", {"input_json": json.dumps({
            "deliverable_type": "hierarchy",
            "entities": {
                "hierarchy_nodes": [
                    {"node_id": "n1", "node_type": "PLANT", "name": "Test",
                     "name_fr": "Test", "code": "TST", "level": 1},
                ],
            },
            "milestone": 1,
        })})
        data = json.loads(result)
        assert "composite_score" in data or "score" in data or "grade" in data

    def test_tool_error_handling(self):
        """Tool returns structured error for invalid input."""
        result = call_tool("calculate_roi", {"input_json": json.dumps({})})
        # Should return some result (possibly error dict, not crash)
        assert result is not None
