# Shutdown Parameters Reference

## Lifecycle States

| State | Description | Terminal |
|-------|-------------|---------|
| PLANNED | Event created, not yet started | No |
| IN_PROGRESS | Execution underway | No |
| COMPLETED | Execution finished | Yes |
| CANCELLED | Event cancelled before start | Yes |

## Valid Transitions

| From | To | Method |
|------|----|--------|
| PLANNED | IN_PROGRESS | start_shutdown |
| PLANNED | CANCELLED | cancel_shutdown |
| IN_PROGRESS | COMPLETED | complete_shutdown |

## Metrics Formulas

### Planned Hours
```
planned_hours = max(0.0, (planned_end - planned_start).total_seconds() / 3600)
Rounded to 1 decimal place.
```

### Schedule Compliance
```
schedule_compliance = min(100.0, round((planned_hours / actual_hours) * 100, 1))
Minimum planned_hours = 1.0 (avoid division by zero)
Default actual_hours = planned_hours if 0
```

### Scope Completion
```
completed_count = len([wo for wo in completed_wos if wo in work_orders])
scope_completion = round((completed_count / total_wos) * 100, 1) if total_wos > 0 else 0.0
```

### Planned vs Actual Ratio
```
ratio = round(planned_hours / actual_hours, 2) if actual_hours > 0 else 1.0
> 1.0 = ahead of schedule
< 1.0 = overran
```

## Worked Example

| Step | Action | Status | Hours | Completion | Delays |
|------|--------|--------|-------|------------|--------|
| Create | Plan 84.0h shutdown, 5 WOs | PLANNED | 84.0 planned | 0% | 0h |
| Start | Begin at 06:30 | IN_PROGRESS | actual_start set | 0% | 0h |
| Update 1 | WO-001, WO-002 done | IN_PROGRESS | ~29.5h | 40% | +2.0h |
| Update 2 | WO-003, WO-004 done | IN_PROGRESS | ~59.5h | 80% | +1.5h (3.5h total) |
| Complete | End at 20:00 | COMPLETED | 85.5h actual | 80% | 3.5h total |

**Metrics:**
- schedule_compliance = min(100, 84.0/85.5*100) = 98.2%
- scope_completion = 80.0% (4/5 WOs)
- planned_vs_actual = 84.0/85.5 = 0.98
- total_delays = 3.5h

---

## Report Types (GAP-W14)

| Type | When | Contains |
|------|------|----------|
| DAILY_PROGRESS | End of each day | Completed today, pending, blockers, delays, metrics snapshot |
| SHIFT_END | End of each shift | Shift-specific completions, blockers, delay for shift |
| FINAL_SUMMARY | After shutdown completes | Full cumulative metrics, delay analysis, scope analysis, duration analysis |

All three use the same `ShutdownDailyReport` model with `report_type` discriminator.

## Shift Suggestion Algorithm

Priority ranking (deterministic, no LLM):

1. **Critical path items** (if schedule provided) — highest priority
2. **Items with all dependencies satisfied** — ready to execute
3. **Unblocked items** (not in blockers_pending) — next priority
4. **Blocked items** — listed last

**Velocity projection:**
```
velocity = completed_in_scope_wos / actual_hours
shift_capacity = velocity * 8.0 hours
projected_after_shift = (current_completed + shift_capacity) / total_wos * 100
```

**Safety reminders (always included):**
- Verify LOTO before starting work
- Confirm PTW (Permit to Work) is active
- Check confined space entry requirements

## Schedule Generation

### Algorithm
1. **Topological sort** (Kahn's algorithm) — detect circular deps
2. **Early-start scheduling** — each WO starts at max(end_offset of dependencies)
3. **Shift assignment** — offset / shift_hours → shift index (MORNING/AFTERNOON/NIGHT cycle)
4. **Critical path** — longest weighted path through DAG (traced backwards from max-distance node)

### Input Format
```json
{
  "work_order_id": "WO-001",
  "name": "Replace bearing",
  "duration_hours": 4.0,
  "dependencies": ["WO-000"],
  "specialties": ["mechanic"],
  "area": "SAG Mill"
}
```

### Output: ShutdownSchedule
- `items`: list of ShutdownScheduleItem with offsets
- `total_duration_hours`: makespan of the schedule
- `critical_path_hours`: duration of the critical chain
- `critical_path_items`: WO IDs on the critical path
- `shifts_required`: ceil(total_duration / shift_hours)

### Worked Example: Schedule

| WO | Duration | Deps | Start Offset | End Offset | Critical Path |
|----|----------|------|--------------|------------|---------------|
| A | 4h | none | 0h | 4h | No |
| B | 6h | none | 0h | 6h | Yes |
| C | 2h | A, B | 6h | 8h | Yes |

- Total duration: 8h
- Critical path: B -> C (6+2=8h)
- Shifts required: 1 (8h / 8h = 1)
