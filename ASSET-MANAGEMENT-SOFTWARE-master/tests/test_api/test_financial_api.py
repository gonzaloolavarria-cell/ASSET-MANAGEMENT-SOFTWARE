"""Tests for financial API endpoints (api/routers/financial.py)."""

import pytest

pytestmark = pytest.mark.integration


def _roi_input(**overrides):
    """Build a valid ROIInput dict."""
    data = {
        "project_id": "PRJ-TEST-001",
        "plant_id": "OCP-JFC1",
        "description": "Test ROI project",
        "investment_cost": 100000.0,
        "annual_avoided_downtime_hours": 48.0,
        "hourly_production_value": 5000.0,
        "annual_labor_savings_hours": 120.0,
        "labor_cost_per_hour": 50.0,
        "annual_material_savings": 10000.0,
        "annual_operating_cost_increase": 5000.0,
        "analysis_horizon_years": 5,
        "discount_rate": 0.08,
    }
    data.update(overrides)
    return data


def _budget_item(**overrides):
    """Build a valid BudgetItem dict."""
    data = {
        "plant_id": "OCP-JFC1",
        "equipment_id": "EQ-001",
        "cost_center": "CC-001",
        "category": "LABOR",
        "description": "Test budget item",
        "planned_amount": 50000.0,
        "actual_amount": 45000.0,
    }
    data.update(overrides)
    return data


class TestROIEndpoints:
    """Tests for ROI calculation endpoints."""

    def test_calculate_roi_basic(self, client):
        resp = client.post("/api/v1/financial/roi", json=_roi_input())
        assert resp.status_code == 200
        data = resp.json()
        assert "npv" in data
        assert "investment_cost" in data
        assert data["investment_cost"] == 100000.0

    def test_calculate_roi_zero_investment(self, client):
        resp = client.post("/api/v1/financial/roi", json=_roi_input(investment_cost=0))
        # Should handle gracefully (either 200 or 422)
        assert resp.status_code in (200, 422)

    def test_calculate_roi_negative_savings(self, client):
        resp = client.post("/api/v1/financial/roi", json=_roi_input(
            annual_avoided_downtime_hours=0,
            annual_labor_savings_hours=0,
            annual_material_savings=0,
            annual_operating_cost_increase=50000.0,
        ))
        assert resp.status_code == 200
        data = resp.json()
        # BCR can be negative
        assert "bcr" in data

    def test_compare_scenarios(self, client):
        scenarios = {
            "scenarios": [
                _roi_input(project_id="scenario-1", investment_cost=50000),
                _roi_input(project_id="scenario-2", investment_cost=100000),
                _roi_input(project_id="scenario-3", investment_cost=200000),
            ]
        }
        resp = client.post("/api/v1/financial/roi/compare", json=scenarios)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 3

    def test_financial_impact(self, client):
        resp = client.post("/api/v1/financial/impact", json={
            "equipment_id": "EQ-SAG-001",
            "failure_rate": 2.5,
            "cost_per_failure": 25000.0,
            "annual_pm_cost": 15000.0,
            "downtime_per_failure": 24.0,
            "production_value_per_hour": 5000.0,
            "man_hours_current": 500.0,
            "man_hours_optimized": 350.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "total_annual_impact" in data

    def test_man_hours_saved(self, client):
        resp = client.post("/api/v1/financial/man-hours", json={
            "traditional_hours": {"inspection": 200, "planning": 100, "reporting": 80},
            "ai_hours": {"inspection": 150, "planning": 60, "reporting": 30},
            "labor_rate": 65.0,
            "plant_id": "OCP-JFC1",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "hours_saved" in data


class TestBudgetEndpoints:
    """Tests for budget tracking endpoints."""

    def test_track_budget_basic(self, client):
        resp = client.post("/api/v1/financial/budget/track", json={
            "plant_id": "OCP-JFC1",
            "items": [
                _budget_item(category="LABOR", planned_amount=50000, actual_amount=45000),
                _budget_item(category="MATERIALS", planned_amount=30000, actual_amount=35000),
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "total_planned" in data

    def test_track_budget_empty_items(self, client):
        resp = client.post("/api/v1/financial/budget/track", json={
            "plant_id": "OCP-JFC1",
            "items": [],
        })
        assert resp.status_code == 200

    def test_budget_alerts(self, client):
        # First get a budget summary
        track_resp = client.post("/api/v1/financial/budget/track", json={
            "plant_id": "OCP-JFC1",
            "items": [
                _budget_item(category="MATERIALS", planned_amount=30000, actual_amount=45000),
            ],
        })
        assert track_resp.status_code == 200
        summary = track_resp.json()
        resp = client.post("/api/v1/financial/budget/alerts", json={
            "summary": summary,
            "threshold_pct": 10.0,
        })
        assert resp.status_code == 200

    def test_financial_summary(self, client):
        resp = client.get("/api/v1/financial/summary/OCP-JFC1")
        assert resp.status_code == 200

    def test_budget_forecast(self, client):
        resp = client.post("/api/v1/financial/budget/forecast", json={
            "items": [
                _budget_item(planned_amount=120000, actual_amount=30000),
            ],
            "months_ahead": 3,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_track_budget_large_numbers(self, client):
        resp = client.post("/api/v1/financial/budget/track", json={
            "plant_id": "OCP-JFC1",
            "items": [
                _budget_item(planned_amount=10000000, actual_amount=9500000),
            ],
        })
        assert resp.status_code == 200

    def test_roi_with_long_horizon(self, client):
        resp = client.post("/api/v1/financial/roi", json=_roi_input(analysis_horizon_years=20))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data.get("cumulative_savings_by_year", [])) == 20
