"""Tests for RFI Pydantic models."""

from datetime import date

import pytest
from pydantic import ValidationError

from tools.models.rfi_models import (
    AMS_TEMPLATES,
    DATA_QUALITY_MAX,
    DATA_QUALITY_MIN,
    REQUIRED_COMPLETENESS_THRESHOLD,
    REQUIRED_FIELDS,
    CMMSType,
    CompanySiteProfile,
    CriticalityMethodRFI,
    DataAvailabilityChecklist,
    DataAvailabilityItem,
    DataFormat,
    EquipmentHierarchyData,
    Industry,
    KPIBaselineTargets,
    Language,
    MaintenanceCurrentState,
    OrgStructure,
    OrganizationResources,
    RFISubmission,
    RFIValidationSummary,
    SAPVersion,
    ScopeTimeline,
    ScopeType,
    StandardsCompliance,
    StrategyMaturity,
    WorkshopFormat,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_completeness_threshold(self):
        assert 0 < REQUIRED_COMPLETENESS_THRESHOLD <= 1.0

    def test_ams_templates_count(self):
        assert len(AMS_TEMPLATES) == 14

    def test_ams_templates_ids_unique(self):
        ids = [t[0] for t in AMS_TEMPLATES]
        assert len(ids) == len(set(ids))

    def test_ams_templates_sequential(self):
        for i, (tid, _name) in enumerate(AMS_TEMPLATES, start=1):
            assert tid.startswith(f"{i:02d}_")

    def test_required_fields_keys(self):
        expected_keys = {
            "company_site", "equipment_hierarchy", "maintenance_state",
            "organization", "standards", "kpi_baseline", "scope_timeline",
            "data_availability",
        }
        assert set(REQUIRED_FIELDS.keys()) == expected_keys


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TestEnums:
    def test_industry_values(self):
        assert Industry.MINING.value == "mining"
        assert Industry.OIL_GAS.value == "oil-gas"

    def test_strategy_maturity_values(self):
        assert StrategyMaturity.REACTIVE.value == "reactive"
        assert StrategyMaturity.OPTIMIZED.value == "optimized"

    def test_cmms_type_values(self):
        assert CMMSType.SAP_PM.value == "sap-pm"
        assert CMMSType.NONE.value == "none"

    def test_sap_version_values(self):
        assert SAPVersion.S4HANA.value == "S/4HANA"

    def test_language_values(self):
        assert Language.FR.value == "fr"
        assert Language.EN.value == "en"


# ---------------------------------------------------------------------------
# Sheet models
# ---------------------------------------------------------------------------

class TestCompanySiteProfile:
    def test_defaults(self):
        profile = CompanySiteProfile()
        assert profile.company_name == ""
        assert profile.industry is None
        assert profile.primary_language is None

    def test_full_valid(self):
        profile = CompanySiteProfile(
            company_name="OCP Group",
            industry=Industry.MINING,
            plant_name="Jorf Fertilizer Complex",
            plant_code="OCP-JFC",
            location="El Jadida, Morocco",
            country="MA",
            primary_language=Language.FR,
            contact_name="John Doe",
            contact_email="john@ocp.ma",
        )
        assert profile.company_name == "OCP Group"
        assert profile.industry == Industry.MINING

    def test_name_max_length(self):
        long_name = "A" * 201
        with pytest.raises(ValidationError):
            CompanySiteProfile(company_name=long_name)


class TestEquipmentHierarchyData:
    def test_defaults(self):
        data = EquipmentHierarchyData()
        assert data.equipment_list_available is None
        assert data.estimated_equipment_count is None

    def test_negative_count_rejected(self):
        with pytest.raises(ValidationError):
            EquipmentHierarchyData(estimated_equipment_count=-1)

    def test_hierarchy_levels_range(self):
        valid = EquipmentHierarchyData(hierarchy_levels=6)
        assert valid.hierarchy_levels == 6

        with pytest.raises(ValidationError):
            EquipmentHierarchyData(hierarchy_levels=0)

        with pytest.raises(ValidationError):
            EquipmentHierarchyData(hierarchy_levels=11)


class TestMaintenanceCurrentState:
    def test_defaults_all_none(self):
        state = MaintenanceCurrentState()
        assert state.strategy_maturity is None
        assert state.cmms_type is None
        assert state.wo_history_years is None

    def test_wo_history_years_range(self):
        valid = MaintenanceCurrentState(wo_history_years=10)
        assert valid.wo_history_years == 10

        with pytest.raises(ValidationError):
            MaintenanceCurrentState(wo_history_years=-1)

        with pytest.raises(ValidationError):
            MaintenanceCurrentState(wo_history_years=51)


class TestOrganizationResources:
    def test_defaults(self):
        org = OrganizationResources()
        assert org.team_size is None
        assert org.trades == []

    def test_trades_list(self):
        org = OrganizationResources(trades=["mechanical", "electrical"])
        assert len(org.trades) == 2

    def test_shifts_max(self):
        with pytest.raises(ValidationError):
            OrganizationResources(shifts=5)


class TestKPIBaselineTargets:
    def test_defaults(self):
        kpi = KPIBaselineTargets()
        assert kpi.current_availability is None
        assert kpi.target_availability is None

    def test_valid_boundaries(self):
        kpi = KPIBaselineTargets(
            current_availability=0.0,
            target_availability=100.0,
        )
        assert kpi.current_availability == 0.0
        assert kpi.target_availability == 100.0

    def test_availability_over_100(self):
        with pytest.raises(ValidationError):
            KPIBaselineTargets(current_availability=101.0)

    def test_negative_availability(self):
        with pytest.raises(ValidationError):
            KPIBaselineTargets(current_availability=-1.0)

    def test_mtbf_max(self):
        with pytest.raises(ValidationError):
            KPIBaselineTargets(current_mtbf_hours=100_001)


class TestScopeTimeline:
    def test_defaults(self):
        st = ScopeTimeline()
        assert st.scope_type is None
        assert st.areas_in_scope == []

    def test_valid_dates(self):
        st = ScopeTimeline(
            start_date=date(2026, 1, 1),
            target_completion=date(2026, 6, 30),
        )
        assert st.start_date == date(2026, 1, 1)

    def test_inverted_dates_rejected(self):
        with pytest.raises(ValidationError, match="target_completion"):
            ScopeTimeline(
                start_date=date(2026, 6, 30),
                target_completion=date(2026, 1, 1),
            )


class TestDataAvailabilityItem:
    def test_quality_score_range(self):
        valid = DataAvailabilityItem(
            template_id="01_equipment_hierarchy",
            template_name="Equipment Hierarchy",
            quality_score=3,
        )
        assert valid.quality_score == 3

    def test_quality_score_too_low(self):
        with pytest.raises(ValidationError):
            DataAvailabilityItem(
                template_id="01_equipment_hierarchy",
                template_name="Equipment Hierarchy",
                quality_score=0,
            )

    def test_quality_score_too_high(self):
        with pytest.raises(ValidationError):
            DataAvailabilityItem(
                template_id="01_equipment_hierarchy",
                template_name="Equipment Hierarchy",
                quality_score=6,
            )


class TestDataAvailabilityChecklist:
    def test_14_templates(self):
        items = [
            DataAvailabilityItem(template_id=tid, template_name=name)
            for tid, name in AMS_TEMPLATES
        ]
        checklist = DataAvailabilityChecklist(items=items)
        assert len(checklist.items) == 14


# ---------------------------------------------------------------------------
# Composite models
# ---------------------------------------------------------------------------

class TestRFISubmission:
    def test_default_creation(self):
        sub = RFISubmission()
        assert sub.company_site.company_name == ""
        assert sub.equipment_hierarchy.estimated_equipment_count is None
        assert sub.data_availability.items == []

    def test_full_creation(self):
        sub = RFISubmission(
            company_site=CompanySiteProfile(
                company_name="OCP", plant_name="JFC",
                industry=Industry.MINING, country="MA",
                primary_language=Language.FR,
            ),
            equipment_hierarchy=EquipmentHierarchyData(
                equipment_list_available=True,
                estimated_equipment_count=100,
            ),
            maintenance_state=MaintenanceCurrentState(
                strategy_maturity=StrategyMaturity.DEVELOPING,
                cmms_type=CMMSType.SAP_PM,
                sap_version=SAPVersion.S4HANA,
            ),
            organization=OrganizationResources(team_size=50, shifts=3),
            standards=StandardsCompliance(procedure_language=Language.FR),
            kpi_baseline=KPIBaselineTargets(target_availability=95.0),
            scope_timeline=ScopeTimeline(
                scope_type=ScopeType.SYSTEM,
                start_date=date(2026, 2, 1),
                target_completion=date(2026, 6, 30),
            ),
        )
        assert sub.company_site.company_name == "OCP"
        assert sub.maintenance_state.sap_version == SAPVersion.S4HANA


class TestRFIValidationSummary:
    def test_defaults(self):
        summary = RFIValidationSummary()
        assert summary.total_fields == 0
        assert summary.is_sufficient is False

    def test_sufficient(self):
        summary = RFIValidationSummary(
            total_fields=20,
            required_fields=14,
            filled_required=14,
            completeness_score=100.0,
            errors=0,
            warnings=0,
            is_sufficient=True,
        )
        assert summary.is_sufficient is True
