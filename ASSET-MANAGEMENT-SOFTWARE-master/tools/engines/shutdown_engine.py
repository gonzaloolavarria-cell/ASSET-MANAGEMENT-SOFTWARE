"""Shutdown Execution Tracking Engine — Phase 5 + GAP-W14 Enhancement.

Tracks shutdown maintenance events, actual vs planned comparison,
delay tracking, completion metrics, daily/shift reporting,
shift-to-shift suggestions, and schedule generation.

Deterministic — no LLM required.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime

from tools.engines.state_machine import StateMachine
from tools.models.schemas import (
    ReportSection,
    ShiftType,
    ShutdownDailyReport,
    ShutdownEvent,
    ShutdownMetrics,
    ShutdownReportType,
    ShutdownSchedule,
    ShutdownScheduleItem,
    ShutdownShiftSuggestion,
    ShutdownStatus,
    ShutdownWorkOrderStatus,
)


class ShutdownEngine:
    """Manages shutdown execution lifecycle and metrics."""

    @staticmethod
    def create_shutdown(
        plant_id: str,
        name: str,
        planned_start: datetime,
        planned_end: datetime,
        work_orders: list[str],
    ) -> ShutdownEvent:
        """Create a PLANNED shutdown event."""
        planned_hours = max(0.0, (planned_end - planned_start).total_seconds() / 3600)
        return ShutdownEvent(
            plant_id=plant_id,
            name=name,
            planned_start=planned_start,
            planned_end=planned_end,
            planned_hours=round(planned_hours, 1),
            work_orders=work_orders,
        )

    @staticmethod
    def start_shutdown(event: ShutdownEvent) -> tuple[ShutdownEvent, str]:
        """Transition PLANNED → IN_PROGRESS."""
        try:
            StateMachine.validate_transition("shutdown", event.status.value, "IN_PROGRESS")
        except Exception as e:
            return event, f"Cannot start: {e}"

        event.status = ShutdownStatus.IN_PROGRESS
        event.actual_start = datetime.now()
        return event, "Shutdown started"

    @staticmethod
    def update_progress(
        event: ShutdownEvent,
        completed_wos: list[str],
        delay_hours: float = 0.0,
        delay_reasons: list[str] | None = None,
    ) -> ShutdownEvent:
        """Update shutdown progress with completed work orders and delays."""
        event.completed_work_orders = completed_wos
        total_wos = len(event.work_orders)
        completed_count = len([wo for wo in completed_wos if wo in event.work_orders])
        event.completion_pct = round((completed_count / total_wos * 100) if total_wos > 0 else 0.0, 1)

        if delay_hours > 0:
            event.delay_hours += delay_hours
        if delay_reasons:
            event.delay_reasons.extend(delay_reasons)

        if event.actual_start:
            elapsed = (datetime.now() - event.actual_start).total_seconds() / 3600
            event.actual_hours = round(elapsed, 1)

        return event

    @staticmethod
    def complete_shutdown(event: ShutdownEvent) -> tuple[ShutdownEvent, str]:
        """Transition IN_PROGRESS → COMPLETED."""
        try:
            StateMachine.validate_transition("shutdown", event.status.value, "COMPLETED")
        except Exception as e:
            return event, f"Cannot complete: {e}"

        event.status = ShutdownStatus.COMPLETED
        event.actual_end = datetime.now()
        if event.actual_start:
            event.actual_hours = round(
                (event.actual_end - event.actual_start).total_seconds() / 3600, 1
            )

        total_wos = len(event.work_orders)
        completed_count = len([wo for wo in event.completed_work_orders if wo in event.work_orders])
        event.completion_pct = round((completed_count / total_wos * 100) if total_wos > 0 else 100.0, 1)

        return event, "Shutdown completed"

    @staticmethod
    def cancel_shutdown(event: ShutdownEvent) -> tuple[ShutdownEvent, str]:
        """Transition PLANNED → CANCELLED."""
        try:
            StateMachine.validate_transition("shutdown", event.status.value, "CANCELLED")
        except Exception as e:
            return event, f"Cannot cancel: {e}"

        event.status = ShutdownStatus.CANCELLED
        return event, "Shutdown cancelled"

    @staticmethod
    def calculate_metrics(event: ShutdownEvent) -> ShutdownMetrics:
        """Calculate shutdown performance metrics."""
        planned_hours = event.planned_hours if event.planned_hours > 0 else 1.0
        actual_hours = event.actual_hours if event.actual_hours > 0 else planned_hours

        schedule_compliance = min(100.0, round((planned_hours / actual_hours) * 100, 1))
        planned_vs_actual = round(planned_hours / actual_hours, 2) if actual_hours > 0 else 1.0

        total_wos = len(event.work_orders)
        completed_count = len([wo for wo in event.completed_work_orders if wo in event.work_orders])
        scope_completion = round((completed_count / total_wos * 100) if total_wos > 0 else 0.0, 1)

        return ShutdownMetrics(
            shutdown_id=event.shutdown_id,
            schedule_compliance_pct=schedule_compliance,
            scope_completion_pct=scope_completion,
            planned_vs_actual_ratio=planned_vs_actual,
            total_delays_hours=event.delay_hours,
        )

    # ── GAP-W14: Daily / Shift / Final Reports ──────────────────────────

    @staticmethod
    def generate_daily_report(
        event: ShutdownEvent,
        report_date: date,
        completed_today: list[str],
        blocked_wos: list[ShutdownWorkOrderStatus] | None = None,
        delay_hours_today: float = 0.0,
        delay_reasons_today: list[str] | None = None,
        resource_requirements: list[str] | None = None,
    ) -> ShutdownDailyReport:
        """Generate end-of-day shutdown progress report."""
        pending = [wo for wo in event.work_orders if wo not in event.completed_work_orders]
        blocked = blocked_wos or []
        unresolved = [b.blocker for b in blocked if b.blocker]

        metrics = ShutdownEngine.calculate_metrics(event)

        planned_elapsed = 0.0
        if event.planned_hours > 0 and event.planned_start:
            end_of_day = datetime(report_date.year, report_date.month, report_date.day, 23, 59, 59)
            elapsed_secs = (end_of_day - event.planned_start).total_seconds()
            planned_elapsed = min(max(0.0, elapsed_secs / 3600), event.planned_hours)

        sections = [
            ReportSection(
                title="Progress Summary",
                content=f"Completion: {event.completion_pct}% ({len(event.completed_work_orders)}/{len(event.work_orders)} WOs)",
                metrics={
                    "completion_pct": event.completion_pct,
                    "schedule_compliance_pct": metrics.schedule_compliance_pct,
                },
            ),
            ReportSection(
                title="Completed Today",
                content=", ".join(completed_today) if completed_today else "No work orders completed today",
            ),
            ReportSection(
                title="Pending Work",
                content=f"{len(pending)} work orders remaining",
                tables=[{"work_order_id": wo} for wo in pending],
            ),
            ReportSection(
                title="Blockers",
                content=f"{len(unresolved)} unresolved blockers" if unresolved else "No blockers",
                tables=[b.model_dump(mode="json") for b in blocked],
            ),
            ReportSection(
                title="Delays",
                content=f"Today: {delay_hours_today}h | Cumulative: {event.delay_hours}h",
                metrics={
                    "delay_hours_today": delay_hours_today,
                    "delay_hours_cumulative": event.delay_hours,
                },
            ),
        ]

        return ShutdownDailyReport(
            shutdown_id=event.shutdown_id,
            report_type=ShutdownReportType.DAILY_PROGRESS,
            report_date=report_date,
            total_work_orders=len(event.work_orders),
            completed_today=completed_today,
            completed_cumulative=list(event.completed_work_orders),
            pending_work_orders=pending,
            blocked_work_orders=blocked,
            completion_pct=event.completion_pct,
            schedule_compliance_pct=metrics.schedule_compliance_pct,
            planned_hours_elapsed=round(planned_elapsed, 1),
            actual_hours_elapsed=event.actual_hours,
            delay_hours_today=delay_hours_today,
            delay_hours_cumulative=event.delay_hours,
            delay_reasons_today=delay_reasons_today or [],
            unresolved_blockers=unresolved,
            resource_requirements=resource_requirements or [],
            sections=sections,
        )

    @staticmethod
    def generate_shift_report(
        event: ShutdownEvent,
        report_date: date,
        shift: ShiftType,
        completed_this_shift: list[str],
        blocked_wos: list[ShutdownWorkOrderStatus] | None = None,
        delay_hours_shift: float = 0.0,
        delay_reasons_shift: list[str] | None = None,
    ) -> ShutdownDailyReport:
        """Generate end-of-shift shutdown report."""
        pending = [wo for wo in event.work_orders if wo not in event.completed_work_orders]
        blocked = blocked_wos or []
        unresolved = [b.blocker for b in blocked if b.blocker]

        metrics = ShutdownEngine.calculate_metrics(event)

        sections = [
            ReportSection(
                title="Shift Summary",
                content=f"Shift {shift.value}: {len(completed_this_shift)} WOs completed",
                metrics={
                    "completion_pct": event.completion_pct,
                    "schedule_compliance_pct": metrics.schedule_compliance_pct,
                },
            ),
            ReportSection(
                title="Completed This Shift",
                content=", ".join(completed_this_shift) if completed_this_shift else "No work orders completed this shift",
            ),
            ReportSection(
                title="Blockers",
                content=f"{len(unresolved)} unresolved blockers" if unresolved else "No blockers",
            ),
        ]

        return ShutdownDailyReport(
            shutdown_id=event.shutdown_id,
            report_type=ShutdownReportType.SHIFT_END,
            report_date=report_date,
            shift=shift,
            total_work_orders=len(event.work_orders),
            completed_today=completed_this_shift,
            completed_cumulative=list(event.completed_work_orders),
            pending_work_orders=pending,
            blocked_work_orders=blocked,
            completion_pct=event.completion_pct,
            schedule_compliance_pct=metrics.schedule_compliance_pct,
            planned_hours_elapsed=0.0,
            actual_hours_elapsed=event.actual_hours,
            delay_hours_today=delay_hours_shift,
            delay_hours_cumulative=event.delay_hours,
            delay_reasons_today=delay_reasons_shift or [],
            unresolved_blockers=unresolved,
            sections=sections,
        )

    @staticmethod
    def generate_final_summary(event: ShutdownEvent) -> ShutdownDailyReport:
        """Generate final shutdown summary report after completion."""
        metrics = ShutdownEngine.calculate_metrics(event)
        pending = [wo for wo in event.work_orders if wo not in event.completed_work_orders]
        report_date = event.actual_end.date() if event.actual_end else date.today()

        sections = [
            ReportSection(
                title="Final Metrics",
                content=f"Schedule compliance: {metrics.schedule_compliance_pct}% | Scope: {metrics.scope_completion_pct}%",
                metrics={
                    "schedule_compliance_pct": metrics.schedule_compliance_pct,
                    "scope_completion_pct": metrics.scope_completion_pct,
                    "planned_vs_actual_ratio": metrics.planned_vs_actual_ratio,
                    "total_delays_hours": metrics.total_delays_hours,
                },
            ),
            ReportSection(
                title="Delay Analysis",
                content=f"Total delays: {event.delay_hours}h",
                tables=[{"reason": r} for r in event.delay_reasons],
            ),
            ReportSection(
                title="Scope Analysis",
                content=f"Completed: {len(event.completed_work_orders)}/{len(event.work_orders)} | Not completed: {len(pending)}",
                tables=[{"work_order_id": wo} for wo in pending],
            ),
            ReportSection(
                title="Duration Analysis",
                content=f"Planned: {event.planned_hours}h | Actual: {event.actual_hours}h",
                metrics={
                    "planned_hours": event.planned_hours,
                    "actual_hours": event.actual_hours,
                },
            ),
        ]

        return ShutdownDailyReport(
            shutdown_id=event.shutdown_id,
            report_type=ShutdownReportType.FINAL_SUMMARY,
            report_date=report_date,
            total_work_orders=len(event.work_orders),
            completed_today=[],
            completed_cumulative=list(event.completed_work_orders),
            pending_work_orders=pending,
            completion_pct=event.completion_pct,
            schedule_compliance_pct=metrics.schedule_compliance_pct,
            planned_hours_elapsed=event.planned_hours,
            actual_hours_elapsed=event.actual_hours,
            delay_hours_today=0.0,
            delay_hours_cumulative=event.delay_hours,
            sections=sections,
        )

    # ── GAP-W14: Velocity & Shift Suggestions ───────────────────────────

    @staticmethod
    def calculate_velocity(event: ShutdownEvent) -> float:
        """Calculate WOs completed per hour. Returns 0.0 if no elapsed time."""
        if event.actual_hours <= 0 or not event.completed_work_orders:
            return 0.0
        in_scope = [wo for wo in event.completed_work_orders if wo in event.work_orders]
        return round(len(in_scope) / event.actual_hours, 4)

    @staticmethod
    def suggest_next_shift_focus(
        event: ShutdownEvent,
        target_date: date,
        target_shift: ShiftType,
        schedule: ShutdownSchedule | None = None,
        blockers_resolved: list[str] | None = None,
        blockers_pending: list[str] | None = None,
    ) -> ShutdownShiftSuggestion:
        """Suggest prioritized work focus for the next shift."""
        pending = [wo for wo in event.work_orders if wo not in event.completed_work_orders]
        resolved = blockers_resolved or []
        still_pending = blockers_pending or []

        priority_wos: list[str] = []
        priority_reasons: list[str] = []
        critical_items: list[str] = []

        if schedule:
            # Prioritize critical path items that are pending
            cp_pending = [wo for wo in schedule.critical_path_items if wo in pending]
            for wo in cp_pending:
                priority_wos.append(wo)
                priority_reasons.append(f"{wo}: critical path item")
            critical_items = list(schedule.critical_path_items)

            # Then add items whose dependencies are all completed
            completed_set = set(event.completed_work_orders)
            for item in schedule.items:
                if item.work_order_id in pending and item.work_order_id not in priority_wos:
                    if all(dep in completed_set for dep in item.dependencies):
                        priority_wos.append(item.work_order_id)
                        priority_reasons.append(f"{item.work_order_id}: dependencies satisfied")
        else:
            # Without schedule, list all pending (unblocked first)
            blocked_ids = set(still_pending)
            unblocked = [wo for wo in pending if wo not in blocked_ids]
            blocked = [wo for wo in pending if wo in blocked_ids]
            priority_wos = unblocked + blocked
            for wo in unblocked:
                priority_reasons.append(f"{wo}: ready to execute")
            for wo in blocked:
                priority_reasons.append(f"{wo}: blocked")

        # Velocity-based projection
        velocity = ShutdownEngine.calculate_velocity(event)
        remaining = len(pending)
        if velocity > 0:
            hours_remaining = remaining / velocity
            total_hours = event.actual_hours + hours_remaining
            projected = round((len(event.work_orders) - remaining + remaining) / len(event.work_orders) * 100, 1) if event.work_orders else 0.0
            # More accurate: what % will be done after this shift (8h)
            shift_capacity = velocity * 8.0
            after_shift = min(len(event.work_orders), len(event.completed_work_orders) + shift_capacity)
            projected = round(after_shift / len(event.work_orders) * 100, 1) if event.work_orders else 0.0
        else:
            projected = event.completion_pct

        # Extract focus areas from WO IDs (area prefix convention)
        areas: set[str] = set()
        for wo in priority_wos[:10]:
            parts = wo.split("-")
            if len(parts) >= 2:
                areas.add(parts[0])

        return ShutdownShiftSuggestion(
            shutdown_id=event.shutdown_id,
            target_date=target_date,
            target_shift=target_shift,
            priority_work_orders=priority_wos,
            priority_reasons=priority_reasons,
            blockers_resolved=resolved,
            blockers_pending=still_pending,
            focus_areas=sorted(areas),
            recommended_sequence=priority_wos[:10],
            safety_reminders=[
                "Verify LOTO before starting work",
                "Confirm PTW (Permit to Work) is active",
                "Check confined space entry requirements",
            ],
            critical_path_items=critical_items,
            estimated_completion_if_on_track=min(100.0, projected),
        )

    # ── GAP-W14: Schedule / Cronogram Generation ────────────────────────

    @staticmethod
    def generate_shutdown_schedule(
        event: ShutdownEvent,
        work_order_details: list[dict],
        shift_hours: float = 8.0,
    ) -> ShutdownSchedule:
        """Generate sequenced shutdown schedule with critical path.

        Args:
            event: The shutdown event.
            work_order_details: List of dicts with keys:
                work_order_id, name, duration_hours, dependencies (list[str]),
                specialties (list[str]), area (str).
            shift_hours: Hours per shift (default 8).

        Returns:
            ShutdownSchedule with topologically sorted items and critical path.

        Raises:
            ValueError: If circular dependencies are detected.
        """
        if not work_order_details:
            return ShutdownSchedule(shutdown_id=event.shutdown_id)

        # Build adjacency and detail lookup
        details: dict[str, dict] = {}
        graph: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = {}

        for wo in work_order_details:
            wo_id = wo["work_order_id"]
            details[wo_id] = wo
            deps = wo.get("dependencies", [])
            in_degree.setdefault(wo_id, 0)
            for dep in deps:
                graph[dep].append(wo_id)
                in_degree[wo_id] = in_degree.get(wo_id, 0) + 1
                in_degree.setdefault(dep, in_degree.get(dep, 0))

        # Topological sort (Kahn's algorithm)
        queue = [n for n, d in in_degree.items() if d == 0]
        sorted_order: list[str] = []
        while queue:
            queue.sort()  # deterministic ordering
            node = queue.pop(0)
            sorted_order.append(node)
            for neighbor in graph.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_order) != len(in_degree):
            raise ValueError("Circular dependency detected in work order dependencies")

        # Early-start scheduling
        start_offsets: dict[str, float] = {}
        end_offsets: dict[str, float] = {}

        for wo_id in sorted_order:
            wo = details.get(wo_id, {})
            duration = wo.get("duration_hours", 0.0)
            deps = wo.get("dependencies", [])
            earliest_start = 0.0
            for dep in deps:
                if dep in end_offsets:
                    earliest_start = max(earliest_start, end_offsets[dep])
            start_offsets[wo_id] = earliest_start
            end_offsets[wo_id] = earliest_start + duration

        # Critical path (longest path through DAG)
        dist: dict[str, float] = {}
        predecessor: dict[str, str | None] = {}
        for wo_id in sorted_order:
            wo = details.get(wo_id, {})
            duration = wo.get("duration_hours", 0.0)
            deps = wo.get("dependencies", [])
            if not deps:
                dist[wo_id] = duration
                predecessor[wo_id] = None
            else:
                best_pred = max(deps, key=lambda d: dist.get(d, 0.0))
                dist[wo_id] = dist.get(best_pred, 0.0) + duration
                predecessor[wo_id] = best_pred

        # Trace back critical path from the node with max distance
        critical_path_items: list[str] = []
        if dist:
            end_node = max(dist, key=lambda n: dist[n])
            critical_path_hours = dist[end_node]
            node: str | None = end_node
            while node is not None:
                critical_path_items.append(node)
                node = predecessor.get(node)
            critical_path_items.reverse()
        else:
            critical_path_hours = 0.0

        cp_set = set(critical_path_items)

        # Build schedule items
        shifts = [ShiftType.MORNING, ShiftType.AFTERNOON, ShiftType.NIGHT]
        items: list[ShutdownScheduleItem] = []
        total_duration = 0.0

        for wo_id in sorted_order:
            wo = details.get(wo_id, {})
            duration = wo.get("duration_hours", 0.0)
            start = start_offsets.get(wo_id, 0.0)
            end = end_offsets.get(wo_id, 0.0)
            shift_index = int(start // shift_hours) % len(shifts)

            items.append(ShutdownScheduleItem(
                work_order_id=wo_id,
                name=wo.get("name", ""),
                start_offset_hours=round(start, 1),
                duration_hours=round(duration, 1),
                end_offset_hours=round(end, 1),
                shift=shifts[shift_index],
                dependencies=wo.get("dependencies", []),
                specialties=wo.get("specialties", []),
                area=wo.get("area", ""),
                is_critical_path=wo_id in cp_set,
            ))
            total_duration = max(total_duration, end)

        shifts_required = math.ceil(total_duration / shift_hours) if shift_hours > 0 else 0

        return ShutdownSchedule(
            shutdown_id=event.shutdown_id,
            items=items,
            total_duration_hours=round(total_duration, 1),
            critical_path_hours=round(critical_path_hours, 1),
            critical_path_items=critical_path_items,
            shifts_required=shifts_required,
        )
