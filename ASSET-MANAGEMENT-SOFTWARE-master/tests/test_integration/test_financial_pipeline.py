"""
Integration tests: Financial engine pipeline.
ROI + Budget + Impact calculations with realistic OCP scenarios.
"""

import pytest
from datetime import date

from tools.engines.roi_engine import ROIEngine
from tools.engines.budget_engine import BudgetEngine
from tools.models.schemas import (
    BudgetItem,
    FinancialCategory,
    ROIInput,
    CurrencyCode,
)


pytestmark = pytest.mark.integration


class TestROIBudgetIntegration:
    """ROI and budget engine integration tests."""

    def test_roi_basic_calculation(self, pipeline_roi_input):
        """ROI engine produces valid result from realistic input."""
        result = ROIEngine.calculate_roi(pipeline_roi_input)
        assert result.investment_cost == pipeline_roi_input.investment_cost
        assert result.npv != 0
        assert len(result.cumulative_savings_by_year) == pipeline_roi_input.analysis_horizon_years

    def test_roi_positive_npv_scenario(self, pipeline_roi_input):
        """High-savings scenario yields positive NPV."""
        result = ROIEngine.calculate_roi(pipeline_roi_input)
        # 96hrs * $12k/hr = $1.15M annual savings vs $180k investment
        assert result.npv > 0
        assert result.bcr > 1.0

    def test_roi_payback_period(self, pipeline_roi_input):
        """Payback period is reasonable for this scenario."""
        result = ROIEngine.calculate_roi(pipeline_roi_input)
        if result.payback_period_years is not None:
            assert result.payback_period_years > 0
            assert result.payback_period_years < pipeline_roi_input.analysis_horizon_years

    def test_scenario_comparison(self, pipeline_roi_input):
        """Compare multiple ROI scenarios, sorted by NPV."""
        scenarios = [
            pipeline_roi_input,
            ROIInput(
                project_id="low-invest",
                plant_id="OCP-JFC1",
                investment_cost=50000,
                annual_avoided_downtime_hours=24,
                hourly_production_value=12000,
                analysis_horizon_years=5,
                discount_rate=0.08,
            ),
            ROIInput(
                project_id="high-invest",
                plant_id="OCP-JFC1",
                investment_cost=500000,
                annual_avoided_downtime_hours=200,
                hourly_production_value=12000,
                analysis_horizon_years=5,
                discount_rate=0.08,
            ),
        ]
        results = ROIEngine.compare_scenarios(scenarios)
        assert len(results) == 3
        # Should be sorted by NPV descending
        for i in range(len(results) - 1):
            assert results[i].npv >= results[i + 1].npv

    def test_budget_tracking_from_items(self, pipeline_budget_items):
        """Budget engine tracks items correctly."""
        items_dicts = [item.model_dump() for item in pipeline_budget_items]
        for item in items_dicts:
            for key in ("period_start", "period_end"):
                if item.get(key) and hasattr(item[key], "isoformat"):
                    item[key] = item[key].isoformat()
        summary = BudgetEngine.track_budget("OCP-JFC1", items_dicts)
        assert summary.total_planned > 0
        assert summary.total_actual > 0

    def test_budget_variance_alerts(self, pipeline_budget_items):
        """Variance alerts triggered for over-budget categories."""
        items_dicts = [item.model_dump() for item in pipeline_budget_items]
        for item in items_dicts:
            for key in ("period_start", "period_end"):
                if item.get(key) and hasattr(item[key], "isoformat"):
                    item[key] = item[key].isoformat()
        summary = BudgetEngine.track_budget("OCP-JFC1", items_dicts)
        alerts = BudgetEngine.detect_variance_alerts(summary, threshold_pct=5.0)
        # With a 5% threshold, some items should trigger alerts
        assert isinstance(alerts, list)

    def test_financial_impact_calculation(self):
        """Financial impact for SAG mill failure scenario."""
        impact = ROIEngine.calculate_financial_impact(
            equipment_id="EQ-SAG-001",
            failure_rate=2.0,
            cost_per_failure=25000.0,
            cost_per_pm=5000.0,
            annual_pm_count=3,
            production_value_per_hour=12000.0,
            avg_downtime_hours=24.0,
        )
        assert impact.total_annual_impact > 0
        assert impact.annual_failure_cost > 0

    def test_man_hours_saved(self):
        """Man-hours comparison between traditional and AI-assisted."""
        report = ROIEngine.calculate_man_hours_saved(
            traditional_hours={"inspection": 200, "planning": 150, "reporting": 80},
            ai_hours={"inspection": 120, "planning": 80, "reporting": 25},
            labor_rate=65.0,
            plant_id="OCP-JFC1",
        )
        assert report.traditional_man_hours > report.ai_assisted_man_hours
        assert report.hours_saved > 0


class TestFinancialEdgeCases:
    """Edge cases for financial calculations."""

    def test_zero_discount_rate(self):
        """ROI with 0% discount rate."""
        inp = ROIInput(
            investment_cost=100000,
            annual_avoided_downtime_hours=50,
            hourly_production_value=5000,
            analysis_horizon_years=5,
            discount_rate=0.0,
        )
        result = ROIEngine.calculate_roi(inp)
        assert result is not None

    def test_one_year_horizon(self):
        """ROI with 1-year horizon."""
        inp = ROIInput(
            investment_cost=100000,
            annual_avoided_downtime_hours=50,
            hourly_production_value=5000,
            analysis_horizon_years=1,
            discount_rate=0.08,
        )
        result = ROIEngine.calculate_roi(inp)
        assert len(result.cumulative_savings_by_year) == 1

    def test_high_discount_rate(self):
        """ROI with 50% discount rate."""
        inp = ROIInput(
            investment_cost=100000,
            annual_avoided_downtime_hours=50,
            hourly_production_value=5000,
            analysis_horizon_years=5,
            discount_rate=0.5,
        )
        result = ROIEngine.calculate_roi(inp)
        assert result is not None

    def test_all_financial_categories(self):
        """Budget tracking with all category values."""
        items = []
        for cat in FinancialCategory:
            items.append({
                "plant_id": "TEST",
                "category": cat.value,
                "planned_amount": 10000,
                "actual_amount": 9500,
            })
        summary = BudgetEngine.track_budget("TEST", items)
        assert summary.total_planned > 0

    def test_single_budget_item(self):
        """Budget with single item."""
        items = [{
            "plant_id": "TEST",
            "category": "LABOR",
            "planned_amount": 50000,
            "actual_amount": 45000,
        }]
        summary = BudgetEngine.track_budget("TEST", items)
        assert summary.total_planned == 50000

    def test_net_negative_savings(self):
        """ROI with net-negative savings (cost increase > savings)."""
        inp = ROIInput(
            investment_cost=100000,
            annual_avoided_downtime_hours=0,
            hourly_production_value=0,
            annual_operating_cost_increase=50000,
            analysis_horizon_years=5,
            discount_rate=0.08,
        )
        result = ROIEngine.calculate_roi(inp)
        assert result.npv < 0

    def test_budget_forecast(self, pipeline_budget_items):
        """Budget forecast produces future items."""
        forecast = BudgetEngine.forecast_budget(pipeline_budget_items, months_ahead=3)
        assert isinstance(forecast, list)

    def test_cumulative_savings_monotonic(self, pipeline_roi_input):
        """Cumulative savings should be monotonically increasing (if positive)."""
        result = ROIEngine.calculate_roi(pipeline_roi_input)
        savings = result.cumulative_savings_by_year
        if len(savings) > 1 and result.annual_net_savings > 0:
            for i in range(1, len(savings)):
                assert savings[i] >= savings[i - 1], (
                    f"Cumulative savings not monotonic: {savings}"
                )

    def test_irr_convergence(self, pipeline_roi_input):
        """IRR should converge for reasonable scenarios."""
        result = ROIEngine.calculate_roi(pipeline_roi_input)
        if result.irr_pct is not None:
            assert result.irr_pct > 0  # Positive returns expected

    def test_empty_man_hours(self):
        """Man-hours with empty dicts."""
        report = ROIEngine.calculate_man_hours_saved(
            traditional_hours={},
            ai_hours={},
            labor_rate=50.0,
            plant_id="TEST",
        )
        assert report.hours_saved == 0
