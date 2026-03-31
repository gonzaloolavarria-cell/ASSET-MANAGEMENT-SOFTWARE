# GAP-W14: Shutdown Management Enhancement — Execution Tracker

> **Source:** MASTER_PLAN.md T-47 | **Gap:** GAP-W14
> **Estimate:** 1-2 sessions | **Status:** DONE
> **Workshop basis:** 03-10 AMS Definicion transcripts (Jose Cortinat)

---

## Objective

Enhance `shutdown_engine.py` with three capabilities identified in the functional definition workshop:

1. **Daily progress reporting** — automated end-of-day/shift closure reports
2. **Shift-to-shift suggestions** — prioritized work focus for incoming shift
3. **Schedule generation** — cronogram with dependency sequencing and critical path

## Workshop Context

Jose Cortinat (product lead, Transcript 2, line ~250):
> "con el cierre del dia, lo reportado con ordenes de trabajo, va generando toda la reportabilidad automatizada de el avance de la parada, requerimientos, bloqueos, y sugerencia de enfoque de trabajo al dia siguiente. Para que los equipos esten mas alineados cuando comienzan el turno."

Key requirements:

- End-of-day WO review -> auto-generated progress report
- Blocker identification and resource requirements
- Next-shift/next-day work focus suggestion
- Schedule generation for major shutdowns (cronogramas)
- Teams aligned when starting each shift

## Pre-Existing Code

| Component | Location | Status |
|-----------|----------|--------|
| ShutdownEngine (6 methods) | `tools/engines/shutdown_engine.py` | EXISTS -- extend |
| ShutdownEvent (17 fields) | `tools/models/schemas.py:2254` | EXISTS -- reuse |
| ShutdownMetrics (4 fields) | `tools/models/schemas.py:2273` | EXISTS -- reuse |
| ShutdownStatus enum | `tools/models/schemas.py` | EXISTS -- reuse |
| ShutdownType enum | `tools/models/schemas.py` | EXISTS -- reuse |
| ReportSection model | `tools/models/schemas.py:2471` | EXISTS -- reuse |
| ShiftType enum | `tools/models/schemas.py:110` | EXISTS -- reuse |
| MCP tools (4) | `agents/tool_wrappers/reliability_tools.py` | EXISTS -- extend |
| Skill orchestrate-shutdown | `skills/02-work-planning/orchestrate-shutdown/` | EXISTS -- update |
| API endpoints (4) | `api/routers/reliability.py` | EXISTS -- extend |
| UI tab | `streamlit_app/pages/13_reliability.py` | EXISTS -- enhance |
| DB models (2) | `api/database/models.py` | EXISTS -- no changes needed |
| Tests (9) | `tests/test_shutdown_engine.py` | EXISTS -- extend |

## Execution Checklist

### Session 1: Core Backend

#### Step 1: New Pydantic Schemas (`tools/models/schemas.py`)

- [x] 1.1 Add `ShutdownReportType` enum (DAILY_PROGRESS, SHIFT_END, FINAL_SUMMARY)
- [x] 1.2 Add `ShutdownWorkOrderStatus` model (work_order_id, status, completed_at, blocker)
- [x] 1.3 Add `ShutdownDailyReport` model (report_id, shutdown_id, report_type, report_date, shift, progress, metrics, blockers, sections)
- [x] 1.4 Add `ShutdownShiftSuggestion` model (suggestion_id, shutdown_id, target_date, target_shift, priorities, blockers, focus, projection)
- [x] 1.5 Add `ShutdownScheduleItem` model (work_order_id, offsets, shift, dependencies, specialties, area, is_critical_path)
- [x] 1.6 Add `ShutdownSchedule` model (schedule_id, items, durations, critical path, shifts_required)
- [x] 1.7 Update `tools/models/__init__.py` exports (wildcard import -- no change needed)

#### Step 2: Engine -- Reports (`tools/engines/shutdown_engine.py`)

- [x] 2.1 Implement `generate_daily_report()` static method
- [x] 2.2 Implement `generate_shift_report()` static method
- [x] 2.3 Implement `generate_final_summary()` static method

#### Step 3: Engine -- Suggestions (`tools/engines/shutdown_engine.py`)

- [x] 3.1 Implement `calculate_velocity()` static method
- [x] 3.2 Implement `suggest_next_shift_focus()` static method

#### Step 4: Engine -- Schedule/Cronogram (`tools/engines/shutdown_engine.py`)

- [x] 4.1 Implement `generate_shutdown_schedule()` static method (topological sort + critical path)

#### Step 5: MCP Tool Wrappers (`agents/tool_wrappers/reliability_tools.py`)

- [x] 5.1 Add `generate_shutdown_daily_report` tool
- [x] 5.2 Add `generate_shutdown_shift_report` tool
- [x] 5.3 Add `suggest_shutdown_next_shift` tool
- [x] 5.4 Add `generate_shutdown_schedule` tool
- [x] 5.5 Add `generate_shutdown_final_summary` tool

#### Step 6: Tests (`tests/test_shutdown_engine.py`)

- [x] 6.1 TestGenerateDailyReport (6 tests)
- [x] 6.2 TestGenerateShiftReport (3 tests)
- [x] 6.3 TestGenerateFinalSummary (3 tests)
- [x] 6.4 TestSuggestNextShiftFocus (5 tests)
- [x] 6.5 TestGenerateShutdownSchedule (7 tests)
- [x] 6.6 TestCalculateVelocity (2 tests)
- [x] 6.7 Run tests: `python -m pytest tests/test_shutdown_engine.py -v` -- 37 passing

#### Step 7: Skill Updates (`skills/02-work-planning/orchestrate-shutdown/`)

- [x] 7.1 Update CLAUDE.md with Steps 7-10
- [x] 7.2 Add trigger keywords (EN + ES)
- [x] 7.3 Update references/shutdown-parameters.md
- [x] 7.4 Update evals/trigger-eval.json

### Session 2: API + UI + Integration

#### Step 8: API Endpoints (`api/routers/reliability.py`)

- [x] 8.1 Add `POST /shutdowns/{shutdown_id}/daily-report`
- [x] 8.2 Add `POST /shutdowns/{shutdown_id}/shift-report`
- [x] 8.3 Add `POST /shutdowns/{shutdown_id}/suggest-next-shift`
- [x] 8.4 Add `POST /shutdowns/{shutdown_id}/schedule`
- [x] 8.5 Add `POST /shutdowns/{shutdown_id}/final-summary`
- [x] 8.6 Add service methods in `api/services/reliability_service.py`

#### Step 9: UI Enhancement (`streamlit_app/pages/13_reliability.py`)

- [x] 9.1 Add Daily Report expander
- [x] 9.2 Add Shift Suggestions expander
- [x] 9.3 Add Schedule/Cronogram expander
- [x] 9.4 Add Final Summary expander
- [x] 9.5 Add i18n keys to en.json (22 keys)
- [x] 9.6 Add i18n keys to es.json (22 keys)
- [x] 9.7 Add i18n keys to fr.json (22 keys)
- [x] 9.8 Add i18n keys to ar.json (22 keys)

#### Step 10: Integration and Closeout

- [x] 10.1 Run full test suite: 2,713 passed, 3 failed (pre-existing page count tests)
- [x] 10.2 MCP tool count: 5 new tools added to reliability_tools.py
- [ ] 10.3 Run skill trigger eval (deferred -- requires Claude API key)
- [x] 10.4 Update MASTER_PLAN.md: GAP-W14 closed, T-47 done
- [x] 10.5 Update MASTER_PLAN.md changelog (Session 19 entry)
- [x] 10.6 Update this file: Status = DONE

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Single `ShutdownDailyReport` with `report_type` discriminator | Reduces schema proliferation; 3 report types share 90% of fields |
| Offset-based scheduling (hours from shutdown start) | Portable, testable, UI converts to real dates |
| Reuse `ReportSection` from `schemas.py:2471` | Consistent with existing weekly/monthly report pattern |
| Reuse `ShiftType` enum from `schemas.py:110` | No new enums for existing concepts |
| Deterministic suggestions (no LLM) | Critical path first, unblocked second -- pure algorithm |
| Extend existing `ShutdownEngine` class | Don't fragment shutdown logic into multiple files |
| Topological sort for schedule | Standard algorithm, detects circular deps, enables critical path |

## Files Modified

| File | Change Type | Lines Added (est.) |
|------|-------------|-------------------|
| `tools/models/schemas.py` | MODIFY | ~60 |
| `tools/engines/shutdown_engine.py` | MODIFY | ~220 |
| `agents/tool_wrappers/reliability_tools.py` | MODIFY | ~70 |
| `tests/test_shutdown_engine.py` | MODIFY | ~220 |
| `skills/02-work-planning/orchestrate-shutdown/CLAUDE.md` | MODIFY | ~40 |
| `skills/02-work-planning/orchestrate-shutdown/references/shutdown-parameters.md` | MODIFY | ~50 |
| `skills/02-work-planning/orchestrate-shutdown/evals/trigger-eval.json` | MODIFY | ~20 |
| `api/routers/reliability.py` | MODIFY | ~50 |
| `api/services/reliability_service.py` | MODIFY | ~40 |
| `streamlit_app/pages/13_reliability.py` | MODIFY | ~100 |
| `streamlit_app/i18n/en.json` | MODIFY | ~15 keys |
| `streamlit_app/i18n/es.json` | MODIFY | ~15 keys |
| `streamlit_app/i18n/fr.json` | MODIFY | ~15 keys |
| `streamlit_app/i18n/ar.json` | MODIFY | ~15 keys |
| `MASTER_PLAN.md` | MODIFY | ~5 |
| **Total** | | **~940 lines** |
