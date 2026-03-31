"""
Tests: Usage-Based Task Support (GAP-W08)
Verifies SchedulingTrigger enum, FREQ_UNIT_TRIGGER mapping,
and SAPMaintenancePlan counter-based fields.
"""

import pytest

from tools.models.schemas import (
    FREQ_UNIT_TRIGGER,
    FrequencyUnit,
    SAPMaintenancePlan,
    SchedulingTrigger,
)


class TestSchedulingTriggerEnum:
    def test_calendar_value(self):
        assert SchedulingTrigger.CALENDAR == "CALENDAR"

    def test_counter_value(self):
        assert SchedulingTrigger.COUNTER == "COUNTER"

    def test_exactly_two_members(self):
        assert len(SchedulingTrigger) == 2


class TestFreqUnitTriggerMapping:
    def test_all_frequency_units_have_trigger(self):
        """Every FrequencyUnit must map to a SchedulingTrigger."""
        for unit in FrequencyUnit:
            assert unit in FREQ_UNIT_TRIGGER, (
                f"FrequencyUnit.{unit.name} has no entry in FREQ_UNIT_TRIGGER"
            )

    def test_operational_units_are_counter(self):
        for unit in [
            FrequencyUnit.HOURS_RUN,
            FrequencyUnit.OPERATING_HOURS,
            FrequencyUnit.TONNES,
            FrequencyUnit.CYCLES,
        ]:
            assert FREQ_UNIT_TRIGGER[unit] == SchedulingTrigger.COUNTER

    def test_calendar_units_are_calendar(self):
        for unit in [
            FrequencyUnit.DAYS,
            FrequencyUnit.WEEKS,
            FrequencyUnit.MONTHS,
            FrequencyUnit.YEARS,
            FrequencyUnit.HOURS,  # generic hours → calendar (backward compat)
        ]:
            assert FREQ_UNIT_TRIGGER[unit] == SchedulingTrigger.CALENDAR


class TestSAPMaintenancePlanCounterFields:
    def test_backward_compat_no_new_required_fields(self):
        """Existing instantiation without new fields still works."""
        plan = SAPMaintenancePlan(
            plan_id="P1", description="Test Plan",
            cycle_value=28, cycle_unit="DAY",
            scheduling_period=14, scheduling_unit="DAY",
        )
        assert plan.scheduling_trigger is None
        assert plan.measuring_point is None

    def test_counter_plan_instantiation(self):
        plan = SAPMaintenancePlan(
            plan_id="P2", description="Liner Replace",
            cycle_value=8000, cycle_unit="H",
            scheduling_period=14, scheduling_unit="DAY",
            scheduling_trigger=SchedulingTrigger.COUNTER,
            measuring_point="EQUI-SAG-001",
        )
        assert plan.scheduling_trigger == SchedulingTrigger.COUNTER
        assert plan.measuring_point == "EQUI-SAG-001"

    def test_calendar_plan_no_measuring_point(self):
        plan = SAPMaintenancePlan(
            plan_id="P3", description="Weekly Inspection",
            cycle_value=4, cycle_unit="WK",
            scheduling_period=14, scheduling_unit="DAY",
            scheduling_trigger=SchedulingTrigger.CALENDAR,
        )
        assert plan.scheduling_trigger == SchedulingTrigger.CALENDAR
        assert plan.measuring_point is None
