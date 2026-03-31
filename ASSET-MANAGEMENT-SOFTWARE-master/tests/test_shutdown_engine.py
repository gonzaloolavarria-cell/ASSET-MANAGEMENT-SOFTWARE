"""Tests for Shutdown Execution Tracking Engine — Phase 5 + GAP-W14."""

import pytest
from datetime import date, datetime, timedelta

from tools.engines.shutdown_engine import ShutdownEngine
from tools.models.schemas import (
    ShiftType,
    ShutdownReportType,
    ShutdownSchedule,
    ShutdownStatus,
    ShutdownWorkOrderStatus,
)


def _make_shutdown(hours=48):
    start = datetime(2025, 6, 1, 6, 0, 0)
    end = start + timedelta(hours=hours)
    return ShutdownEngine.create_shutdown(
        "P1", "Major Turnaround", start, end, ["WO-001", "WO-002", "WO-003"],
    )


class TestCreateShutdown:

    def test_creates_planned(self):
        event = _make_shutdown()
        assert event.status == ShutdownStatus.PLANNED
        assert event.planned_hours == 48.0
        assert len(event.work_orders) == 3

    def test_zero_duration(self):
        start = datetime(2025, 6, 1, 6, 0, 0)
        event = ShutdownEngine.create_shutdown("P1", "Quick", start, start, ["WO-001"])
        assert event.planned_hours == 0.0


class TestStartShutdown:

    def test_planned_to_in_progress(self):
        event = _make_shutdown()
        event, msg = ShutdownEngine.start_shutdown(event)
        assert event.status == ShutdownStatus.IN_PROGRESS
        assert event.actual_start is not None
        assert "started" in msg

    def test_cannot_start_completed(self):
        event = _make_shutdown()
        event, _ = ShutdownEngine.start_shutdown(event)
        event, _ = ShutdownEngine.complete_shutdown(event)
        event, msg = ShutdownEngine.start_shutdown(event)
        assert event.status == ShutdownStatus.COMPLETED
        assert "Cannot" in msg


class TestUpdateProgress:

    def test_partial_completion(self):
        event = _make_shutdown()
        event, _ = ShutdownEngine.start_shutdown(event)
        event = ShutdownEngine.update_progress(event, ["WO-001", "WO-002"])
        assert event.completion_pct == pytest.approx(66.7, abs=0.1)

    def test_delay_tracking(self):
        event = _make_shutdown()
        event, _ = ShutdownEngine.start_shutdown(event)
        event = ShutdownEngine.update_progress(event, [], delay_hours=4.0, delay_reasons=["Material delay"])
        assert event.delay_hours == 4.0
        assert "Material delay" in event.delay_reasons


class TestCompleteShutdown:

    def test_in_progress_to_completed(self):
        event = _make_shutdown()
        event, _ = ShutdownEngine.start_shutdown(event)
        event, msg = ShutdownEngine.complete_shutdown(event)
        assert event.status == ShutdownStatus.COMPLETED
        assert event.actual_end is not None
        assert "completed" in msg


class TestCancelShutdown:

    def test_planned_to_cancelled(self):
        event = _make_shutdown()
        event, msg = ShutdownEngine.cancel_shutdown(event)
        assert event.status == ShutdownStatus.CANCELLED
        assert "cancelled" in msg

    def test_cannot_cancel_in_progress(self):
        event = _make_shutdown()
        event, _ = ShutdownEngine.start_shutdown(event)
        event, msg = ShutdownEngine.cancel_shutdown(event)
        assert event.status == ShutdownStatus.IN_PROGRESS
        assert "Cannot" in msg


class TestMetrics:

    def test_schedule_compliance(self):
        event = _make_shutdown()
        event, _ = ShutdownEngine.start_shutdown(event)
        event = ShutdownEngine.update_progress(event, ["WO-001", "WO-002", "WO-003"])
        metrics = ShutdownEngine.calculate_metrics(event)
        assert metrics.scope_completion_pct == 100.0
        assert metrics.schedule_compliance_pct > 0

    def test_total_delays(self):
        event = _make_shutdown()
        event, _ = ShutdownEngine.start_shutdown(event)
        event = ShutdownEngine.update_progress(event, [], delay_hours=8.0)
        metrics = ShutdownEngine.calculate_metrics(event)
        assert metrics.total_delays_hours == 8.0


# ── GAP-W14: Daily Report Tests ─────────────────────────────────────


def _make_in_progress_event():
    """Helper: create an IN_PROGRESS event with some completed WOs."""
    event = _make_shutdown()
    event, _ = ShutdownEngine.start_shutdown(event)
    event.actual_hours = 12.0  # simulate 12h elapsed
    event = ShutdownEngine.update_progress(event, ["WO-001"])
    event.actual_hours = 12.0  # fix since update_progress recalculates
    return event


class TestGenerateDailyReport:

    def test_daily_report_calculates_pending_wos(self):
        event = _make_in_progress_event()
        report = ShutdownEngine.generate_daily_report(
            event, date(2025, 6, 2), completed_today=["WO-001"],
        )
        assert "WO-002" in report.pending_work_orders
        assert "WO-003" in report.pending_work_orders
        assert "WO-001" not in report.pending_work_orders
        assert report.total_work_orders == 3

    def test_daily_report_includes_blockers(self):
        event = _make_in_progress_event()
        blocked = [
            ShutdownWorkOrderStatus(
                work_order_id="WO-002", status="BLOCKED", blocker="Waiting for crane",
            ),
        ]
        report = ShutdownEngine.generate_daily_report(
            event, date(2025, 6, 2), completed_today=["WO-001"], blocked_wos=blocked,
        )
        assert len(report.blocked_work_orders) == 1
        assert "Waiting for crane" in report.unresolved_blockers

    def test_daily_report_metrics_snapshot(self):
        event = _make_in_progress_event()
        report = ShutdownEngine.generate_daily_report(
            event, date(2025, 6, 2), completed_today=["WO-001"],
        )
        assert report.completion_pct == pytest.approx(33.3, abs=0.1)
        assert report.actual_hours_elapsed == 12.0
        assert report.report_type == ShutdownReportType.DAILY_PROGRESS

    def test_daily_report_delay_tracking(self):
        event = _make_in_progress_event()
        event.delay_hours = 5.0  # cumulative from before
        report = ShutdownEngine.generate_daily_report(
            event, date(2025, 6, 2), completed_today=[],
            delay_hours_today=3.0, delay_reasons_today=["Rain"],
        )
        assert report.delay_hours_today == 3.0
        assert report.delay_hours_cumulative == 5.0
        assert "Rain" in report.delay_reasons_today

    def test_daily_report_generates_sections(self):
        event = _make_in_progress_event()
        report = ShutdownEngine.generate_daily_report(
            event, date(2025, 6, 2), completed_today=["WO-001"],
        )
        titles = [s.title for s in report.sections]
        assert "Progress Summary" in titles
        assert "Completed Today" in titles
        assert "Pending Work" in titles
        assert "Blockers" in titles
        assert "Delays" in titles

    def test_daily_report_on_planned_event(self):
        event = _make_shutdown()  # still PLANNED
        report = ShutdownEngine.generate_daily_report(
            event, date(2025, 6, 1), completed_today=[],
        )
        assert report.completion_pct == 0.0
        assert len(report.pending_work_orders) == 3


# ── GAP-W14: Shift Report Tests ─────────────────────────────────────


class TestGenerateShiftReport:

    def test_shift_report_has_shift_field(self):
        event = _make_in_progress_event()
        report = ShutdownEngine.generate_shift_report(
            event, date(2025, 6, 2), ShiftType.MORNING, completed_this_shift=["WO-001"],
        )
        assert report.shift == ShiftType.MORNING

    def test_shift_report_type_is_shift_end(self):
        event = _make_in_progress_event()
        report = ShutdownEngine.generate_shift_report(
            event, date(2025, 6, 2), ShiftType.AFTERNOON, completed_this_shift=[],
        )
        assert report.report_type == ShutdownReportType.SHIFT_END

    def test_shift_report_completed_this_shift(self):
        event = _make_in_progress_event()
        report = ShutdownEngine.generate_shift_report(
            event, date(2025, 6, 2), ShiftType.NIGHT, completed_this_shift=["WO-001"],
        )
        assert report.completed_today == ["WO-001"]


# ── GAP-W14: Final Summary Tests ────────────────────────────────────


class TestGenerateFinalSummary:

    def test_final_summary_on_completed_event(self):
        event = _make_in_progress_event()
        event = ShutdownEngine.update_progress(event, ["WO-001", "WO-002", "WO-003"])
        event, _ = ShutdownEngine.complete_shutdown(event)
        report = ShutdownEngine.generate_final_summary(event)
        assert report.completion_pct == 100.0
        assert report.schedule_compliance_pct > 0

    def test_final_summary_type_is_final(self):
        event = _make_in_progress_event()
        event, _ = ShutdownEngine.complete_shutdown(event)
        report = ShutdownEngine.generate_final_summary(event)
        assert report.report_type == ShutdownReportType.FINAL_SUMMARY

    def test_final_summary_all_sections_present(self):
        event = _make_in_progress_event()
        event, _ = ShutdownEngine.complete_shutdown(event)
        report = ShutdownEngine.generate_final_summary(event)
        titles = [s.title for s in report.sections]
        assert "Final Metrics" in titles
        assert "Delay Analysis" in titles
        assert "Scope Analysis" in titles
        assert "Duration Analysis" in titles


# ── GAP-W14: Shift Suggestion Tests ─────────────────────────────────


class TestSuggestNextShiftFocus:

    def test_suggest_prioritizes_critical_path(self):
        event = _make_in_progress_event()
        schedule = ShutdownSchedule(
            shutdown_id=event.shutdown_id,
            items=[],
            critical_path_items=["WO-002", "WO-003"],
        )
        suggestion = ShutdownEngine.suggest_next_shift_focus(
            event, date(2025, 6, 2), ShiftType.MORNING, schedule=schedule,
        )
        # WO-002 and WO-003 are pending and on critical path
        assert suggestion.priority_work_orders[0] == "WO-002"
        assert suggestion.priority_work_orders[1] == "WO-003"

    def test_suggest_without_schedule_returns_pending(self):
        event = _make_in_progress_event()
        suggestion = ShutdownEngine.suggest_next_shift_focus(
            event, date(2025, 6, 2), ShiftType.MORNING,
        )
        assert "WO-002" in suggestion.priority_work_orders
        assert "WO-003" in suggestion.priority_work_orders

    def test_suggest_includes_unblocked_items(self):
        event = _make_in_progress_event()
        suggestion = ShutdownEngine.suggest_next_shift_focus(
            event, date(2025, 6, 2), ShiftType.MORNING,
            blockers_resolved=["crane_available"],
            blockers_pending=["WO-003"],
        )
        # WO-002 is unblocked (not in blockers_pending), WO-003 is blocked
        unblocked_idx = suggestion.priority_work_orders.index("WO-002")
        blocked_idx = suggestion.priority_work_orders.index("WO-003")
        assert unblocked_idx < blocked_idx

    def test_suggest_calculates_projected_completion(self):
        event = _make_in_progress_event()
        # 1 WO completed in 12 hours → velocity ~0.083 WO/h
        suggestion = ShutdownEngine.suggest_next_shift_focus(
            event, date(2025, 6, 2), ShiftType.MORNING,
        )
        assert suggestion.estimated_completion_if_on_track >= event.completion_pct

    def test_suggest_includes_safety_reminders(self):
        event = _make_in_progress_event()
        suggestion = ShutdownEngine.suggest_next_shift_focus(
            event, date(2025, 6, 2), ShiftType.MORNING,
        )
        assert len(suggestion.safety_reminders) >= 2
        assert any("LOTO" in r for r in suggestion.safety_reminders)


# ── GAP-W14: Schedule Generation Tests ──────────────────────────────


class TestGenerateShutdownSchedule:

    def test_schedule_no_dependencies(self):
        event = _make_shutdown()
        details = [
            {"work_order_id": "WO-001", "name": "Task A", "duration_hours": 4.0, "dependencies": [], "specialties": ["mech"], "area": "SAG"},
            {"work_order_id": "WO-002", "name": "Task B", "duration_hours": 3.0, "dependencies": [], "specialties": ["elec"], "area": "SAG"},
        ]
        schedule = ShutdownEngine.generate_shutdown_schedule(event, details)
        # All start at offset 0 since no deps
        for item in schedule.items:
            assert item.start_offset_hours == 0.0

    def test_schedule_serial_dependencies(self):
        event = _make_shutdown()
        details = [
            {"work_order_id": "A", "name": "A", "duration_hours": 4.0, "dependencies": [], "specialties": [], "area": ""},
            {"work_order_id": "B", "name": "B", "duration_hours": 3.0, "dependencies": ["A"], "specialties": [], "area": ""},
            {"work_order_id": "C", "name": "C", "duration_hours": 2.0, "dependencies": ["B"], "specialties": [], "area": ""},
        ]
        schedule = ShutdownEngine.generate_shutdown_schedule(event, details)
        items = {i.work_order_id: i for i in schedule.items}
        assert items["A"].start_offset_hours == 0.0
        assert items["B"].start_offset_hours == pytest.approx(4.0)
        assert items["C"].start_offset_hours == pytest.approx(7.0)

    def test_schedule_parallel_items(self):
        event = _make_shutdown()
        details = [
            {"work_order_id": "A", "name": "A", "duration_hours": 4.0, "dependencies": [], "specialties": [], "area": ""},
            {"work_order_id": "B", "name": "B", "duration_hours": 6.0, "dependencies": [], "specialties": [], "area": ""},
            {"work_order_id": "C", "name": "C", "duration_hours": 2.0, "dependencies": ["A", "B"], "specialties": [], "area": ""},
        ]
        schedule = ShutdownEngine.generate_shutdown_schedule(event, details)
        items = {i.work_order_id: i for i in schedule.items}
        # C depends on both A and B, B takes 6h
        assert items["C"].start_offset_hours == pytest.approx(6.0)

    def test_schedule_critical_path_identified(self):
        event = _make_shutdown()
        details = [
            {"work_order_id": "A", "name": "A", "duration_hours": 4.0, "dependencies": [], "specialties": [], "area": ""},
            {"work_order_id": "B", "name": "B", "duration_hours": 6.0, "dependencies": [], "specialties": [], "area": ""},
            {"work_order_id": "C", "name": "C", "duration_hours": 2.0, "dependencies": ["A", "B"], "specialties": [], "area": ""},
        ]
        schedule = ShutdownEngine.generate_shutdown_schedule(event, details)
        # Critical path: B → C (6+2=8, longer than A → C = 4+2=6)
        assert "B" in schedule.critical_path_items
        assert "C" in schedule.critical_path_items

    def test_schedule_critical_path_hours(self):
        event = _make_shutdown()
        details = [
            {"work_order_id": "A", "name": "A", "duration_hours": 4.0, "dependencies": [], "specialties": [], "area": ""},
            {"work_order_id": "B", "name": "B", "duration_hours": 6.0, "dependencies": [], "specialties": [], "area": ""},
            {"work_order_id": "C", "name": "C", "duration_hours": 2.0, "dependencies": ["B"], "specialties": [], "area": ""},
        ]
        schedule = ShutdownEngine.generate_shutdown_schedule(event, details)
        assert schedule.critical_path_hours == pytest.approx(8.0)

    def test_schedule_circular_dependency_raises(self):
        event = _make_shutdown()
        details = [
            {"work_order_id": "A", "name": "A", "duration_hours": 2.0, "dependencies": ["B"], "specialties": [], "area": ""},
            {"work_order_id": "B", "name": "B", "duration_hours": 3.0, "dependencies": ["A"], "specialties": [], "area": ""},
        ]
        with pytest.raises(ValueError, match="Circular dependency"):
            ShutdownEngine.generate_shutdown_schedule(event, details)

    def test_schedule_shift_count(self):
        event = _make_shutdown()
        details = [
            {"work_order_id": "A", "name": "A", "duration_hours": 20.0, "dependencies": [], "specialties": [], "area": ""},
        ]
        schedule = ShutdownEngine.generate_shutdown_schedule(event, details, shift_hours=8.0)
        assert schedule.shifts_required == 3  # ceil(20/8) = 3


# ── GAP-W14: Velocity Tests ─────────────────────────────────────────


class TestCalculateVelocity:

    def test_velocity_with_progress(self):
        event = _make_in_progress_event()  # 1 WO completed in 12h
        velocity = ShutdownEngine.calculate_velocity(event)
        assert velocity > 0
        assert velocity == pytest.approx(1 / 12, abs=0.01)

    def test_velocity_no_elapsed_time(self):
        event = _make_shutdown()
        velocity = ShutdownEngine.calculate_velocity(event)
        assert velocity == 0.0
