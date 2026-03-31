"""Tests for financial MCP tool wrappers (GAP-W04)."""

import json
import pytest

from agents.tool_wrappers.financial_tools import (
    calculate_roi, compare_roi_scenarios, calculate_financial_impact,
    calculate_man_hours_saved, track_budget, detect_budget_alerts,
    generate_financial_summary, forecast_budget,
)
from agents.tool_wrappers.registry import TOOL_REGISTRY


class TestFinancialToolsRegistered:
    """Verify all 8 financial tools are in the TOOL_REGISTRY."""

    EXPECTED_TOOLS = [
        "calculate_roi", "compare_roi_scenarios", "calculate_financial_impact",
        "calculate_man_hours_saved", "track_budget", "detect_budget_alerts",
        "generate_financial_summary", "forecast_budget",
    ]

    @pytest.mark.parametrize("tool_name", EXPECTED_TOOLS)
    def test_tool_in_registry(self, tool_name):
        assert tool_name in TOOL_REGISTRY, f"{tool_name} not registered"


class TestFinancialToolsCalls:
    """Verify financial tools return valid JSON results."""

    def test_calculate_roi(self):
        result = calculate_roi(json.dumps({
            "project_id": "P1", "plant_id": "OCP",
            "investment_cost": 500000,
            "annual_avoided_downtime_hours": 200,
            "hourly_production_value": 5000,
            "annual_labor_savings_hours": 1000,
            "annual_material_savings": 100000,
        }))
        data = json.loads(result)
        assert "npv" in data
        assert "bcr" in data
        assert data["npv"] > 0

    def test_compare_roi_scenarios(self):
        result = compare_roi_scenarios(json.dumps({
            "scenarios": [
                {"project_id": "A", "plant_id": "P", "investment_cost": 100000,
                 "annual_avoided_downtime_hours": 50, "hourly_production_value": 1000,
                 "annual_labor_savings_hours": 200, "annual_material_savings": 10000},
                {"project_id": "B", "plant_id": "P", "investment_cost": 200000,
                 "annual_avoided_downtime_hours": 100, "hourly_production_value": 2000,
                 "annual_labor_savings_hours": 400, "annual_material_savings": 20000},
            ]
        }))
        data = json.loads(result)
        assert len(data) == 2

    def test_calculate_financial_impact(self):
        result = calculate_financial_impact(json.dumps({
            "equipment_id": "SAG-01",
            "failure_rate": 3.0, "cost_per_failure": 50000,
            "cost_per_pm": 5000, "annual_pm_count": 12,
            "production_value_per_hour": 8000, "avg_downtime_hours": 24,
        }))
        data = json.loads(result)
        assert data["total_annual_impact"] > 0

    def test_calculate_man_hours_saved(self):
        result = calculate_man_hours_saved(json.dumps({
            "traditional_hours": {"planning": 100, "fmeca": 200},
            "ai_hours": {"planning": 40, "fmeca": 60},
            "labor_rate": 50.0,
        }))
        data = json.loads(result)
        assert data["hours_saved"] == 200

    def test_track_budget(self):
        result = track_budget(json.dumps({
            "plant_id": "OCP-JFC",
            "items": [
                {"item_id": "B1", "plant_id": "OCP", "category": "LABOR",
                 "description": "Labor", "planned_amount": 100000, "actual_amount": 110000},
            ],
        }))
        data = json.loads(result)
        assert "total_planned" in data
        assert data["total_planned"] == 100000

    def test_detect_budget_alerts(self):
        result = detect_budget_alerts(json.dumps({
            "plant_id": "OCP",
            "items": [
                {"item_id": "B1", "plant_id": "OCP", "category": "LABOR",
                 "description": "Labor", "planned_amount": 100000, "actual_amount": 130000},
            ],
            "threshold_pct": 10.0,
        }))
        data = json.loads(result)
        assert len(data) > 0

    def test_generate_financial_summary(self):
        result = generate_financial_summary(json.dumps({
            "plant_id": "OCP-JFC",
        }))
        data = json.loads(result)
        assert "plant_id" in data

    def test_forecast_budget(self):
        result = forecast_budget(json.dumps({
            "items": [
                {"item_id": "B1", "plant_id": "OCP", "category": "LABOR",
                 "description": "Labor", "planned_amount": 1200000, "actual_amount": 1300000},
            ],
            "months_ahead": 3,
        }))
        data = json.loads(result)
        assert len(data) > 0
