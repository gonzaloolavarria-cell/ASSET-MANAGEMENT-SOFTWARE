"""Tests for financial data models (GAP-W04)."""

import pytest
from datetime import date, datetime

from tools.models.schemas import (
    BudgetItem, BudgetSummary, ROIInput, ROIResult,
    FinancialImpact, FinancialSummary, BudgetVarianceAlert, ManHourSavingsReport,
    FinancialCategory, BudgetStatus, ROIStatus, CurrencyCode,
)


class TestFinancialEnums:
    """Verify financial enum definitions."""

    def test_financial_category_values(self):
        assert len(FinancialCategory) == 8
        assert FinancialCategory.LABOR.value == "LABOR"
        assert FinancialCategory.DOWNTIME_COST.value == "DOWNTIME_COST"

    def test_budget_status_values(self):
        assert len(BudgetStatus) == 4
        assert BudgetStatus.PLANNED.value == "PLANNED"

    def test_roi_status_values(self):
        assert len(ROIStatus) == 3
        assert ROIStatus.PROJECTED.value == "PROJECTED"
        assert ROIStatus.REALIZED.value == "REALIZED"

    def test_currency_code_values(self):
        assert CurrencyCode.USD.value == "USD"
        assert CurrencyCode.MAD.value == "MAD"
        assert CurrencyCode.EUR.value == "EUR"


class TestBudgetItemModel:
    """Verify BudgetItem serialization and validation."""

    def test_minimal_creation(self):
        item = BudgetItem(
            item_id="B1",
            plant_id="OCP-JFC",
            category=FinancialCategory.LABOR,
            description="Test",
            planned_amount=100000,
            actual_amount=95000,
        )
        assert item.item_id == "B1"
        assert item.category == FinancialCategory.LABOR

    def test_defaults(self):
        item = BudgetItem(
            item_id="B2", plant_id="P1", category="MATERIALS",
            description="Parts", planned_amount=50000, actual_amount=45000,
        )
        assert item.currency == CurrencyCode.USD
        assert item.status == BudgetStatus.PLANNED
        assert item.confidence >= 0

    def test_json_roundtrip(self):
        item = BudgetItem(
            item_id="B3", plant_id="P1", category="OVERHEAD",
            description="Admin", planned_amount=10000, actual_amount=12000,
        )
        data = item.model_dump()
        restored = BudgetItem(**data)
        assert restored.item_id == item.item_id
        assert restored.planned_amount == item.planned_amount


class TestROIInputModel:
    """Verify ROIInput validation."""

    def test_creation(self):
        inp = ROIInput(
            project_id="P1", plant_id="OCP-JFC",
            investment_cost=500000,
            annual_avoided_downtime_hours=200,
            hourly_production_value=5000,
            annual_labor_savings_hours=1000,
            annual_material_savings=100000,
        )
        assert inp.discount_rate == 0.08  # default
        assert inp.analysis_horizon_years == 5  # default
        assert inp.labor_cost_per_hour == 50  # default

    def test_json_roundtrip(self):
        inp = ROIInput(
            project_id="P1", plant_id="P1", investment_cost=100000,
            annual_avoided_downtime_hours=100, hourly_production_value=1000,
            annual_labor_savings_hours=500, annual_material_savings=50000,
        )
        data = inp.model_dump()
        restored = ROIInput(**data)
        assert restored.investment_cost == inp.investment_cost


class TestROIResultModel:
    """Verify ROIResult serialization."""

    def test_creation(self):
        result = ROIResult(
            project_id="P1", plant_id="OCP-JFC",
            investment_cost=500000, annual_gross_savings=1000000,
            annual_net_savings=950000, npv=3000000,
            payback_period_years=0.53, bcr=7.0, roi_pct=600.0,
            cumulative_savings_by_year=[400000, 1200000, 1900000],
            status=ROIStatus.PROJECTED,
            recommendation="Strong ROI",
        )
        assert result.npv == 3000000
        assert result.bcr == 7.0

    def test_optional_fields(self):
        result = ROIResult(
            project_id="P1", plant_id="P1",
            investment_cost=100000, annual_gross_savings=0,
            annual_net_savings=-50000, npv=-300000,
            bcr=0.0, roi_pct=-60.0,
            cumulative_savings_by_year=[],
            status=ROIStatus.PROJECTED,
            recommendation="Negative",
        )
        assert result.payback_period_years is None
        assert result.irr_pct is None


class TestFinancialImpactModel:
    """Verify FinancialImpact model."""

    def test_creation(self):
        impact = FinancialImpact(
            impact_id="FI-1", equipment_id="SAG-01",
            annual_failure_cost=150000, annual_pm_cost=60000,
            annual_downtime_hours=72, production_loss_per_hour=8000,
            annual_production_loss=576000, total_annual_impact=786000,
        )
        assert impact.total_annual_impact == 786000

    def test_defaults(self):
        impact = FinancialImpact(
            impact_id="FI-2", equipment_id="EQ-1",
            annual_failure_cost=0, annual_pm_cost=0,
            annual_downtime_hours=0, production_loss_per_hour=0,
            annual_production_loss=0, total_annual_impact=0,
        )
        assert impact.confidence == 0.7  # default
        assert impact.man_hours_saved == 0.0


class TestBudgetVarianceAlertModel:
    """Verify BudgetVarianceAlert model."""

    def test_creation(self):
        alert = BudgetVarianceAlert(
            alert_id="A1", plant_id="OCP-JFC",
            category=FinancialCategory.LABOR,
            planned=1000000, actual=1200000,
            variance_pct=20.0, severity="CRITICAL",
            message="LABOR is 20% over budget",
        )
        assert alert.severity == "CRITICAL"
        assert alert.threshold_pct == 10.0  # default


class TestManHourSavingsReport:
    """Verify ManHourSavingsReport model."""

    def test_creation(self):
        report = ManHourSavingsReport(
            plant_id="OCP-JFC",
            traditional_man_hours=450,
            ai_assisted_man_hours=150,
            hours_saved=300,
            savings_pct=66.7,
            cost_equivalent=15000,
            by_activity={"planning": 60, "fmeca": 140},
        )
        assert report.hours_saved == 300
        assert report.currency == CurrencyCode.USD
