# GAP-W10 Execution Plan: Consultant Workflow / Deliverable Tracking

> **Status:** COMPLETE
> **Estimated effort:** 12-14 hours (2 sessions)
> **Created:** 2026-03-11
> **Last updated:** 2026-03-11

---

## Context

**Problem:** The AMS platform has an ExecutionPlan model (checklist-level tracking) and a Progress Dashboard (Page 19), but no first-class deliverable tracking, time logging, or client approval workflow.

**Workshop requirement (03-10 transcripts):**
- Consultants need faster, standardized delivery with real-time progress visibility
- Clients track: schedule (plazos), deliverables (entregables), cost
- Clients can't validate deliverable quality — need clear quality criteria and review workflow
- Platform should show project status, cost, timeline, non-conformities

**Key quotes from workshop:**
> "Son proyectos que normalmente se ejecutan con consultoras, son proyectos largos, costosos para cuando terminas los entregables, posiblemente esos entregables en el camino se han desviado." — Jose Cortinat

> "el propio cliente tiene ese problema, que como no tienen tiempo, como dicen que esta bien el entregable y libero el pago de un contrato..." — Jose Cortinat

**MASTER_PLAN reference:** GAP-W10, Task T-48 (Priority P4B). "Client-facing deliverable view, effort logging, client review/approval portal."

---

## Architecture Decisions

1. **Deliverable = first-class entity** with 6-state lifecycle (DRAFT -> IN_PROGRESS -> SUBMITTED -> UNDER_REVIEW -> APPROVED; UNDER_REVIEW -> REJECTED -> IN_PROGRESS rework cycle)
2. **Stateless engine** (`DeliverableTrackingEngine`) for business logic — follows quality_score_engine pattern
3. **Combined Streamlit page** (Page 21) with 4 tabs, role-filtered — no separate client portal app
4. **Time logging at deliverable level** — TimeLog entries sum to deliverable.actual_hours
5. **Seed deliverables from ExecutionPlan** — bridge existing wizard output to new tracking
6. **No JWT yet** (G-07 is separate) — role selection via Streamlit sidebar, same as existing role_config.py
7. **SQLite auto-create** — new tables created on startup via `create_all_tables()`, no Alembic needed

---

## Deliverable Lifecycle State Machine

```
DRAFT ──> IN_PROGRESS ──> SUBMITTED ──> UNDER_REVIEW ──> APPROVED (terminal)
                                              │
                                              └──> REJECTED ──> IN_PROGRESS (rework)
```

---

## Phase A: Core Infrastructure (Session 1)

### A.1 Data Models — Pydantic Schemas (`tools/models/schemas.py`)
- [x] `DeliverableStatus` enum: DRAFT, IN_PROGRESS, SUBMITTED, UNDER_REVIEW, APPROVED, REJECTED
- [x] `DeliverableCategory` enum: HIERARCHY, CRITICALITY, FMECA, RCM_DECISIONS, TASKS, WORK_PACKAGES, WORK_INSTRUCTIONS, MATERIALS, SAP_UPLOAD, QUALITY_REPORT, VALIDATION_REPORT, CUSTOM
- [x] `Deliverable` model: deliverable_id, name, name_fr, category, milestone(1-4), status, execution_plan_stage_id, quality_score_id, estimated_hours, actual_hours, artifact_paths(list[str]), client_slug, project_slug, assigned_agent, created_at, submitted_at, reviewed_at, completed_at, client_feedback, consultant_notes
- [x] `TimeLog` model: log_id, deliverable_id, hours(>0,<=24), description, logged_by, logged_at, activity_type(analysis/review/rework/meeting/documentation)
- [x] `DeliverableTrackingSummary` model: total_deliverables, by_status(dict), by_milestone(dict), total_estimated_hours, total_actual_hours, variance_hours, variance_pct, overall_completion_pct

### A.2 ORM Models (`api/database/models.py`)
- [x] `DeliverableModel` — table `deliverables`, indexes on (client_slug, project_slug), milestone, status
- [x] `TimeLogModel` — table `time_logs`, FK to deliverables.deliverable_id, index on deliverable_id

### A.3 Deliverable Tracking Engine (NEW: `tools/engines/deliverable_tracking_engine.py`)
- [x] `VALID_TRANSITIONS` dict — explicit state machine
- [x] `STAGE_TO_CATEGORY` dict — maps stage names to DeliverableCategory
- [x] `DEFAULT_HOURS` dict — per-category benchmarks:
  - Hierarchy=2h, Criticality=3h, FMECA=8h, RCM=4h, Tasks=6h, WPs=4h, WIs=3h, Materials=2h, SAP=2h, QualityReport=1h, ValidationReport=1h, Custom=4h
- [x] `DeliverableTrackingEngine` class (stateless):
  - `validate_transition(current, target) -> bool`
  - `transition(current, target) -> DeliverableStatus` (raises ValueError)
  - `calculate_variance(estimated, actual) -> dict`
  - `build_summary(deliverables) -> DeliverableTrackingSummary`
  - `seed_from_execution_plan(plan_dict, client_slug, project_slug) -> list[dict]`
- [x] Register in `tools/engines/__init__.py`

### A.4 API Service (NEW: `api/services/deliverable_service.py`)
- [x] `create_deliverable(db, data)` — create + audit log
- [x] `get_deliverable(db, deliverable_id)` — single lookup
- [x] `list_deliverables(db, client_slug, project_slug, milestone, status)` — filtered list
- [x] `update_deliverable(db, deliverable_id, data)` — generic update
- [x] `transition_status(db, deliverable_id, target_status, feedback)` — validates via engine, sets timestamps
- [x] `log_time(db, data)` — creates TimeLog + updates deliverable.actual_hours
- [x] `list_time_logs(db, deliverable_id)` — ordered by logged_at desc
- [x] `get_project_summary(db, client_slug, project_slug)` — uses engine.build_summary()
- [x] `seed_deliverables_from_plan(db, plan_dict, client_slug, project_slug)` — bulk create

### A.5 API Router (NEW: `api/routers/deliverables.py`)
- [x] `POST /deliverables/` — create deliverable
- [x] `GET /deliverables/` — list with query params (client_slug, project_slug, milestone, status)
- [x] `GET /deliverables/{deliverable_id}` — detail
- [x] `PUT /deliverables/{deliverable_id}` — update fields
- [x] `PUT /deliverables/{deliverable_id}/transition` — status transition {status, feedback}
- [x] `POST /deliverables/{deliverable_id}/time-log` — log time {hours, description, activity_type}
- [x] `GET /deliverables/{deliverable_id}/time-logs` — time log list
- [x] `GET /deliverables/summary/{client_slug}/{project_slug}` — project summary
- [x] `POST /deliverables/seed-from-plan` — seed from execution plan {plan, client_slug, project_slug}

### A.6 Router Registration (`api/main.py`)
- [x] Import: `from api.routers import deliverables`
- [x] Register: `app.include_router(deliverables.router, prefix=prefix)`
- [x] Add `"deliverables"` to root endpoint modules list

### A.7 Admin Reset Update (`api/routers/admin.py`)
- [x] Add TimeLogModel and DeliverableModel to reset-database delete loop (TimeLog first — FK constraint)

### A.8 Streamlit API Client (`streamlit_app/api_client.py`)
- [x] `list_deliverables(client_slug, project_slug, milestone, status)`
- [x] `get_deliverable(deliverable_id)`
- [x] `create_deliverable(data)`
- [x] `update_deliverable(deliverable_id, data)`
- [x] `transition_deliverable(deliverable_id, status, feedback)`
- [x] `log_time(deliverable_id, data)`
- [x] `list_time_logs(deliverable_id)`
- [x] `get_deliverable_summary(client_slug, project_slug)`
- [x] `seed_deliverables(plan, client_slug, project_slug)`

### A.9 i18n Keys (4 files)
- [x] `streamlit_app/i18n/en.json` — deliverables section (~50 keys)
- [x] `streamlit_app/i18n/fr.json` — French translations
- [x] `streamlit_app/i18n/es.json` — Spanish translations
- [x] `streamlit_app/i18n/ar.json` — Arabic translations
- [x] Add `role.action.track_deliverables` key to all 4 files

### A.10 Streamlit Page (NEW: `streamlit_app/pages/21_deliverables.py`)
- [x] **Tab 1: Overview** — summary metrics, per-milestone progress bars, status distribution chart
- [x] **Tab 2: Deliverable Detail** — table with status badges, expandable rows, transition buttons
- [x] **Tab 3: Time Tracking** — log time form, history table, variance analysis
- [x] **Tab 4: Client Review** — SUBMITTED/UNDER_REVIEW filter, approve/reject with feedback
- [x] **Sidebar:** Seed section (load execution plan, seed deliverables)

### A.11 Role Config (`streamlit_app/role_config.py`)
- [x] Add page 21 to `PAGE_REGISTRY`
- [x] Add to CONSULTANT primary pages, MANAGER primary pages, PLANNER secondary pages
- [x] Add quick action for CONSULTANT

### A.12 SessionState Integration (`agents/orchestration/session_state.py`)
- [x] Add `"deliverables": EntityOwner.ORCHESTRATOR` to `ENTITY_OWNERSHIP`
- [x] Add `"time_logs": EntityOwner.ORCHESTRATOR` to `ENTITY_OWNERSHIP`
- [x] Add `deliverables` and `time_logs` property accessors

### A.13 Tests — Phase A
- [x] Create `tests/test_deliverable_tracking.py` — 27 engine unit tests
  - Valid transitions (all 6 edges)
  - Invalid transitions (3 cases: skip states, terminal, wrong direction)
  - Variance calculation (on track, over budget, zero estimate, threshold)
  - Summary building (empty, mixed, all approved)
  - Plan seeding (category mapping, default hours, unknown, prefix match)
  - Constants integrity (all statuses, all categories, stage mappings)
- [x] Create `tests/test_api/test_deliverables.py` — 20 API integration tests
  - CRUD operations (create, get, list, update, 404s)
  - Transition valid/invalid (happy path, rejection+rework, 409, 400)
  - Time logging + actual_hours update, list, 404
  - Summary endpoint (with data + empty)
  - Seed from plan (success + 400)
- [x] Update `tests/test_navigation.py` — page count, PAGE_FILES list, deliverable API client methods, i18n section
- [x] Update `tests/test_role_config.py` — page count 19 -> 23
- [x] Run: `python -m pytest --tb=short -q` — 2655 passed, 47 new tests ALL PASS

---

## Phase B: Polish & Integration (Session 2)

### B.1 Wizard Integration
- [x] `streamlit_app/pages/18_wizard.py` Step 5: replace `total_items * 0.25` with `DEFAULT_HOURS` from engine
- [x] Add "Seed Deliverables" button in wizard Step 5
- [x] `scripts/wizard_cli.py`: same DEFAULT_HOURS estimate, optional `--seed-deliverables` flag

### B.2 Workflow Integration (`agents/orchestration/workflow.py`)
- [x] Add `_update_deliverable_status(milestone_number)` method
  - On approval: DRAFT/IN_PROGRESS deliverables for that milestone -> SUBMITTED
  - Set submitted_at timestamp
  - Non-critical: log and continue if fails
- [x] Call from `_execute_milestone()` after `_update_execution_plan()`

### B.3 Quality Score Linking
- [x] In `_run_quality_scoring()`: store quality_score_id on matching deliverable via `_link_quality_scores_to_deliverables()`
- [x] On Page 21 Tab 2: display quality score badge if quality_score_id set (already in Phase A)

### B.4 Progress Dashboard Link (`streamlit_app/pages/19_progress.py`)
- [x] Add sidebar section showing deliverable summary if DB accessible
- [x] Link to Page 21 via `st.page_link()`

### B.5 Update MASTER_PLAN.md
- [x] Mark GAP-W10 as `[x]` closed
- [x] Mark T-48 as DONE
- [x] Update system state counts (routers, services, models, engines, pages, tests)
- [x] Add changelog entry with session number

### B.6 Final Verification
- [x] `python -m pytest --tb=short -q` — 2,768 passed, 0 failures

---

## Files Summary

### New Files (6)
| File | Purpose |
|------|---------|
| `tools/engines/deliverable_tracking_engine.py` | Stateless engine: state machine, variance, seeding |
| `api/services/deliverable_service.py` | CRUD + transitions + time logging |
| `api/routers/deliverables.py` | 9 REST endpoints |
| `streamlit_app/pages/21_deliverables.py` | 4-tab tracking page |
| `tests/test_deliverable_tracking.py` | Engine unit tests (~12) |
| `tests/test_api/test_deliverables.py` | API integration tests (~12) |

### Modified Files (14)
| File | Change |
|------|--------|
| `tools/models/schemas.py` | +5 new models/enums |
| `tools/engines/__init__.py` | Register new engine |
| `api/database/models.py` | +2 ORM models |
| `api/main.py` | Register router + module |
| `api/routers/admin.py` | Reset-database cleanup |
| `streamlit_app/api_client.py` | +9 client methods |
| `streamlit_app/role_config.py` | Page 21 + role mapping |
| `streamlit_app/i18n/en.json` | +~30 i18n keys |
| `streamlit_app/i18n/fr.json` | +~30 i18n keys |
| `streamlit_app/i18n/es.json` | +~30 i18n keys |
| `streamlit_app/i18n/ar.json` | +~30 i18n keys |
| `agents/orchestration/session_state.py` | +2 entity types |
| `agents/orchestration/workflow.py` | Deliverable status sync |
| `tests/test_navigation.py` | Page count update |
| `tests/test_session_state_extended.py` | New entity tests |
| `MASTER_PLAN.md` | Close GAP-W10 |

---

## Implementation Order (Dependency-Aware)

```
1. schemas.py (foundation — everything depends on this)
2. models.py (ORM — depends on schemas)
3. deliverable_tracking_engine.py (depends on schemas)
4. test_deliverable_tracking.py (verify engine in isolation)
5. deliverable_service.py (depends on ORM + engine)
6. deliverables.py router + main.py registration + admin.py update
7. test_api/test_deliverables.py (verify API layer)
8. api_client.py (depends on router)
9. i18n/*.json (independent — can parallelize)
10. role_config.py (depends on page existence)
11. 21_deliverables.py (depends on api_client + i18n + role_config)
12. session_state.py (independent of UI)
13. workflow.py integration (Phase B)
14. test_navigation.py + test_session_state_extended.py updates
15. Full test suite run
```

---

## Risk Mitigations

| Risk | Mitigation |
|------|------------|
| DB migration needed? | No — SQLite + `create_all_tables()` auto-creates new tables on startup |
| Breaking existing tests? | All changes additive — no existing behavior modified |
| Page count assertion fails? | Update in `test_navigation.py` (Step A.13) |
| FK constraint on reset? | Delete TimeLogModel before DeliverableModel in admin.py |
| i18n keys missing at runtime? | Use `t()` fallback pattern (returns key if missing) |
