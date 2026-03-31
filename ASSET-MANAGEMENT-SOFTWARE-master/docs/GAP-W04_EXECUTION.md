# GAP-W04 Execution Plan — Financial Agent / ROI Tracking

> **Status:** COMPLETE (Sessions A+B done · C/D optional post-pilot)
> **Created:** 2026-03-11
> **Last Updated:** 2026-03-12
> **Related Gaps:** GAP-W04 · T-45 · MASTER_PLAN §3.5 line 247
> **See also:** `docs/GAP-W04_EXECUTION_PLAN.md` (original implementation tracker — all ✅)

---

## Context

Management at OCP needs **financial proof of ROI** to justify the AMS investment.
The platform already has a Life-Cycle Cost engine and cost-risk optimizer, but had
no ROI calculator, no budget tracking, and no financial dashboard.

**Workshop requirement (2026-03-10):** Show investment vs. avoided downtime costs,
budget variance, and man-hours saved by AI-assisted analysis.

**Goal:** ROI calculation engine + budget entities in SessionState + financial
dashboard page. Agents gain financial tools. Closes GAP-W04 / T-45.

---

## Session A: Core Implementation ✅ DONE

### Phase 1: Data Models

- [x] **1.1** `tools/models/schemas.py` — 12 new financial schemas
  - Enums: `FinancialCategory` (8), `BudgetStatus` (4), `ROIStatus` (3), `CurrencyCode` (3)
  - Models: `BudgetItem`, `BudgetSummary`, `ROIInput`, `ROIResult`,
    `FinancialImpact`, `FinancialSummary`, `BudgetVarianceAlert`, `ManHourSavingsReport`

### Phase 2: Business Logic Engines

- [x] **2.1** `tools/engines/roi_engine.py` — 4 static methods
  - `calculate_roi()` → NPV, payback period, BCR, IRR, cumulative savings by year
  - `compare_scenarios()` → rank by NPV descending
  - `calculate_financial_impact()` → annualized cost breakdown per equipment
  - `calculate_man_hours_saved()` → traditional vs. AI-assisted comparison

- [x] **2.2** `tools/engines/budget_engine.py` — 4 static methods
  - `track_budget()` → variance per category + recommendations
  - `detect_variance_alerts()` → WARNING (>10%) / CRITICAL (>20%) thresholds
  - `generate_financial_summary()` → executive roll-up
  - `forecast_budget()` → linear extrapolation for 3-month horizon

### Phase 3: MCP Tool Wrappers

- [x] **3.1** `agents/tool_wrappers/financial_tools.py` — 8 tools registered in server.py
  - Orchestrator: `calculate_roi`, `compare_roi_scenarios`, `calculate_man_hours_saved`,
    `detect_budget_alerts`, `generate_financial_summary` (5 tools)
  - Reliability: `calculate_financial_impact` (1 tool)
  - Planning: `calculate_roi`, `calculate_financial_impact`, `track_budget`,
    `forecast_budget` (4 tools)

- [x] **3.2** `agents/tool_wrappers/server.py` — financial_tools imported + AGENT_TOOL_MAP updated

### Phase 4: API Layer

- [x] **4.1** `api/routers/financial.py` — 8 endpoints
  - `POST /financial/roi` — single project ROI
  - `POST /financial/roi/compare` — multi-scenario ranking
  - `POST /financial/budget/track` — budget variance
  - `POST /financial/budget/alerts` — threshold alerts
  - `POST /financial/budget/forecast` — 3-month forecast
  - `POST /financial/impact` — per-equipment financial impact
  - `POST /financial/man-hours` — man-hours saved
  - `GET /financial/summary/{plant_id}` — executive summary

- [x] **4.2** `api/main.py` — financial router registered at `/api/v1/financial`

- [x] **4.3** `streamlit_app/api_client.py` — 7 new client methods

### Phase 5: Streamlit UI

- [x] **5.1** `streamlit_app/pages/24_financial.py` — Page 24, 5-tab dashboard
  - Tab 1: Budget Tracking (variance, alerts, category bar chart)
  - Tab 2: ROI Calculator (form inputs, NPV/payback/BCR/ROI, cumulative savings line)
  - Tab 3: Cost Drivers (per-equipment Pareto chart)
  - Tab 4: Man-Hours Savings (activity comparison grouped bars)
  - Tab 5: Financial Summary (executive roll-up + recommendations)

- [x] **5.2** `streamlit_app/components/charts.py` — 4 new Plotly functions
  - `budget_variance_chart()`, `roi_cumulative_chart()`,
    `cost_driver_pareto_chart()`, `man_hours_comparison_chart()`

- [x] **5.3** `streamlit_app/i18n/{en,es,fr,ar}.json` — 45+ financial keys

- [x] **5.4** `streamlit_app/role_config.py` — Page 24 added
  - Manager: primary · Planner: secondary

### Phase 6: Tests (Core)

- [x] **6.1** `tests/test_financial_schemas.py` — ~14 tests
- [x] **6.2** `tests/test_financial_engine.py` — ~40 tests
- [x] **6.3** `tests/test_financial_tools.py` — ~8 tests
- [x] **6.4** `tests/test_navigation.py` — updated to page count 24
- [x] **6.5** `tests/test_agent_tool_access.py` — updated tool assignments
- [x] **6.6** `tests/test_agent_tools.py` — updated tool counts
- [x] **6.7** `tests/test_role_config.py` — updated with page 24

---

## Session B: Skill + Validation ✅ DONE (Sessions 24-25)

**Note:** Session B was completed in Sessions 24-25 (before this planning session).
All items below were already done when this tracking doc was created on 2026-03-12.

### Phase 7: Financial Skill ✅

- [x] **7.1** `skills/04-cost-analysis/calculate-roi/CLAUDE.md` — ROI skill (Orchestrator)
  - Triggers: ROI, retorno de inversión, NPV, BCR, payback, investment justification
  - Tools: `calculate_roi`, `compare_roi_scenarios`

- [x] **7.2** `skills/04-cost-analysis/calculate-roi/evals/trigger-eval.json`

- [x] **7.3** `skills/04-cost-analysis/calculate-roi/evals/evals.json`

- [x] **7.4** `calculate-roi` registered in `agents/orchestrator/skills.yaml`
- [x] **7.5** `track-budget` registered in `agents/planning/skills.yaml`

### Phase 8: Test Suite Validation ✅

- [x] **8.1** Financial tests pass: `pytest tests/test_financial_*.py` — **57 passed**
- [x] **8.2** Full suite: **2,888 passed, 0 failures** (at time of completion)
- [x] **8.3** Pre-existing failure in test_api (audio_transcription circular import) — out of scope
- [x] **8.4** *(2026-03-12 fix)* Fixed `test_skills_v2.py` — 4 failures from `capture-expert-knowledge`
  skill (GAP-W13) not reflected in test expectations. Updated expected counts 16→17 and 43→44.

### Phase 9: MASTER_PLAN Update ✅

- [x] **9.1** GAP-W04 marked `[x]` DONE in MASTER_PLAN §3.5
- [x] **9.2** T-45 marked done in §5 (P4B table)
- [x] **9.3** System state counts updated (UI pages 24, routers 22, tools 163, engines 42)
- [x] **9.4** Changelog entry added

### Phase 10: Smoke Test ✅ DONE (2026-03-12)

- [x] **10.1** Page 24 structure verified — AST valid, 5 tabs (tab1–tab5), 6 API methods wired
- [x] **10.2** ROI Calculator: `POST /financial/roi` → NPV $2,015,407, BCR 5.03, "Strong ROI: investment highly justified"
- [x] **10.3** Budget tab: variance chart function exists in `components/charts.py`
- [x] **10.4** `POST /api/v1/financial/roi` → HTTP 200, valid JSON with npv/bcr/recommendation fields

---

## Session C: Persistence Layer (PENDING)

**Goal:** Persist financial data to DB for historical tracking and audit trail.

### Phase 11: ORM Models

- [ ] **11.1** Add to `api/database/models.py`:
  - `BudgetItemModel` — plant_id, category, period_start, period_end,
    planned_amount, actual_amount, currency, created_at
  - `ROIProjectModel` — project_id, plant_id, investment_cost, npv, bcr,
    payback_years, status, calculated_at

### Phase 12: Service Layer

- [ ] **12.1** Create `api/services/financial_service.py`:
  - `save_budget_items(plant_id, items)` — bulk upsert
  - `get_budget_summary(plant_id, period?)` — aggregate + variance from DB
  - `save_roi_project(roi_result)` — persist ROI calculation
  - `get_roi_history(plant_id)` — list all projects by plant

- [ ] **12.2** Update `GET /financial/summary/{plant_id}` to pull from DB

### Phase 13: SessionState Integration

- [ ] **13.1** Add `financial_summaries` entity (owner: orchestrator) to SWMR table
- [ ] **13.2** Add `budget_items` entity (owner: planning) to SWMR table
- [ ] **13.3** Optional: wire `generate_financial_summary` into M3 gate review

### Phase 14: Persistence Tests

- [ ] **14.1** ~15 tests in `tests/test_api/test_financial_api.py`

---

## Session D: Reporting + Workflow Integration (OPTIONAL)

### Phase 15: Reporting Integration

- [ ] **15.1** Add `generate_financial_kpi_section()` to `tools/engines/reporting_engine.py`
- [ ] **15.2** Wire to Page 15 (Reports) — add "Financial KPIs" section

### Phase 16: Workflow Gate

- [ ] **16.1** In `agents/orchestration/workflow.py`, after M3 approval:
  - Auto-call `calculate_financial_impact` + `generate_financial_summary`
  - Persist via SessionState, include in gate report

---

## Critical Files Reference

| File | Role | Status |
|------|------|--------|
| `tools/engines/roi_engine.py` | ROI calculations | ✅ EXISTS |
| `tools/engines/budget_engine.py` | Budget tracking | ✅ EXISTS |
| `tools/models/schemas.py` | 12 financial schemas | ✅ MODIFIED |
| `agents/tool_wrappers/financial_tools.py` | 8 MCP tools | ✅ EXISTS |
| `agents/tool_wrappers/server.py` | Tool registration | ✅ MODIFIED |
| `api/routers/financial.py` | 8 API endpoints | ✅ EXISTS |
| `api/main.py` | Router registration | ✅ MODIFIED |
| `streamlit_app/pages/24_financial.py` | 5-tab dashboard | ✅ EXISTS |
| `streamlit_app/components/charts.py` | 4 Plotly charts | ✅ MODIFIED |
| `streamlit_app/api_client.py` | 7 client methods | ✅ MODIFIED |
| `streamlit_app/i18n/{en,es,fr,ar}.json` | 45+ i18n keys | ✅ MODIFIED |
| `streamlit_app/role_config.py` | Page 24 role access | ✅ MODIFIED |
| `tests/test_financial_*.py` | 3 test files (~62 tests) | ✅ EXISTS |
| `skills/02-work-planning/calculate-financial-roi/` | Financial skill | ❌ MISSING |
| `api/services/financial_service.py` | Service layer | ❌ MISSING (Session C) |
| `api/database/models.py` | ORM persistence | ❌ NOT EXTENDED (Session C) |
| `MASTER_PLAN.md` | Gap tracking | ❌ NOT UPDATED |

---

## Verification Checklist — Session B Exit Criteria

- [ ] `pytest --tb=short -q` → 2,775+ passing, 0 failures
- [ ] `pytest tests/test_financial_*.py -v` → all pass
- [ ] Page 24 loads: all 5 tabs render without error
- [ ] ROI Calculator: SAG Mill inputs → NPV + payback displayed
- [ ] Skill file exists: `skills/02-work-planning/calculate-financial-roi/CLAUDE.md`
- [ ] `agents/planning/skills.yaml` includes `calculate-financial-roi`
- [ ] MASTER_PLAN: GAP-W04 marked `[x]` DONE, all counts updated

---

## Tool Count Reference (After Session B)

| Agent | Before | After GAP-W04 |
|-------|--------|---------------|
| Orchestrator | 27 | 32 (+5) |
| Reliability | 48 | 49 (+1) |
| Planning | 79 | 83 (+4) |
| Spare Parts | 3 | 3 |
| **Total** | **~158** | **~163** |
