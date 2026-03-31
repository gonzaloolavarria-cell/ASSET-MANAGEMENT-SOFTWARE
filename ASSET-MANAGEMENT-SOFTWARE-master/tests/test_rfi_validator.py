"""Tests for RFI validator."""

from datetime import date

import pytest

from tools.models.rfi_models import (
    AMS_TEMPLATES,
    REQUIRED_COMPLETENESS_THRESHOLD,
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
    OrganizationResources,
    RFISubmission,
    SAPVersion,
    ScopeTimeline,
    ScopeType,
    StandardsCompliance,
    StrategyMaturity,
)
from tools.validators.rfi_validator import RFIValidator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def empty_submission() -> RFISubmission:
    """Submission with all defaults (empty)."""
    return RFISubmission()


@pytest.fixture
def complete_submission() -> RFISubmission:
    """Fully filled submission with all required fields."""
    return RFISubmission(
        company_site=CompanySiteProfile(
            company_name="OCP Group",
            industry=Industry.MINING,
            plant_name="Jorf Fertilizer Complex",
            plant_code="OCP-JFC",
            location="El Jadida, Morocco",
            country="MA",
            primary_language=Language.FR,
            contact_name="John Doe",
            contact_email="john@ocp.ma",
        ),
        equipment_hierarchy=EquipmentHierarchyData(
            equipment_list_available=True,
            equipment_list_format=DataFormat.SAP_EXPORT,
            estimated_equipment_count=500,
            hierarchy_levels=6,
        ),
        maintenance_state=MaintenanceCurrentState(
            strategy_maturity=StrategyMaturity.DEVELOPING,
            cmms_type=CMMSType.SAP_PM,
            sap_version=SAPVersion.S4HANA,
            wo_history_available=True,
            wo_history_years=5,
        ),
        organization=OrganizationResources(
            team_size=50,
            shifts=3,
            trades=["mechanical", "electrical", "instrumentation"],
        ),
        standards=StandardsCompliance(
            procedure_language=Language.FR,
            iso_certifications=["ISO 55001"],
            lototo_program=True,
        ),
        kpi_baseline=KPIBaselineTargets(
            current_availability=85.0,
            target_availability=95.0,
        ),
        scope_timeline=ScopeTimeline(
            scope_type=ScopeType.SYSTEM,
            start_date=date(2026, 2, 1),
            target_completion=date(2026, 6, 30),
            areas_in_scope=["Phosphate Processing"],
        ),
        data_availability=DataAvailabilityChecklist(
            items=[
                DataAvailabilityItem(
                    template_id=tid, template_name=name, available=True,
                    data_format=DataFormat.EXCEL, quality_score=3,
                )
                for tid, name in AMS_TEMPLATES
            ],
        ),
    )


# ---------------------------------------------------------------------------
# Required fields
# ---------------------------------------------------------------------------

class TestRequiredFields:
    def test_all_required_present(self, complete_submission):
        results = RFIValidator.validate_required_fields(complete_submission)
        assert len(results) == 0

    def test_missing_company_name(self, complete_submission):
        complete_submission.company_site.company_name = ""
        results = RFIValidator.validate_required_fields(complete_submission)
        errors = [r for r in results if r.entity_id == "company_site.company_name"]
        assert len(errors) == 1
        assert errors[0].severity == "ERROR"

    def test_missing_industry(self, complete_submission):
        complete_submission.company_site.industry = None
        results = RFIValidator.validate_required_fields(complete_submission)
        errors = [r for r in results if r.entity_id == "company_site.industry"]
        assert len(errors) == 1

    def test_empty_submission_has_many_errors(self, empty_submission):
        results = RFIValidator.validate_required_fields(empty_submission)
        # All required fields should be flagged
        assert len(results) > 10

    def test_missing_scope_type(self, complete_submission):
        complete_submission.scope_timeline.scope_type = None
        results = RFIValidator.validate_required_fields(complete_submission)
        errors = [r for r in results if "scope_type" in r.entity_id]
        assert len(errors) == 1


# ---------------------------------------------------------------------------
# Coherence checks
# ---------------------------------------------------------------------------

class TestCoherence:
    def test_sap_without_version(self):
        sub = RFISubmission(
            maintenance_state=MaintenanceCurrentState(
                cmms_type=CMMSType.SAP_PM,
                sap_version=None,
            ),
        )
        results = RFIValidator.validate_coherence(sub)
        rfi_010 = [r for r in results if r.rule_id == "RFI-010"]
        assert len(rfi_010) == 1
        assert rfi_010[0].severity == "ERROR"

    def test_sap_with_version_ok(self):
        sub = RFISubmission(
            maintenance_state=MaintenanceCurrentState(
                cmms_type=CMMSType.SAP_PM,
                sap_version=SAPVersion.S4HANA,
            ),
        )
        results = RFIValidator.validate_coherence(sub)
        rfi_010 = [r for r in results if r.rule_id == "RFI-010"]
        assert len(rfi_010) == 0

    def test_non_sap_no_version_ok(self):
        sub = RFISubmission(
            maintenance_state=MaintenanceCurrentState(
                cmms_type=CMMSType.MAXIMO,
                sap_version=None,
            ),
        )
        results = RFIValidator.validate_coherence(sub)
        rfi_010 = [r for r in results if r.rule_id == "RFI-010"]
        assert len(rfi_010) == 0

    def test_wo_history_available_without_years(self):
        sub = RFISubmission(
            maintenance_state=MaintenanceCurrentState(
                wo_history_available=True,
                wo_history_years=None,
            ),
        )
        results = RFIValidator.validate_coherence(sub)
        rfi_011 = [r for r in results if r.rule_id == "RFI-011"]
        assert len(rfi_011) == 1

    def test_wo_history_not_available_no_warning(self):
        sub = RFISubmission(
            maintenance_state=MaintenanceCurrentState(
                wo_history_available=False,
            ),
        )
        results = RFIValidator.validate_coherence(sub)
        rfi_011 = [r for r in results if r.rule_id == "RFI-011"]
        assert len(rfi_011) == 0

    def test_criticality_without_method(self):
        sub = RFISubmission(
            maintenance_state=MaintenanceCurrentState(
                prior_criticality_assessment=True,
                criticality_method=None,
            ),
        )
        results = RFIValidator.validate_coherence(sub)
        rfi_012 = [r for r in results if r.rule_id == "RFI-012"]
        assert len(rfi_012) == 1

    def test_equipment_list_without_format(self):
        sub = RFISubmission(
            equipment_hierarchy=EquipmentHierarchyData(
                equipment_list_available=True,
                equipment_list_format=None,
            ),
        )
        results = RFIValidator.validate_coherence(sub)
        rfi_013 = [r for r in results if r.rule_id == "RFI-013"]
        assert len(rfi_013) == 1

    def test_bom_available_without_format(self):
        sub = RFISubmission(
            equipment_hierarchy=EquipmentHierarchyData(
                bom_available=True,
                bom_format=None,
            ),
        )
        results = RFIValidator.validate_coherence(sub)
        rfi_015 = [r for r in results if r.rule_id == "RFI-015"]
        assert len(rfi_015) == 1

    def test_complete_submission_no_coherence_issues(self, complete_submission):
        results = RFIValidator.validate_coherence(complete_submission)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# Numeric ranges
# ---------------------------------------------------------------------------

class TestNumericRanges:
    def test_target_below_current_availability(self):
        sub = RFISubmission(
            kpi_baseline=KPIBaselineTargets(
                current_availability=90.0,
                target_availability=80.0,
            ),
        )
        results = RFIValidator.validate_numeric_ranges(sub)
        rfi_021 = [r for r in results if r.rule_id == "RFI-021"]
        assert len(rfi_021) == 1
        assert rfi_021[0].severity == "WARNING"

    def test_target_above_current_ok(self):
        sub = RFISubmission(
            kpi_baseline=KPIBaselineTargets(
                current_availability=80.0,
                target_availability=95.0,
            ),
        )
        results = RFIValidator.validate_numeric_ranges(sub)
        rfi_021 = [r for r in results if r.rule_id == "RFI-021"]
        assert len(rfi_021) == 0

    def test_pm_compliance_target_below_current(self):
        sub = RFISubmission(
            kpi_baseline=KPIBaselineTargets(
                current_pm_compliance=80.0,
                target_pm_compliance=70.0,
            ),
        )
        results = RFIValidator.validate_numeric_ranges(sub)
        rfi_022 = [r for r in results if r.rule_id == "RFI-022"]
        assert len(rfi_022) == 1


# ---------------------------------------------------------------------------
# Completeness
# ---------------------------------------------------------------------------

class TestCompleteness:
    def test_100_percent(self, complete_submission):
        score, results = RFIValidator.calculate_completeness(complete_submission)
        assert score == 100.0
        assert any(r.rule_id == "RFI-050" for r in results)

    def test_0_percent(self, empty_submission):
        score, results = RFIValidator.calculate_completeness(empty_submission)
        assert score == 0.0

    def test_partial(self):
        sub = RFISubmission(
            company_site=CompanySiteProfile(
                company_name="Test",
                industry=Industry.MINING,
                plant_name="Plant",
                country="US",
                primary_language=Language.EN,
            ),
        )
        score, _ = RFIValidator.calculate_completeness(sub)
        assert 0 < score < 100


# ---------------------------------------------------------------------------
# Full validation
# ---------------------------------------------------------------------------

class TestFullValidation:
    def test_clean_submission(self, complete_submission):
        results = RFIValidator.run_full_validation(complete_submission)
        errors = [r for r in results if r.severity == "ERROR"]
        assert len(errors) == 0

    def test_empty_submission_has_threshold_warning(self, empty_submission):
        results = RFIValidator.run_full_validation(empty_submission)
        rfi_099 = [r for r in results if r.rule_id == "RFI-099"]
        assert len(rfi_099) == 1

    def test_multiple_issues(self):
        sub = RFISubmission(
            maintenance_state=MaintenanceCurrentState(
                cmms_type=CMMSType.SAP_PM,
                sap_version=None,  # coherence error
            ),
            kpi_baseline=KPIBaselineTargets(
                current_availability=90.0,
                target_availability=80.0,  # range warning
            ),
        )
        results = RFIValidator.run_full_validation(sub)
        # Should have required field errors + coherence error + range warning + completeness
        assert len(results) > 5
