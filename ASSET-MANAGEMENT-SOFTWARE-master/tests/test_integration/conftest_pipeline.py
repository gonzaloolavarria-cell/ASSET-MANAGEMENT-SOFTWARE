"""
Shared pipeline fixtures for cross-milestone integration tests.
Provides a complete, cross-linked entity graph for M1-M4 testing.
"""

import uuid
from datetime import date, datetime

import pytest

from tools.models.schemas import (
    AllocatedTask,
    ApprovalStatus,
    BudgetItem,
    BudgetStatus,
    Cause,
    CriticalityAssessment,
    CriticalityCategory,
    CriticalityMethod,
    CriteriaScore,
    FailureConsequence,
    FailureEffect,
    FailureMode,
    FailurePattern,
    FailureType,
    FMStatus,
    FrequencyUnit,
    Function,
    FunctionType,
    FunctionalFailure,
    LabourResource,
    LabourSpecialty,
    LabourSummary,
    LabourSummaryEntry,
    MaintenanceTask,
    MaterialResource,
    Mechanism,
    NodeMetadata,
    NodeType,
    PlantHierarchyNode,
    RiskClass,
    ROIInput,
    StrategyType,
    TaskConstraint,
    TaskType,
    UnitOfMeasure,
    WPConstraint,
    WPType,
    WorkPackage,
    WPApprovalStatus,
    BudgetType,
    FinancialCategory,
    CurrencyCode,
)


# ============================================================
# FIXED IDS for cross-entity referencing
# ============================================================
PLANT_ID = str(uuid.uuid4())
AREA_ID = str(uuid.uuid4())
SYSTEM_ID = str(uuid.uuid4())
EQUIP_ID = str(uuid.uuid4())
SUBASSY_ID = str(uuid.uuid4())
MI_ID = str(uuid.uuid4())

FUNC_PRIMARY_ID = str(uuid.uuid4())
FUNC_SECONDARY_ID = str(uuid.uuid4())
FUNC_PROTECTIVE_ID = str(uuid.uuid4())

FF_TOTAL_ID = str(uuid.uuid4())
FF_PARTIAL_1_ID = str(uuid.uuid4())
FF_PARTIAL_2_ID = str(uuid.uuid4())


@pytest.fixture
def pipeline_hierarchy_nodes():
    """6 nodes: Plant -> Area -> System -> Equipment -> SubAssembly -> MI."""
    return [
        PlantHierarchyNode(
            node_id=PLANT_ID, node_type=NodeType.PLANT,
            name="Jorf Fertilizer Complex", name_fr="Complexe Jorf",
            code="OCP-JFC1", level=1,
        ),
        PlantHierarchyNode(
            node_id=AREA_ID, node_type=NodeType.AREA,
            name="Grinding Area", name_fr="Zone de broyage",
            code="JFC1-BRY", parent_node_id=PLANT_ID, level=2,
        ),
        PlantHierarchyNode(
            node_id=SYSTEM_ID, node_type=NodeType.SYSTEM,
            name="SAG Mill System", name_fr="Systeme Broyeur SAG",
            code="JFC1-BRY-SAG", parent_node_id=AREA_ID, level=3,
        ),
        PlantHierarchyNode(
            node_id=EQUIP_ID, node_type=NodeType.EQUIPMENT,
            name="SAG Mill #1", name_fr="Broyeur SAG #1",
            code="BRY-SAG-ML-001", parent_node_id=SYSTEM_ID, level=4,
            tag="BRY-SAG-ML-001",
            metadata=NodeMetadata(manufacturer="FLSmidth", model="SAG 12x6",
                                  power_kw=8500.0, weight_kg=450000.0),
        ),
        PlantHierarchyNode(
            node_id=SUBASSY_ID, node_type=NodeType.SUB_ASSEMBLY,
            name="Drive System", name_fr="Systeme d'entrainement",
            code="BRY-SAG-ML-001-DRV", parent_node_id=EQUIP_ID, level=5,
        ),
        PlantHierarchyNode(
            node_id=MI_ID, node_type=NodeType.MAINTAINABLE_ITEM,
            name="Drive Motor", name_fr="Moteur d'entrainement",
            code="BRY-SAG-ML-001-DRV-MOT", parent_node_id=SUBASSY_ID, level=6,
        ),
    ]


@pytest.fixture
def pipeline_criticality():
    """2 assessments with full 11-criteria scores."""
    return [
        CriticalityAssessment(
            node_id=EQUIP_ID,
            assessed_at=datetime(2026, 2, 20, 10, 0),
            assessed_by="reliability_agent",
            method=CriticalityMethod.FULL_MATRIX,
            criteria_scores=[
                CriteriaScore(category=CriticalityCategory.SAFETY, consequence_level=4),
                CriteriaScore(category=CriticalityCategory.HEALTH, consequence_level=3),
                CriteriaScore(category=CriticalityCategory.ENVIRONMENT, consequence_level=3),
                CriteriaScore(category=CriticalityCategory.PRODUCTION, consequence_level=5),
                CriteriaScore(category=CriticalityCategory.OPERATING_COST, consequence_level=4),
                CriteriaScore(category=CriticalityCategory.CAPITAL_COST, consequence_level=4),
                CriteriaScore(category=CriticalityCategory.SCHEDULE, consequence_level=3),
                CriteriaScore(category=CriticalityCategory.REVENUE, consequence_level=5),
                CriteriaScore(category=CriticalityCategory.COMMUNICATIONS, consequence_level=2),
                CriteriaScore(category=CriticalityCategory.COMPLIANCE, consequence_level=3),
                CriteriaScore(category=CriticalityCategory.REPUTATION, consequence_level=3),
            ],
            probability=4,
            risk_class=RiskClass.IV_CRITICAL,
        ),
        CriticalityAssessment(
            node_id=MI_ID,
            assessed_at=datetime(2026, 2, 20, 10, 30),
            assessed_by="reliability_agent",
            method=CriticalityMethod.FULL_MATRIX,
            criteria_scores=[
                CriteriaScore(category=CriticalityCategory.SAFETY, consequence_level=3),
                CriteriaScore(category=CriticalityCategory.HEALTH, consequence_level=2),
                CriteriaScore(category=CriticalityCategory.ENVIRONMENT, consequence_level=2),
                CriteriaScore(category=CriticalityCategory.PRODUCTION, consequence_level=4),
                CriteriaScore(category=CriticalityCategory.OPERATING_COST, consequence_level=3),
                CriteriaScore(category=CriticalityCategory.CAPITAL_COST, consequence_level=3),
                CriteriaScore(category=CriticalityCategory.SCHEDULE, consequence_level=2),
                CriteriaScore(category=CriticalityCategory.REVENUE, consequence_level=4),
                CriteriaScore(category=CriticalityCategory.COMMUNICATIONS, consequence_level=1),
                CriteriaScore(category=CriticalityCategory.COMPLIANCE, consequence_level=2),
                CriteriaScore(category=CriticalityCategory.REPUTATION, consequence_level=2),
            ],
            probability=3,
            risk_class=RiskClass.III_HIGH,
        ),
    ]


@pytest.fixture
def pipeline_fmeca():
    """3 functions, 3 functional failures, 6 failure modes (valid 72-combo pairs)."""
    functions = [
        Function(
            function_id=FUNC_PRIMARY_ID,
            node_id=MI_ID,
            function_type=FunctionType.PRIMARY,
            description="To drive SAG mill at minimum 8500 kW continuously",
            description_fr="Entrainer le broyeur SAG a minimum 8500 kW en continu",
            performance_standard="8500 kW, continuous, <80°C winding temp",
        ),
        Function(
            function_id=FUNC_SECONDARY_ID,
            node_id=MI_ID,
            function_type=FunctionType.SECONDARY,
            description="To maintain lubrication oil flow at 40 L/min",
            description_fr="Maintenir le debit d'huile de lubrification a 40 L/min",
        ),
        Function(
            function_id=FUNC_PROTECTIVE_ID,
            node_id=MI_ID,
            function_type=FunctionType.PROTECTIVE,
            description="To trip motor on high temperature above 90°C",
            description_fr="Declencher le moteur en cas de temperature elevee au-dessus de 90°C",
        ),
    ]
    failures = [
        FunctionalFailure(
            failure_id=FF_TOTAL_ID,
            function_id=FUNC_PRIMARY_ID,
            failure_type=FailureType.TOTAL,
            description="Motor fails to run (0 kW output)",
            description_fr="Le moteur ne tourne pas (puissance 0 kW)",
        ),
        FunctionalFailure(
            failure_id=FF_PARTIAL_1_ID,
            function_id=FUNC_PRIMARY_ID,
            failure_type=FailureType.PARTIAL,
            description="Motor runs below rated power (<8500 kW)",
            description_fr="Le moteur tourne en dessous de la puissance nominale",
        ),
        FunctionalFailure(
            failure_id=FF_PARTIAL_2_ID,
            function_id=FUNC_SECONDARY_ID,
            failure_type=FailureType.TOTAL,
            description="No oil flow to bearings",
            description_fr="Pas de debit d'huile vers les roulements",
        ),
    ]
    # Valid 72-combo pairs from MASTER
    failure_modes = [
        FailureMode(
            functional_failure_id=FF_TOTAL_ID,
            what="Bearing",
            mechanism=Mechanism.WEARS,
            cause=Cause.RELATIVE_MOVEMENT,
            failure_pattern=FailurePattern.B_AGE,
            failure_consequence=FailureConsequence.EVIDENT_OPERATIONAL,
            is_hidden=False,
            failure_effect=FailureEffect(
                evidence="High vibration on drive end",
                production_impact="Complete shutdown 600 t/hr lost",
                estimated_downtime_hours=48.0,
            ),
            strategy_type=StrategyType.CONDITION_BASED,
        ),
        FailureMode(
            functional_failure_id=FF_TOTAL_ID,
            what="Winding",
            mechanism=Mechanism.THERMALLY_OVERLOADS,
            cause=Cause.OVERCURRENT,
            failure_pattern=FailurePattern.C_FATIGUE,
            failure_consequence=FailureConsequence.EVIDENT_OPERATIONAL,
            is_hidden=False,
            failure_effect=FailureEffect(
                evidence="Insulation resistance drops below 1 MOhm",
                production_impact="Complete shutdown",
                estimated_downtime_hours=96.0,
            ),
            strategy_type=StrategyType.FIXED_TIME,
        ),
        FailureMode(
            functional_failure_id=FF_PARTIAL_1_ID,
            what="Coupling",
            mechanism=Mechanism.LOOSES_PRELOAD,
            cause=Cause.VIBRATION,
            failure_pattern=FailurePattern.E_RANDOM,
            failure_consequence=FailureConsequence.EVIDENT_OPERATIONAL,
            is_hidden=False,
            failure_effect=FailureEffect(
                evidence="Abnormal vibration at coupling",
                production_impact="Reduced power transfer",
                estimated_downtime_hours=8.0,
            ),
            strategy_type=StrategyType.CONDITION_BASED,
        ),
        FailureMode(
            functional_failure_id=FF_PARTIAL_1_ID,
            what="Stator",
            mechanism=Mechanism.DEGRADES,
            cause=Cause.CONTAMINATION,
            failure_pattern=FailurePattern.F_EARLY_LIFE,
            failure_consequence=FailureConsequence.EVIDENT_NONOPERATIONAL,
            is_hidden=False,
            failure_effect=FailureEffect(
                evidence="Motor current imbalance >5%",
                production_impact="Derated operation",
                estimated_downtime_hours=24.0,
            ),
            strategy_type=StrategyType.CONDITION_BASED,
        ),
        FailureMode(
            functional_failure_id=FF_PARTIAL_2_ID,
            what="Oil pump",
            mechanism=Mechanism.WEARS,
            cause=Cause.BREAKDOWN_OF_LUBRICATION,
            failure_pattern=FailurePattern.B_AGE,
            failure_consequence=FailureConsequence.EVIDENT_OPERATIONAL,
            is_hidden=False,
            failure_effect=FailureEffect(
                evidence="Oil level drops in reservoir",
                production_impact="Bearing damage risk",
                estimated_downtime_hours=12.0,
            ),
            strategy_type=StrategyType.FIXED_TIME,
        ),
        FailureMode(
            functional_failure_id=FF_PARTIAL_2_ID,
            what="Temperature sensor",
            mechanism=Mechanism.DRIFTS,
            cause=Cause.USE,
            failure_pattern=FailurePattern.E_RANDOM,
            failure_consequence=FailureConsequence.HIDDEN_SAFETY,
            is_hidden=True,
            failure_effect=FailureEffect(
                evidence="No alarm on high temperature condition",
                safety_threat="Undetected overheating may cause fire",
                estimated_downtime_hours=4.0,
            ),
            strategy_type=StrategyType.FAULT_FINDING,
        ),
    ]
    return {"functions": functions, "failures": failures, "failure_modes": failure_modes}


@pytest.fixture
def pipeline_tasks():
    """8 maintenance tasks: INSPECT*3, REPLACE*3, SERVICE*2. REPLACE tasks have materials (T-16)."""
    return [
        MaintenanceTask(
            name="Inspect bearing vibration",
            name_fr="Inspecter vibration roulement",
            task_type=TaskType.INSPECT,
            acceptable_limits="< 4.5 mm/s RMS",
            consequences="Bearing seizure, 48hr shutdown",
            constraint=TaskConstraint.ONLINE,
            access_time_hours=0.0,
            frequency_value=4,
            frequency_unit=FrequencyUnit.WEEKS,
            labour_resources=[
                LabourResource(specialty=LabourSpecialty.CONMON_SPECIALIST, quantity=1, hours_per_person=0.5),
            ],
        ),
        MaintenanceTask(
            name="Inspect winding insulation resistance",
            name_fr="Inspecter resistance isolement bobinage",
            task_type=TaskType.INSPECT,
            acceptable_limits="> 1 MOhm at 1kV DC",
            consequences="Winding burnout, 96hr shutdown",
            constraint=TaskConstraint.ONLINE,
            access_time_hours=0.0,
            frequency_value=13,
            frequency_unit=FrequencyUnit.WEEKS,
            labour_resources=[
                LabourResource(specialty=LabourSpecialty.ELECTRICIAN, quantity=1, hours_per_person=1.0),
            ],
        ),
        MaintenanceTask(
            name="Inspect coupling alignment",
            name_fr="Inspecter alignement accouplement",
            task_type=TaskType.INSPECT,
            acceptable_limits="< 0.05mm offset",
            consequences="Vibration damage",
            constraint=TaskConstraint.ONLINE,
            access_time_hours=0.0,
            frequency_value=4,
            frequency_unit=FrequencyUnit.WEEKS,
            labour_resources=[
                LabourResource(specialty=LabourSpecialty.CONMON_SPECIALIST, quantity=1, hours_per_person=0.5),
            ],
        ),
        MaintenanceTask(
            name="Replace drive end bearing",
            name_fr="Remplacer roulement cote entrainement",
            task_type=TaskType.REPLACE,
            is_secondary=True,
            consequences="Shaft damage risk",
            constraint=TaskConstraint.OFFLINE,
            access_time_hours=2.0,
            frequency_value=52,
            frequency_unit=FrequencyUnit.WEEKS,
            budget_type=BudgetType.REPLACE,
            budgeted_life=18000.0,
            labour_resources=[
                LabourResource(specialty=LabourSpecialty.FITTER, quantity=2, hours_per_person=8.0),
            ],
            material_resources=[
                MaterialResource(description="Spherical roller bearing 22340", stock_code="MAT-BRG-22340",
                                 quantity=1, unit_of_measure=UnitOfMeasure.EA, unit_price=12500.0),
            ],
        ),
        MaintenanceTask(
            name="Replace oil pump seals",
            name_fr="Remplacer joints pompe huile",
            task_type=TaskType.REPLACE,
            consequences="Oil leakage, bearing damage",
            constraint=TaskConstraint.OFFLINE,
            access_time_hours=1.0,
            frequency_value=26,
            frequency_unit=FrequencyUnit.WEEKS,
            labour_resources=[
                LabourResource(specialty=LabourSpecialty.FITTER, quantity=1, hours_per_person=4.0),
            ],
            material_resources=[
                MaterialResource(description="Oil pump seal kit", stock_code="MAT-SEAL-KIT-01",
                                 quantity=1, unit_of_measure=UnitOfMeasure.EA, unit_price=850.0),
            ],
        ),
        MaintenanceTask(
            name="Replace temperature sensor",
            name_fr="Remplacer capteur temperature",
            task_type=TaskType.REPLACE,
            consequences="Loss of protection function",
            constraint=TaskConstraint.OFFLINE,
            access_time_hours=0.5,
            frequency_value=52,
            frequency_unit=FrequencyUnit.WEEKS,
            labour_resources=[
                LabourResource(specialty=LabourSpecialty.INSTRUMENTIST, quantity=1, hours_per_person=2.0),
            ],
            material_resources=[
                MaterialResource(description="RTD sensor Pt100", stock_code="MAT-RTD-PT100",
                                 quantity=1, unit_of_measure=UnitOfMeasure.EA, unit_price=320.0),
            ],
        ),
        MaintenanceTask(
            name="Lubricate drive system bearings",
            name_fr="Lubrifier roulements systeme entrainement",
            task_type=TaskType.LUBRICATE,
            consequences="Accelerated bearing wear",
            constraint=TaskConstraint.ONLINE,
            access_time_hours=0.0,
            frequency_value=4,
            frequency_unit=FrequencyUnit.WEEKS,
            labour_resources=[
                LabourResource(specialty=LabourSpecialty.FITTER, quantity=1, hours_per_person=1.0),
            ],
        ),
        MaintenanceTask(
            name="Clean cooling fan filters",
            name_fr="Nettoyer filtres ventilateur refroidissement",
            task_type=TaskType.CLEAN,
            consequences="Motor overheating risk",
            constraint=TaskConstraint.ONLINE,
            access_time_hours=0.0,
            frequency_value=4,
            frequency_unit=FrequencyUnit.WEEKS,
            labour_resources=[
                LabourResource(specialty=LabourSpecialty.FITTER, quantity=1, hours_per_person=0.5),
            ],
        ),
    ]


@pytest.fixture
def pipeline_work_packages(pipeline_tasks):
    """3 WPs with allocated tasks, SAP-compatible codes (<=72 chars)."""
    tasks = pipeline_tasks
    return [
        WorkPackage(
            name="4W SAG CONMON INSP ON",
            code="WP-SAG-001",
            node_id=EQUIP_ID,
            frequency_value=4,
            frequency_unit=FrequencyUnit.WEEKS,
            constraint=WPConstraint.ONLINE,
            access_time_hours=0.0,
            work_package_type=WPType.STANDALONE,
            allocated_tasks=[
                AllocatedTask(task_id=tasks[0].task_id, order=1, operation_number=10),
                AllocatedTask(task_id=tasks[2].task_id, order=2, operation_number=20),
                AllocatedTask(task_id=tasks[6].task_id, order=3, operation_number=30),
                AllocatedTask(task_id=tasks[7].task_id, order=4, operation_number=40),
            ],
            labour_summary=LabourSummary(
                total_hours=2.5,
                by_specialty=[
                    LabourSummaryEntry(specialty="CONMON_SPECIALIST", hours=1.0, people=1),
                    LabourSummaryEntry(specialty="FITTER", hours=1.5, people=1),
                ],
            ),
        ),
        WorkPackage(
            name="13W SAG ELEC INSP ON",
            code="WP-SAG-002",
            node_id=EQUIP_ID,
            frequency_value=13,
            frequency_unit=FrequencyUnit.WEEKS,
            constraint=WPConstraint.ONLINE,
            access_time_hours=0.0,
            work_package_type=WPType.STANDALONE,
            allocated_tasks=[
                AllocatedTask(task_id=tasks[1].task_id, order=1, operation_number=10),
            ],
            labour_summary=LabourSummary(
                total_hours=1.0,
                by_specialty=[
                    LabourSummaryEntry(specialty="ELECTRICIAN", hours=1.0, people=1),
                ],
            ),
        ),
        WorkPackage(
            name="52W SAG OVERHAUL OFF",
            code="WP-SAG-003",
            node_id=EQUIP_ID,
            frequency_value=52,
            frequency_unit=FrequencyUnit.WEEKS,
            constraint=WPConstraint.OFFLINE,
            access_time_hours=2.0,
            work_package_type=WPType.SEQUENTIAL,
            allocated_tasks=[
                AllocatedTask(task_id=tasks[3].task_id, order=1, operation_number=10),
                AllocatedTask(task_id=tasks[4].task_id, order=2, operation_number=20),
                AllocatedTask(task_id=tasks[5].task_id, order=3, operation_number=30),
            ],
            labour_summary=LabourSummary(
                total_hours=22.0,
                by_specialty=[
                    LabourSummaryEntry(specialty="FITTER", hours=20.0, people=2),
                    LabourSummaryEntry(specialty="INSTRUMENT_TECH", hours=2.0, people=1),
                ],
            ),
        ),
    ]


@pytest.fixture
def pipeline_budget_items():
    """5 budget items across LABOR, MATERIALS, CONTRACTOR categories."""
    return [
        BudgetItem(
            plant_id="OCP-JFC1", equipment_id="BRY-SAG-ML-001",
            cost_center="CC-BRY-001",
            category=FinancialCategory.LABOR,
            description="Annual preventive maintenance labour",
            planned_amount=125000.0, actual_amount=118000.0,
            period_start=date(2026, 1, 1), period_end=date(2026, 12, 31),
            status=BudgetStatus.IN_EXECUTION,
        ),
        BudgetItem(
            plant_id="OCP-JFC1", equipment_id="BRY-SAG-ML-001",
            cost_center="CC-BRY-001",
            category=FinancialCategory.MATERIALS,
            description="Bearing and seal replacements",
            planned_amount=85000.0, actual_amount=92000.0,
            period_start=date(2026, 1, 1), period_end=date(2026, 12, 31),
            status=BudgetStatus.IN_EXECUTION,
        ),
        BudgetItem(
            plant_id="OCP-JFC1", equipment_id="BRY-SAG-ML-001",
            cost_center="CC-BRY-001",
            category=FinancialCategory.MATERIALS,
            description="Lubricants and consumables",
            planned_amount=15000.0, actual_amount=13500.0,
            period_start=date(2026, 1, 1), period_end=date(2026, 12, 31),
            status=BudgetStatus.IN_EXECUTION,
        ),
        BudgetItem(
            plant_id="OCP-JFC1", equipment_id="BRY-SAG-ML-001",
            cost_center="CC-BRY-001",
            category=FinancialCategory.EQUIPMENT_RENTAL,
            description="Vibration monitoring equipment rental",
            planned_amount=35000.0, actual_amount=35000.0,
            period_start=date(2026, 1, 1), period_end=date(2026, 12, 31),
            status=BudgetStatus.CLOSED,
        ),
        BudgetItem(
            plant_id="OCP-JFC1", equipment_id="BRY-SAG-ML-001",
            cost_center="CC-BRY-001",
            category=FinancialCategory.CONTRACTORS,
            description="Engineering support and supervision",
            planned_amount=45000.0, actual_amount=48000.0,
            period_start=date(2026, 1, 1), period_end=date(2026, 12, 31),
            status=BudgetStatus.IN_EXECUTION,
        ),
    ]


@pytest.fixture
def pipeline_roi_input():
    """Realistic phosphate mining ROI scenario."""
    return ROIInput(
        project_id="PRJ-SAG-CBM-2026",
        plant_id="OCP-JFC1",
        description="CBM implementation for SAG mill drive motor",
        investment_cost=180000.0,
        annual_avoided_downtime_hours=96.0,
        hourly_production_value=12000.0,
        annual_labor_savings_hours=240.0,
        labor_cost_per_hour=65.0,
        annual_material_savings=25000.0,
        annual_operating_cost_increase=15000.0,
        analysis_horizon_years=5,
        discount_rate=0.08,
    )


@pytest.fixture
def pipeline_session(pipeline_hierarchy_nodes, pipeline_criticality, pipeline_fmeca,
                     pipeline_tasks, pipeline_work_packages):
    """SessionState pre-populated with all entity types."""
    from agents.orchestration.session_state import SessionState

    session = SessionState(
        session_id="test-pipeline-session",
        equipment_tag="BRY-SAG-ML-001",
        plant_code="OCP-JFC1",
    )
    # M1 entities (use mode='json' for JSON-serializable output)
    session.write_entities("hierarchy_nodes",
                           [n.model_dump(mode="json") for n in pipeline_hierarchy_nodes], "reliability")
    session.write_entities("criticality_assessments",
                           [c.model_dump(mode="json") for c in pipeline_criticality], "reliability")
    # M2 entities
    session.write_entities("functions",
                           [f.model_dump(mode="json") for f in pipeline_fmeca["functions"]], "reliability")
    session.write_entities("functional_failures",
                           [ff.model_dump(mode="json") for ff in pipeline_fmeca["failures"]], "reliability")
    session.write_entities("failure_modes",
                           [fm.model_dump(mode="json") for fm in pipeline_fmeca["failure_modes"]], "reliability")
    # M3 entities
    session.write_entities("maintenance_tasks",
                           [t.model_dump(mode="json") for t in pipeline_tasks], "planning")
    session.write_entities("work_packages",
                           [wp.model_dump(mode="json") for wp in pipeline_work_packages], "planning")
    return session
