"""Tests for ROI and Budget engines (GAP-W04)."""

import pytest
from datetime import date

from tools.engines.roi_engine import ROIEngine
from tools.engines.budget_engine import BudgetEngine
from tools.models.schemas import (
    BudgetItem, BudgetSummary, ROIInput, ROIResult,
    FinancialCategory, ROIStatus, CurrencyCode,
)


# ════════════════════════════════════════════════════════════════
# ROI Engine Tests
# ════════════════════════════════════════════════════════════════

class TestROIEngine:
    """Unit tests for ROIEngine methods."""

    def _basic_input(self, **overrides) -> ROIInput:
        defaults = {
            "project_id": "P-001",
            "plant_id": "OCP-JFC",
            "investment_cost": 500_000,
            "annual_avoided_downtime_hours": 200,
            "hourly_production_value": 5000,
            "annual_labor_savings_hours": 1000,
            "labor_cost_per_hour": 50,
            "annual_material_savings": 100_000,
            "analysis_horizon_years": 5,
            "discount_rate": 0.08,
        }
        defaults.update(overrides)
        return ROIInput(**defaults)

    def test_calculate_roi_basic(self):
        inp = self._basic_input()
        result = ROIEngine.calculate_roi(inp)
        assert isinstance(result, ROIResult)
        assert result.project_id == "P-001"
        assert result.plant_id == "OCP-JFC"
        # Gross = 200*5000 + 1000*50 + 100000 = 1_150_000
        assert result.annual_gross_savings == 1_150_000
        assert result.annual_net_savings == 1_150_000  # no operating cost increase
        assert result.npv > 0
        assert result.bcr > 1.0
        assert result.roi_pct > 0
        assert result.payback_period_years is not None
        assert result.payback_period_years < 1.0  # Very short payback
        assert result.status == ROIStatus.PROJECTED
        assert result.recommendation == "Strong ROI: investment highly justified"
        assert len(result.cumulative_savings_by_year) == 5

    def test_calculate_roi_zero_investment(self):
        inp = self._basic_input(investment_cost=0)
        result = ROIEngine.calculate_roi(inp)
        assert result.bcr == 0.0
        assert result.roi_pct == 0.0
        assert result.payback_period_years is None

    def test_calculate_roi_negative_net_savings(self):
        inp = self._basic_input(
            annual_avoided_downtime_hours=0,
            annual_labor_savings_hours=0,
            annual_material_savings=0,
            annual_operating_cost_increase=100_000,
        )
        result = ROIEngine.calculate_roi(inp)
        assert result.annual_net_savings < 0
        assert result.npv < 0
        assert result.payback_period_years is None
        assert "Negative" in result.recommendation

    def test_calculate_roi_marginal(self):
        inp = self._basic_input(
            investment_cost=1_000_000,
            annual_avoided_downtime_hours=10,
            hourly_production_value=100,
            annual_labor_savings_hours=10,
            annual_material_savings=1000,
            annual_operating_cost_increase=0,
        )
        result = ROIEngine.calculate_roi(inp)
        assert result.bcr < 1.0

    def test_irr_convergence(self):
        inp = self._basic_input()
        result = ROIEngine.calculate_roi(inp)
        assert result.irr_pct is not None
        assert result.irr_pct > 0

    def test_irr_no_convergence_negative_savings(self):
        inp = self._basic_input(
            annual_avoided_downtime_hours=0,
            annual_labor_savings_hours=0,
            annual_material_savings=0,
            annual_operating_cost_increase=50000,
        )
        result = ROIEngine.calculate_roi(inp)
        assert result.irr_pct is None

    def test_cumulative_savings_increasing(self):
        inp = self._basic_input()
        result = ROIEngine.calculate_roi(inp)
        cum = result.cumulative_savings_by_year
        assert len(cum) == 5
        # Cumulative savings should be increasing
        for i in range(1, len(cum)):
            assert cum[i] > cum[i - 1]

    def test_compare_scenarios(self):
        inputs = [
            self._basic_input(project_id="LOW", investment_cost=1_000_000,
                              annual_avoided_downtime_hours=10, hourly_production_value=100),
            self._basic_input(project_id="HIGH", investment_cost=500_000),
        ]
        results = ROIEngine.compare_scenarios(inputs)
        assert len(results) == 2
        assert results[0].npv >= results[1].npv  # Sorted by NPV desc

    def test_calculate_financial_impact(self):
        impact = ROIEngine.calculate_financial_impact(
            equipment_id="SAG-MILL-01",
            failure_rate=3.0,
            cost_per_failure=50_000,
            cost_per_pm=5_000,
            annual_pm_count=12,
            production_value_per_hour=8_000,
            avg_downtime_hours=24,
        )
        assert impact.equipment_id == "SAG-MILL-01"
        assert impact.annual_failure_cost == 150_000  # 3 * 50000
        assert impact.annual_pm_cost == 60_000  # 5000 * 12
        assert impact.annual_production_loss == 576_000  # 3 * 24 * 8000
        assert impact.total_annual_impact == 786_000
        assert impact.annual_downtime_hours == 72  # 3 * 24

    def test_calculate_financial_impact_zero_failure_rate(self):
        impact = ROIEngine.calculate_financial_impact(
            equipment_id="EQ-SAFE",
            failure_rate=0.0,
            cost_per_failure=100_000,
            cost_per_pm=1_000,
            annual_pm_count=12,
            production_value_per_hour=5_000,
            avg_downtime_hours=8,
        )
        assert impact.annual_failure_cost == 0
        assert impact.annual_production_loss == 0
        assert impact.annual_pm_cost == 12_000

    def test_calculate_man_hours_saved(self):
        result = ROIEngine.calculate_man_hours_saved(
            traditional_hours={"planning": 100, "fmeca": 200, "tasks": 150},
            ai_hours={"planning": 40, "fmeca": 60, "tasks": 50},
            labor_rate=50.0,
            plant_id="OCP-JFC",
        )
        assert result.traditional_man_hours == 450
        assert result.ai_assisted_man_hours == 150
        assert result.hours_saved == 300
        assert result.savings_pct == 66.7
        assert result.cost_equivalent == 15_000  # 300 * 50

    def test_man_hours_saved_no_savings(self):
        result = ROIEngine.calculate_man_hours_saved(
            traditional_hours={"planning": 100},
            ai_hours={"planning": 120},
            labor_rate=50.0,
        )
        assert result.hours_saved == 0  # max(0, -20) = 0

    def test_currency_propagation(self):
        inp = self._basic_input(currency=CurrencyCode.EUR)
        result = ROIEngine.calculate_roi(inp)
        assert result.currency == CurrencyCode.EUR

    def test_large_scale_80m_budget(self):
        """Verify engine handles OCP-scale budgets (80M USD/year)."""
        inp = self._basic_input(
            investment_cost=5_000_000,
            annual_avoided_downtime_hours=500,
            hourly_production_value=50_000,
            annual_labor_savings_hours=5000,
            labor_cost_per_hour=80,
            annual_material_savings=2_000_000,
            analysis_horizon_years=10,
        )
        result = ROIEngine.calculate_roi(inp)
        assert result.npv > 0
        assert result.annual_gross_savings > 25_000_000


# ════════════════════════════════════════════════════════════════
# Budget Engine Tests
# ════════════════════════════════════════════════════════════════

class TestBudgetEngine:
    """Unit tests for BudgetEngine methods."""

    def _sample_items(self) -> list[dict]:
        return [
            {"item_id": "B1", "plant_id": "OCP-JFC", "category": "LABOR",
             "description": "Labor", "planned_amount": 1_000_000, "actual_amount": 1_100_000},
            {"item_id": "B2", "plant_id": "OCP-JFC", "category": "MATERIALS",
             "description": "Materials", "planned_amount": 500_000, "actual_amount": 450_000},
            {"item_id": "B3", "plant_id": "OCP-JFC", "category": "CONTRACTORS",
             "description": "Contractors", "planned_amount": 300_000, "actual_amount": 400_000},
        ]

    def test_track_budget(self):
        summary = BudgetEngine.track_budget("OCP-JFC", self._sample_items())
        assert isinstance(summary, BudgetSummary)
        assert summary.plant_id == "OCP-JFC"
        assert summary.total_planned == 1_800_000
        assert summary.total_actual == 1_950_000
        assert summary.total_variance == 150_000
        assert summary.variance_pct > 0
        assert "LABOR" in summary.by_category
        assert "MATERIALS" in summary.by_category

    def test_track_budget_over_budget_categories(self):
        summary = BudgetEngine.track_budget("OCP-JFC", self._sample_items())
        # CONTRACTORS: 400000/300000 = 33% over → should be flagged
        assert "CONTRACTORS" in summary.over_budget_categories

    def test_track_budget_recommendations(self):
        summary = BudgetEngine.track_budget("OCP-JFC", self._sample_items())
        assert len(summary.recommendations) > 0

    def test_track_budget_empty(self):
        summary = BudgetEngine.track_budget("EMPTY", [])
        assert summary.total_planned == 0
        assert summary.total_actual == 0

    def test_detect_variance_alerts_default_threshold(self):
        summary = BudgetEngine.track_budget("OCP-JFC", self._sample_items())
        alerts = BudgetEngine.detect_variance_alerts(summary)
        assert len(alerts) > 0
        # CONTRACTORS is 33% over → should trigger CRITICAL (> 2x threshold)
        critical_alerts = [a for a in alerts if a.severity == "CRITICAL"]
        assert len(critical_alerts) > 0

    def test_detect_variance_alerts_custom_threshold(self):
        summary = BudgetEngine.track_budget("OCP-JFC", self._sample_items())
        alerts_strict = BudgetEngine.detect_variance_alerts(summary, threshold_pct=5.0)
        alerts_loose = BudgetEngine.detect_variance_alerts(summary, threshold_pct=50.0)
        assert len(alerts_strict) >= len(alerts_loose)

    def test_detect_variance_alerts_sorted_by_severity(self):
        summary = BudgetEngine.track_budget("OCP-JFC", self._sample_items())
        alerts = BudgetEngine.detect_variance_alerts(summary)
        if len(alerts) > 1:
            # Sorted by absolute variance_pct descending
            for i in range(1, len(alerts)):
                assert abs(alerts[i - 1].variance_pct) >= abs(alerts[i].variance_pct)

    def test_generate_financial_summary_empty(self):
        summary = BudgetEngine.generate_financial_summary("OCP-JFC")
        assert summary.plant_id == "OCP-JFC"
        assert summary.total_maintenance_budget == 0
        assert summary.resource_productivity_multiplier == 1.0

    def test_generate_financial_summary_full(self):
        budget = BudgetEngine.track_budget("OCP-JFC", self._sample_items())
        roi = ROIEngine.calculate_roi(ROIInput(
            project_id="P1", plant_id="OCP-JFC", investment_cost=500000,
            annual_avoided_downtime_hours=200, hourly_production_value=5000,
            annual_labor_savings_hours=1000, annual_material_savings=100000,
        ))
        impact = ROIEngine.calculate_financial_impact(
            "SAG-01", 3.0, 50000, 5000, 12, 8000, 24,
        )
        man_hrs = ROIEngine.calculate_man_hours_saved(
            {"planning": 100}, {"planning": 40}, 50.0,
        )
        summary = BudgetEngine.generate_financial_summary(
            "OCP-JFC", budget, roi, [impact], man_hrs,
        )
        assert summary.total_maintenance_budget == 1_800_000
        assert summary.total_avoided_cost > 0
        assert summary.total_man_hours_saved > 0
        assert summary.resource_productivity_multiplier > 1.0
        assert len(summary.top_cost_drivers) > 0
        assert len(summary.recommendations) > 0

    def test_forecast_budget(self):
        items = [BudgetItem(**i) for i in self._sample_items()]
        forecasts = BudgetEngine.forecast_budget(items, months_ahead=3)
        assert len(forecasts) == 3  # One per category
        for f in forecasts:
            assert "Forecast" in f.description

    def test_forecast_budget_empty(self):
        forecasts = BudgetEngine.forecast_budget([], months_ahead=3)
        assert forecasts == []

    def test_forecast_budget_zero_months(self):
        items = [BudgetItem(**i) for i in self._sample_items()]
        forecasts = BudgetEngine.forecast_budget(items, months_ahead=0)
        assert forecasts == []
