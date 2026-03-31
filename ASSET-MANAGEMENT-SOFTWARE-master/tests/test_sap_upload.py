"""
Test Suite: SAP Upload Template Structure
Validates SAP export engine and cross-reference model.
Based on REF-03: Maintenance Item, Task List, Work Plan templates.
"""

import pytest

from tools.engines.sap_export_engine import SAPExportEngine
from tools.models.schemas import (
    AllocatedTask,
    FrequencyUnit,
    LabourSummary,
    SAPMaintenanceItem,
    SAPMaintenancePlan,
    SAPOperation,
    SAPTaskList,
    SAPUploadPackage,
    SchedulingTrigger,
    WPConstraint,
    WPType,
    WorkPackage,
)


# ============================================================
# SAP UPLOAD GENERATION
# ============================================================

class TestSAPUploadGeneration:
    def test_generate_single_wp(self, sample_work_package, sample_maintenance_task):
        """Generate SAP upload from a single work package."""
        task_map = {sample_maintenance_task.task_id: sample_maintenance_task}
        package = SAPExportEngine.generate_upload_package(
            [sample_work_package], "OCP-JFC1", tasks=task_map,
        )
        assert package.plant_code == "OCP-JFC1"
        assert len(package.maintenance_items) == 1
        assert len(package.task_lists) == 1
        assert package.maintenance_items[0].item_ref == "$MI1"
        assert package.task_lists[0].list_ref == "$TL1"
        # Verify task data was pulled into SAP operation
        op = package.task_lists[0].operations[0]
        assert "Inspect" in op.short_text
        assert op.duration_hours > 0

    def test_generate_multiple_wps(self):
        """Multiple work packages generate sequential $MI/$TL references."""
        wps = []
        for i in range(3):
            wp = WorkPackage(
                name=f"{(i+1)*4}W SAG MECH SERV OFF",
                code=f"WP-{i+1}", node_id="X",
                frequency_value=(i+1)*4,
                frequency_unit=FrequencyUnit.WEEKS,
                constraint=WPConstraint.OFFLINE, access_time_hours=2.0,
                work_package_type=WPType.STANDALONE,
                allocated_tasks=[
                    AllocatedTask(task_id=f"T{i}", order=1, operation_number=10),
                ],
                labour_summary=LabourSummary(total_hours=4.0),
            )
            wps.append(wp)

        # No task data provided — engine should use defaults
        package = SAPExportEngine.generate_upload_package(wps, "OCP-JFC1")
        assert len(package.maintenance_items) == 3
        assert package.maintenance_items[0].item_ref == "$MI1"
        assert package.maintenance_items[1].item_ref == "$MI2"
        assert package.maintenance_items[2].item_ref == "$MI3"
        assert package.task_lists[0].list_ref == "$TL1"
        assert package.task_lists[1].list_ref == "$TL2"
        assert package.task_lists[2].list_ref == "$TL3"

    def test_empty_wps_raises_error(self):
        """Must provide at least one work package."""
        with pytest.raises(ValueError, match="At least one"):
            SAPExportEngine.generate_upload_package([], "OCP-JFC1")

    def test_constraint_mapping(self):
        """Online → system_condition=1, Offline → system_condition=3."""
        online_wp = WorkPackage(
            name="4W SAG CONMON INSP ON",
            code="WP-ON", node_id="X",
            frequency_value=4, frequency_unit=FrequencyUnit.WEEKS,
            constraint=WPConstraint.ONLINE, access_time_hours=0,
            work_package_type=WPType.STANDALONE,
            allocated_tasks=[AllocatedTask(task_id="T1", order=1, operation_number=10)],
            labour_summary=LabourSummary(total_hours=1.0),
        )
        offline_wp = WorkPackage(
            name="12W SAG MECH SERV OFF",
            code="WP-OFF", node_id="X",
            frequency_value=12, frequency_unit=FrequencyUnit.WEEKS,
            constraint=WPConstraint.OFFLINE, access_time_hours=2.0,
            work_package_type=WPType.STANDALONE,
            allocated_tasks=[AllocatedTask(task_id="T2", order=1, operation_number=10)],
            labour_summary=LabourSummary(total_hours=8.0),
        )

        # No task data — engine uses defaults
        pkg_on = SAPExportEngine.generate_upload_package([online_wp], "X")
        pkg_off = SAPExportEngine.generate_upload_package([offline_wp], "X")
        assert pkg_on.task_lists[0].system_condition == 1   # Running
        assert pkg_off.task_lists[0].system_condition == 3  # Stopped

    def test_frequency_mapping(self):
        """Frequency unit maps to SAP cycle unit."""
        wp = WorkPackage(
            name="12W SAG MECH SERV OFF",
            code="WP-X", node_id="X",
            frequency_value=12, frequency_unit=FrequencyUnit.WEEKS,
            constraint=WPConstraint.OFFLINE, access_time_hours=2.0,
            work_package_type=WPType.STANDALONE,
            allocated_tasks=[AllocatedTask(task_id="T1", order=1, operation_number=10)],
            labour_summary=LabourSummary(total_hours=8.0),
        )
        # No task data — engine uses defaults
        package = SAPExportEngine.generate_upload_package([wp], "X")
        assert package.maintenance_plan.cycle_value == 12
        assert package.maintenance_plan.cycle_unit == "WK"


# ============================================================
# CROSS-REFERENCE VALIDATION
# ============================================================

class TestCrossReferenceValidation:
    def test_valid_cross_references(self):
        """Valid $MI/$TL links should pass."""
        package = SAPUploadPackage(
            plant_code="OCP-JFC1",
            maintenance_plan=SAPMaintenancePlan(
                plan_id="P1", description="X",
                cycle_value=28, cycle_unit="DAY",
                scheduling_period=14, scheduling_unit="DAY",
            ),
            maintenance_items=[
                SAPMaintenanceItem(
                    item_ref="$MI1", description="X", func_loc="X",
                    main_work_center="X", planner_group=1,
                    task_list_ref="$TL1", priority="4",
                ),
            ],
            task_lists=[
                SAPTaskList(
                    list_ref="$TL1", description="X", func_loc="X",
                    system_condition=1,
                    operations=[
                        SAPOperation(
                            operation_number=10, work_centre="X",
                            short_text="Inspect motor", duration_hours=0.5, num_workers=1,
                        ),
                    ],
                ),
            ],
        )
        errors = SAPExportEngine.validate_cross_references(package)
        assert len(errors) == 0

    def test_broken_cross_reference(self):
        """MI references TL that doesn't exist."""
        package = SAPUploadPackage(
            plant_code="OCP-JFC1",
            maintenance_plan=SAPMaintenancePlan(
                plan_id="P1", description="X",
                cycle_value=28, cycle_unit="DAY",
                scheduling_period=14, scheduling_unit="DAY",
            ),
            maintenance_items=[
                SAPMaintenanceItem(
                    item_ref="$MI1", description="X", func_loc="X",
                    main_work_center="X", planner_group=1,
                    task_list_ref="$TL99",  # Doesn't exist!
                    priority="4",
                ),
            ],
            task_lists=[
                SAPTaskList(
                    list_ref="$TL1", description="X", func_loc="X",
                    system_condition=1,
                    operations=[
                        SAPOperation(
                            operation_number=10, work_centre="X",
                            short_text="X", duration_hours=0.5, num_workers=1,
                        ),
                    ],
                ),
            ],
        )
        errors = SAPExportEngine.validate_cross_references(package)
        assert len(errors) >= 1
        assert "$TL99" in errors[0]

    def test_orphan_task_list(self):
        """Task list not referenced by any MI."""
        package = SAPUploadPackage(
            plant_code="OCP-JFC1",
            maintenance_plan=SAPMaintenancePlan(
                plan_id="P1", description="X",
                cycle_value=28, cycle_unit="DAY",
                scheduling_period=14, scheduling_unit="DAY",
            ),
            maintenance_items=[
                SAPMaintenanceItem(
                    item_ref="$MI1", description="X", func_loc="X",
                    main_work_center="X", planner_group=1,
                    task_list_ref="$TL1", priority="4",
                ),
            ],
            task_lists=[
                SAPTaskList(
                    list_ref="$TL1", description="X", func_loc="X",
                    system_condition=1,
                    operations=[SAPOperation(
                        operation_number=10, work_centre="X",
                        short_text="X", duration_hours=0.5, num_workers=1,
                    )],
                ),
                SAPTaskList(
                    list_ref="$TL2", description="Orphan", func_loc="X",
                    system_condition=1,
                    operations=[SAPOperation(
                        operation_number=10, work_centre="X",
                        short_text="X", duration_hours=0.5, num_workers=1,
                    )],
                ),
            ],
        )
        errors = SAPExportEngine.validate_cross_references(package)
        assert len(errors) >= 1
        assert "$TL2" in errors[0]


# ============================================================
# SAP FIELD LENGTH VALIDATION
# ============================================================

class TestSAPFieldLengths:
    def test_valid_field_lengths(self):
        package = SAPUploadPackage(
            plant_code="OCP-JFC1",
            maintenance_plan=SAPMaintenancePlan(
                plan_id="P1", description="X",
                cycle_value=28, cycle_unit="DAY",
                scheduling_period=14, scheduling_unit="DAY",
            ),
            maintenance_items=[],
            task_lists=[
                SAPTaskList(
                    list_ref="$TL1", description="X", func_loc="X",
                    system_condition=1,
                    operations=[
                        SAPOperation(
                            operation_number=10, work_centre="X",
                            short_text="Inspect drive bearing for vibration",
                            duration_hours=0.5, num_workers=1,
                        ),
                    ],
                ),
            ],
        )
        errors = SAPExportEngine.validate_sap_field_lengths(package)
        assert len(errors) == 0

    def test_operation_number_multiples_of_10(self):
        """SAP operations must be numbered 10, 20, 30..."""
        op = SAPOperation(
            operation_number=10, work_centre="X",
            short_text="Valid", duration_hours=1.0, num_workers=1,
        )
        assert op.operation_number == 10

    def test_call_horizon_default_50(self):
        """SAP default call horizon is 50%."""
        plan = SAPMaintenancePlan(
            plan_id="P1", description="X",
            cycle_value=28, cycle_unit="DAY",
            scheduling_period=14, scheduling_unit="DAY",
        )
        assert plan.call_horizon_pct == 50


# ============================================================
# COUNTER-BASED (USAGE) PLAN GENERATION (GAP-W08)
# ============================================================

def _make_wp(name: str, freq_val: float, freq_unit: FrequencyUnit) -> WorkPackage:
    """Helper to build a minimal WorkPackage for counter-plan tests."""
    return WorkPackage(
        name=name,
        code=f"WP-{name[:8]}",
        node_id="X",
        frequency_value=freq_val,
        frequency_unit=freq_unit,
        constraint=WPConstraint.OFFLINE,
        access_time_hours=72.0,
        work_package_type=WPType.STANDALONE,
        allocated_tasks=[AllocatedTask(task_id="T1", order=1, operation_number=10)],
        labour_summary=LabourSummary(total_hours=576.0),
        material_summary=[],
        sap_upload={"template_ref": ""},
    )


class TestCounterBasedPlanGeneration:
    """SAP export correctly handles operational frequency units (GAP-W08)."""

    def test_hours_run_generates_counter_plan(self):
        wp = _make_wp("8KH SAG LINER REPLACE OFF", 8000, FrequencyUnit.HOURS_RUN)
        package = SAPExportEngine.generate_upload_package([wp], "OCP-JFC1")
        plan = package.maintenance_plan
        assert plan.cycle_value == 8000
        assert plan.cycle_unit == "H"
        assert plan.scheduling_trigger == SchedulingTrigger.COUNTER

    def test_operating_hours_generates_counter_plan(self):
        wp = _make_wp("4KH PMP SEAL REPLACE OFF", 4000, FrequencyUnit.OPERATING_HOURS)
        package = SAPExportEngine.generate_upload_package([wp], "OCP-JFC1")
        assert package.maintenance_plan.scheduling_trigger == SchedulingTrigger.COUNTER
        assert package.maintenance_plan.cycle_unit == "H"

    def test_tonnes_generates_counter_plan(self):
        wp = _make_wp("500KT CVY BELT REPLACE OFF", 500000, FrequencyUnit.TONNES)
        package = SAPExportEngine.generate_upload_package([wp], "OCP-JFC1")
        plan = package.maintenance_plan
        assert plan.cycle_unit == "T"
        assert plan.scheduling_trigger == SchedulingTrigger.COUNTER

    def test_cycles_generates_counter_plan(self):
        wp = _make_wp("10KC VLV ACTUATE REPL OFF", 10000, FrequencyUnit.CYCLES)
        package = SAPExportEngine.generate_upload_package([wp], "OCP-JFC1")
        assert package.maintenance_plan.cycle_unit == "CYC"
        assert package.maintenance_plan.scheduling_trigger == SchedulingTrigger.COUNTER

    def test_weeks_generates_calendar_plan(self):
        """Backward compat: time-based units produce CALENDAR trigger."""
        wp = _make_wp("4W SAG INSP ONLINE", 4, FrequencyUnit.WEEKS)
        package = SAPExportEngine.generate_upload_package([wp], "OCP-JFC1")
        assert package.maintenance_plan.scheduling_trigger == SchedulingTrigger.CALENDAR
        assert package.maintenance_plan.cycle_unit == "WK"

    def test_counter_plan_missing_measuring_point_produces_error(self):
        wp = _make_wp("8KH SAG LINER REPLACE OFF", 8000, FrequencyUnit.HOURS_RUN)
        package = SAPExportEngine.generate_upload_package([wp], "OCP-JFC1")
        errors = SAPExportEngine.validate_sap_field_lengths(package)
        assert any("measuring_point" in e.lower() for e in errors)

    def test_counter_plan_with_measuring_point_passes(self):
        wp = _make_wp("8KH SAG LINER REPLACE OFF", 8000, FrequencyUnit.HOURS_RUN)
        package = SAPExportEngine.generate_upload_package([wp], "OCP-JFC1")
        package.maintenance_plan.measuring_point = "EQUI-SAG-HOURS-001"
        errors = SAPExportEngine.validate_sap_field_lengths(package)
        measuring_errors = [e for e in errors if "measuring_point" in e.lower()]
        assert len(measuring_errors) == 0

    def test_existing_time_based_still_works(self):
        """Existing calendar-based WP continues to work unchanged."""
        wp = _make_wp("12W SAG MECH SERV OFF", 12, FrequencyUnit.WEEKS)
        package = SAPExportEngine.generate_upload_package([wp], "X")
        assert package.maintenance_plan.cycle_value == 12
        assert package.maintenance_plan.cycle_unit == "WK"
