# GAP-W05: Role-Based Dashboard Views — Execution Plan

> **Gap:** GAP-W05 | **Task:** T-43 | **Priority:** P4B | **Effort:** 1-2 sessions
> **Source:** Workshop funcional 2026-03-10 (Jose Cortinat, Jorge Alquinta, Gonzalo, Magda)
> **Created:** 2026-03-11 | **Last Updated:** 2026-03-11 | **Status:** COMPLETED

---

## Context

The functional definition workshop (2026-03-10) identified 7 user roles that interact with the platform. Currently all 19 Streamlit pages are equally visible to everyone — no role awareness exists in the UI. Workshop participant Jorge Alquinta specifically requested "un agente por rol"; the decision was **role-based UI views only** (no new agents).

**Problem:** A maintenance manager sees FMECA worksheets they'll never use; a technician sees executive KPI dashboards irrelevant to field work. This creates cognitive overload and hurts adoption — especially critical for field workers (supervisors 80% in terrain).

**Outcome:** Each role sees a personalized landing page with relevant pages highlighted, KPIs, and quick actions. All pages remain accessible (soft filtering) but the UI guides each role.

**Decisions Made:**
- 6 roles (Manager, Reliability Engineer, Planner, Supervisor, Technician, Consultant)
- Default role: Consultant (full access)
- Soft filtering (all pages visible, personalized landing page + banners)

---

## Roles (from Workshop)

| # | Role ID | EN | ES | Focus |
|---|---------|----|----|-------|
| 1 | `MANAGER` | Manager | Gerente de Mantenimiento | Production, safety, cost, availability, budget |
| 2 | `RELIABILITY_ENGINEER` | Reliability Engineer | Ingeniero de Confiabilidad | FMECA, RCA, Pareto, MTTR, strategy |
| 3 | `PLANNER` | Planner | Planificador | Backlog, scheduling, resources, WPs, SAP |
| 4 | `SUPERVISOR` | Supervisor | Supervisor | Daily execution, task assignment, program tracking |
| 5 | `TECHNICIAN` | Technician | Técnico / Mantenedor | Work requests, field capture, checklists |
| 6 | `CONSULTANT` | Consultant | Consultor | Full workflow — strategy to SAP delivery |

---

## Execution Checklist

### Step 1: Create `streamlit_app/role_config.py`
- [x]`UserRole` enum with 6 values
- [x]`ROLE_DISPLAY_NAMES` dict (i18n keys)
- [x]`ROLE_DESCRIPTIONS` dict (i18n keys)
- [x]`ROLE_ICONS` dict (emoji per role)
- [x]`PAGE_REGISTRY` list (19 pages with metadata: id, file, number, i18n_key, milestone)
- [x]`ROLE_PAGE_MAP` dict (primary + secondary pages per role)
- [x]`ROLE_KPIS` dict (KPI list per role with key, target, unit)
- [x]`ROLE_QUICK_ACTIONS` dict (action buttons per role)
- [x]Helper: `get_role_pages(role) -> dict`
- [x]Helper: `get_role_kpis(role) -> list`
- [x]Helper: `is_primary_page(role, page_number) -> bool`

**Role-Page Mapping:**
```
MANAGER:              primary=[7,14,5,15]        secondary=[1,2,19]
RELIABILITY_ENGINEER: primary=[2,3,4,13,16,17]   secondary=[1,5,14,15]
PLANNER:              primary=[10,11,12,6,15]     secondary=[1,5,9,14]
SUPERVISOR:           primary=[11,12,8,9]         secondary=[7,10,15]
TECHNICIAN:           primary=[8,9]               secondary=[1,7]
CONSULTANT:           primary=[18,19,1,2,3,4,6]   secondary=[5,7,10,13,14,15,16,17]
```

**Role-KPI Mapping:**
```
MANAGER:              availability, budget_variance, safety_incidents, production_compliance, mtbf
RELIABILITY_ENGINEER: mtbf, mttr, failure_rate, pm_compliance, bad_actor_count
PLANNER:              backlog_weeks, schedule_adherence, wo_completion, cost_per_wo, reactive_pct
SUPERVISOR:           daily_completion, resource_utilization, reactive_pct, rework_rate
TECHNICIAN:           tasks_completed, quality_score, safety_incidents
CONSULTANT:           wo_completion, pm_compliance, backlog_weeks, availability
```

### Step 2: Add role selector to `streamlit_app/i18n/__init__.py`
- [x]Add `role_selector()` function (clone `language_switcher()` pattern, lines 78-93)
- [x]Update `page_init()` to init `user_role` in session_state (default: CONSULTANT)

### Step 3: Add i18n translation keys
- [x]`streamlit_app/i18n/en.json` — ~40 keys under "role" section
- [x]`streamlit_app/i18n/es.json` — Spanish translations
- [x]`streamlit_app/i18n/fr.json` — French placeholders
- [x]`streamlit_app/i18n/ar.json` — Arabic placeholders

### Step 4: Update `streamlit_app/app.py`
- [x]Import `role_selector` from i18n
- [x]Call `role_selector()` after `language_switcher()`
- [x]Role description + icon header
- [x]"Your Tools" section: primary pages as cards
- [x]"Also Available" section: secondary pages compact
- [x]Quick Actions section
- [x]Original modules table in expander

### Step 5: Create `streamlit_app/components/role_banner.py`
- [x]`role_context_banner(page_number)` function
- [x]Shows subtle caption for non-primary pages

### Step 6: Enhance `streamlit_app/pages/14_executive_dashboard.py`
- [x]Import role config
- [x]Read user_role from session_state
- [x]Filter KPI traffic lights by role
- [x]Role-specific header
- [x]Tab visibility per role

### Step 7: Add `role_context_banner()` to all pages
- [x]`1_hierarchy.py` (page 1)
- [x]`2_criticality.py` (page 2)
- [x]`3_fmea.py` (page 3)
- [x]`4_strategy.py` (page 4)
- [x]`5_analytics.py` (page 5)
- [x]`6_sap_review.py` (page 6)
- [x]`7_overview.py` (page 7)
- [x]`8_field_capture.py` (page 8)
- [x]`9_work_requests.py` (page 9)
- [x]`10_planner.py` (page 10)
- [x]`11_backlog.py` (page 11)
- [x]`12_scheduling.py` (page 12)
- [x]`13_reliability.py` (page 13)
- [x]`15_reports_data.py` (page 15)
- [x]`16_fmeca.py` (page 16)
- [x]`17_defect_elimination.py` (page 17)
- [x]`18_wizard.py` (page 18)
- [x]`19_progress.py` (page 19)

### Step 8: Update `tools/models/schemas.py`
- [x]Add `SUPERVISOR` to `StakeholderRole` enum
- [x]Add `CONSULTANT` to `StakeholderRole` enum

### Step 9: Tests
- [x]Create `tests/test_role_config.py` (all roles have maps, valid page numbers, KPIs, no duplicates)
- [x]Create `tests/test_role_selector.py` (session state, default role, rerun)
- [x]Update `tests/test_navigation.py` (page count, role coverage)

### Step 10: Verify & Document
- [x]Run full test suite: `python -m pytest --tb=short -q` (0 regressions)
- [x]Update `MASTER_PLAN.md`: mark GAP-W05 / T-43 complete
- [x]Update memory file

---

## Files Changed

| File | Action |
|------|--------|
| `streamlit_app/role_config.py` | **CREATE** |
| `streamlit_app/components/role_banner.py` | **CREATE** |
| `tests/test_role_config.py` | **CREATE** |
| `tests/test_role_selector.py` | **CREATE** |
| `streamlit_app/i18n/__init__.py` | EDIT |
| `streamlit_app/i18n/en.json` | EDIT |
| `streamlit_app/i18n/es.json` | EDIT |
| `streamlit_app/i18n/fr.json` | EDIT |
| `streamlit_app/i18n/ar.json` | EDIT |
| `streamlit_app/app.py` | EDIT |
| `streamlit_app/pages/14_executive_dashboard.py` | EDIT |
| `streamlit_app/pages/*.py` (17 pages) | EDIT (one-liner) |
| `tools/models/schemas.py` | EDIT |
| `tests/test_navigation.py` | EDIT |

---

## Key Reusable Code

| Pattern | File | Lines |
|---------|------|-------|
| `language_switcher()` | `streamlit_app/i18n/__init__.py` | 78-93 |
| `page_init()` | `streamlit_app/i18n/__init__.py` | 135-138 |
| `StakeholderRole` enum | `tools/models/schemas.py` | 1368-1377 |
| `t()` translation | `streamlit_app/i18n/__init__.py` | 47-64 |
| `feedback_widget()` per-page | `streamlit_app/components/feedback.py` | pattern |
