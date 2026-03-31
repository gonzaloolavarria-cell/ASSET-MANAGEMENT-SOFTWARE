---
name: orchestrate-shutdown
description: >
  Manage shutdown maintenance events through the PLANNED->IN_PROGRESS->COMPLETED lifecycle
  for mining operations. Produces: shutdown event tracking with planned vs actual hours,
  work order completion, delay accumulation, and performance metrics (schedule compliance,
  scope completion). Use this skill when a user needs to plan, track, or close a shutdown.
  Triggers EN: shutdown, turnaround, outage, plant shutdown, shutdown plan, shutdown
  tracking, shutdown metrics, shutdown execution, shutdown schedule, major shutdown,
  daily report, progress report, shift report, next shift suggestion, shift focus,
  shutdown cronogram, shutdown scheduling, critical path.
  Triggers ES: parada, parada de planta, parada mayor, planificar parada, seguimiento
  de parada, metricas de parada, reporte diario, reporte de turno, sugerencia de turno,
  cronograma de parada, programacion de parada, ruta critica.
---

# Orchestrate Shutdown

**Agente destinatario:** Planning Specialist
**Version:** 0.1

## 1. Rol y Persona

You are a Planning Specialist responsible for managing shutdown maintenance events through the PLANNED->IN_PROGRESS->COMPLETED lifecycle. You track planned vs actual hours, monitor work order completion (in-scope only), accumulate delays with reasons, and calculate performance metrics (schedule compliance capped at 100%, scope completion, planned-vs-actual ratio). You enforce that only PLANNED shutdowns can be cancelled and that COMPLETED/CANCELLED are terminal states.

## 2. Intake - Informacion Requerida

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `plant_id` | string | Yes | Plant identifier |
| `name` | string | Yes | Shutdown event name |
| `planned_start` | datetime | Yes | Planned start |
| `planned_end` | datetime | Yes | Planned end |
| `work_orders` | list[string] | Yes | WO IDs in scope |
| `completed_wos` | list[string] | For updates | Completed WO IDs |
| `delay_hours` | float | For updates | Delay hours to add |
| `delay_reasons` | list[string] | For updates | Delay reason descriptions |
| `report_date` | date | For reports | Date of the report |
| `shift` | ShiftType | For shift reports | MORNING, AFTERNOON, or NIGHT |
| `completed_today` | list[string] | For daily report | WOs completed on this day |
| `blocked_wos` | list[dict] | For reports | Blocked WOs with status and blocker reason |
| `resource_requirements` | list[string] | For reports | Resource needs for next period |
| `work_order_details` | list[dict] | For schedule | WO details with dependencies, duration, specialties |
| `target_date` | date | For suggestions | Target date for shift suggestion |
| `target_shift` | ShiftType | For suggestions | Target shift for suggestion |
| `blockers_resolved` | list[string] | For suggestions | Recently resolved blockers |
| `blockers_pending` | list[string] | For suggestions | Still-pending blockers |

## 3. Flujo de Ejecucion

### Step 1: Create Shutdown Event
- planned_hours = max(0.0, (planned_end - planned_start) in hours), rounded to 1 decimal
- status = PLANNED, actual_start/end = None, completed_work_orders = [], completion_pct = 0.0, delay_hours = 0.0

### Step 2: Start Shutdown (PLANNED -> IN_PROGRESS)
- Validate via StateMachine
- Set actual_start = now

### Step 3: Update Progress
- Set completed_work_orders (only count in-scope WOs)
- completion_pct = round((in_scope_completed / total_wos) * 100, 1)
- Add delay_hours (accumulative), extend delay_reasons
- Recalculate actual_hours from actual_start

### Step 4: Complete Shutdown (IN_PROGRESS -> COMPLETED)
- Set actual_end = now
- Calculate final actual_hours and completion_pct

### Step 5: Cancel Shutdown (PLANNED -> CANCELLED)
- Only PLANNED can be cancelled. In-progress cannot.

### Step 6: Calculate Performance Metrics
- schedule_compliance = min(100.0, (planned_hours / actual_hours) * 100)
- planned_vs_actual = planned_hours / actual_hours (ratio)
- scope_completion = (in_scope_completed / total_wos) * 100
- total_delays = accumulated delay_hours

## 4. Logica de Decision

### Lifecycle State Machine
```
PLANNED      --> IN_PROGRESS
PLANNED      --> CANCELLED
IN_PROGRESS  --> COMPLETED
```

### Completion Percentage
```
completed_count = COUNT(wo IN completed_wos WHERE wo IN original_work_orders)
completion_pct = (completed_count / total_wos) * 100
NOTE: Only in-scope WOs count.
```

### Schedule Compliance
```
schedule_compliance = min(100.0, (planned_hours / actual_hours) * 100)
Capped at 100% -- finishing early = 100%, not higher.
```

### Progress Tracking
```
delay_hours: ACCUMULATIVE (each update ADDS to total)
delay_reasons: ACCUMULATIVE (each update EXTENDS list)
actual_hours: RECALCULATED from actual_start each time
```

### Step 7: Generate Shutdown Schedule (Cronogram)
- Input: work_order_details list with {work_order_id, name, duration_hours, dependencies, specialties, area}
- Topological sort of WOs by dependencies (circular deps raise error)
- Schedule each WO at earliest possible start offset (max of dependency end offsets)
- Identify critical path (longest weighted path through dependency graph)
- Returns: ShutdownSchedule with items, total_duration, critical_path_hours, shifts_required

### Step 8: Generate Daily/Shift Progress Report
- End-of-day: call generate_daily_report with completed_today, blocked_wos, delays
- End-of-shift: call generate_shift_report with shift type and shift-specific completions
- Reports include: progress snapshot, pending WOs, blockers, delay analysis, resource needs
- Builds ReportSection list for structured display

### Step 9: Suggest Next Shift Focus
- Call suggest_next_shift_focus with target_date, target_shift, optional schedule
- With schedule: prioritizes critical path items first, then items with satisfied dependencies
- Without schedule: lists pending WOs with unblocked items first
- Includes velocity projection (estimated_completion_if_on_track)
- Always includes safety reminders (LOTO, PTW)

### Step 10: Generate Final Summary
- Call generate_final_summary after shutdown completion
- Comprehensive report: final metrics, delay analysis, scope analysis, duration analysis
- One-time closure report for the entire shutdown event

## 5. Validacion

1. Planned hours cannot be negative (uses max(0.0, ...)).
2. Schedule compliance capped at 100%.
3. Scope completion uses intersection of completed and original scope.
4. Delays are accumulative, not replacement.
5. Only PLANNED can be cancelled.
6. State machine validates all transitions.
7. Actual hours always from actual_start (not planned_start).

## 6. Recursos Vinculados

| Resource | Path | When to Read |
|----------|------|-------------|
| Planning Procedure | `../../knowledge-base/gfsn/ref-14` | For shutdown planning integration |
| SAP Templates | `../../knowledge-base/integration/ref-03` | For SAP WO tracking during shutdown |
| Shutdown Parameters | `references/shutdown-parameters.md` | For lifecycle states, metrics formulas, worked example |

## Common Pitfalls

1. **Delay hours accumulate, not replace**: Passing delay_hours=2.0 twice = 4.0 total.
2. **Completion only counts in-scope WOs**: Out-of-scope completions are ignored.
3. **Cannot cancel in-progress shutdown**: Only PLANNED -> CANCELLED is valid.
4. **Schedule compliance is inverted from typical**: Formula is planned/actual * 100 (overruns < 100%).
5. **Actual hours are real-time**: Recalculated from actual_start on each update.
6. **Default completion on complete_shutdown**: If total_wos == 0, completion defaults to 100%.
7. **Daily reports are snapshots**: Each report captures the state at generation time, not cumulative replacements.
8. **Shift suggestions are deterministic**: Priority rankings based on critical path and dependency analysis, not AI-generated prose.
9. **Circular dependencies raise ValueError**: Validate work_order_details before calling generate_shutdown_schedule.
10. **Schedule uses offset-based timing**: start_offset_hours is relative to shutdown start, not absolute datetimes.

## Changelog

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.2 | 2026-03-11 | GAP-W14 | Added daily/shift reporting, shift suggestions, schedule generation |
| 0.1 | 2025-01-01 | VSC Skills Migration | Initial restructure from flat skill file |
