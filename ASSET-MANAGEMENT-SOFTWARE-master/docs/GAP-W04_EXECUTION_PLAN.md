# GAP-W04 Execution Plan — Financial Agent / ROI Tracking

> **Living document.** Check boxes as work completes. Any session can pick up where this left off.
> **Created:** 2026-03-11 | **Completed:** 2026-03-11 | **Status:** COMPLETE | **Sessions:** 2

## Context

The AMS platform lacks financial impact measurement, ROI calculation, and budget tracking. Workshop participants (2026-03-10) explicitly flagged this as critical for MVP:

- **Gonzalo:** "Falta un tema importante... la medición y el impacto financiero, la reducción de costos, el impacto del ROI"
- **Jose:** "Eso sería brutal. Imagínate poder transformar lo realizado en impacto financiero"
- **Jose:** "El tema financiero no está ahora mismo" — explicitly missing
- **Jorge:** Maintenance budgets = 80M USD/year. Key metric = "horas hombre ahorradas"

### What exists (REUSE)

| Component | File | Status |
|-----------|------|--------|
| LCC Engine | `tools/engines/lcc_engine.py` | Working, MCP tools registered |
| OCR Engine | `tools/engines/ocr_engine.py` | Working, MCP tools registered |
| Pareto Cost | `tools/engines/pareto_engine.py` | Working |
| Spare Parts ABC | `tools/engines/spare_parts_engine.py` | Working |
| LCC/OCR MCP tools | `agents/tool_wrappers/server.py` lines 119-120 | `calculate_lcc`, `compare_lcc_alternatives`, `calculate_ocr` in planning |
| LCC/OCR skills | `agents/planning/skills.yaml` lines 72-82 | Registered |
| KPI/Health/Reporting engines | `tools/engines/` | Operational only, no financial |

### What to build

| Component | File(s) | Type |
|-----------|---------|------|
| Financial schemas | `tools/models/schemas.py` | MODIFY |
| ROI engine | `tools/engines/roi_engine.py` | CREATE |
| Budget engine | `tools/engines/budget_engine.py` | CREATE |
| MCP tool wrappers | `agents/tool_wrappers/financial_tools.py` | CREATE |
| Skills (2) | `skills/04-cost-analysis/calculate-roi/`, `track-budget/` | CREATE |
| SessionState entities | `agents/orchestration/session_state.py` | MODIFY |
| API router | `api/routers/financial.py` | CREATE |
| Financial dashboard | `streamlit_app/pages/20_financial.py` | CREATE |
| Executive dashboard | `streamlit_app/pages/14_executive_dashboard.py` | MODIFY |
| Reporting integration | `tools/engines/reporting_engine.py` | MODIFY |
| Tests (3 new + 4 modify) | `tests/` | CREATE+MODIFY |

### SWMR Ownership

- `budget_items` → Planning agent
- `roi_calculations` → Orchestrator agent
- `financial_impacts` → Orchestrator agent

---

## Session 1: Foundation

### A. Data Models — `tools/models/schemas.py`

- [x] **A.1** Add enums: `FinancialCategory`, `BudgetStatus`, `ROIStatus`, `CurrencyCode`
- [x] **A.2** Add `BudgetItem` model
- [x] **A.3** Add `BudgetSummary` model
- [x] **A.4** Add `ROIInput` model
- [x] **A.5** Add `ROIResult` model
- [x] **A.6** Add `FinancialImpact` model
- [x] **A.7** Add `FinancialSummary` model
- [x] **A.8** Add `BudgetVarianceAlert` model
- [x] **A.9** Add `ManHourSavingsReport` model

### B. ROI Engine — `tools/engines/roi_engine.py`

- [x] **B.1** `ROIEngine.calculate_roi()` — NPV, payback, BCR, IRR, cumulative savings, recommendation
- [x] **B.2** `ROIEngine.compare_scenarios()` — sorted by NPV desc
- [x] **B.3** `ROIEngine.calculate_financial_impact()` — per-equipment cost rollup
- [x] **B.4** `ROIEngine.calculate_man_hours_saved()` — horas hombre ahorradas

### C. Budget Engine — `tools/engines/budget_engine.py`

- [x] **C.1** `BudgetEngine.track_budget()` — aggregate, variance, recommendations
- [x] **C.2** `BudgetEngine.detect_variance_alerts()` — WARNING/CRITICAL thresholds
- [x] **C.3** `BudgetEngine.generate_financial_summary()` — executive consolidation
- [x] **C.4** `BudgetEngine.forecast_budget()` — linear extrapolation

### D. MCP Tool Wrappers — `agents/tool_wrappers/financial_tools.py`

- [x] **D.1** Create 8 tools: `calculate_roi`, `compare_roi_scenarios`, `calculate_financial_impact`, `calculate_man_hours_saved`, `track_budget`, `detect_budget_alerts`, `generate_financial_summary`, `forecast_budget`
- [x] **D.2** Register in `server.py`: import + AGENT_TOOL_MAP updates

### E. Skills

- [x] **E.1** Create `skills/04-cost-analysis/calculate-roi/CLAUDE.md`
- [x] **E.2** Create `skills/04-cost-analysis/calculate-roi/evals/`
- [x] **E.3** Create `skills/04-cost-analysis/track-budget/CLAUDE.md`
- [x] **E.4** Create `skills/04-cost-analysis/track-budget/evals/`
- [x] **E.5** Register `calculate-roi` in `agents/orchestrator/skills.yaml`
- [x] **E.6** Register `track-budget` in `agents/planning/skills.yaml`

### J. SessionState

- [x] **J.1** Add 3 entity types to `ENTITY_OWNERSHIP`
- [x] **J.2** Add 3 property accessors

### L.1 Engine Registration

- [x] **L.1** Update `tools/engines/__init__.py`

### Verification

- [x] **V.1** `python -m pytest --tb=short -q` — 2,135+ pass, 0 fail

---

## Session 2: User-Facing Layer

### F. API Router — `api/routers/financial.py`

- [x] **F.1** Create 8 endpoints (POST /roi, /roi/compare, /budget/track, /budget/alerts, GET /summary/{plant_id}, POST /impact, /man-hours, /budget/forecast)
- [x] **F.2** Register in `api/main.py`

### G. Financial Dashboard — `streamlit_app/pages/24_financial.py` (page 24, not 20 — pages 20-23 already taken)

- [x] **G.1** Create page with 5 tabs (Budget, ROI Calculator, Cost Drivers, Man-Hours, Summary)
- [x] **G.2** Add 8 API client functions to `api_client.py`
- [x] **G.3** Add 4 chart functions to `components/charts.py` (budget_variance, roi_cumulative, cost_driver_pareto, man_hours_comparison)
- [x] **G.4** Add financial i18n keys to `en.json`, `es.json`, `fr.json`, `ar.json` (~45 keys each)

### H. Executive Dashboard — `pages/14_executive_dashboard.py`

- [x] **H.1** Add 6th tab: Financial (budget variance, cost drivers, ROI, man-hours)

### I. Reporting Integration — `reporting_engine.py`

- [x] **I.1** Add `financial_summary` param to `generate_monthly_kpi_report()` — Financial KPIs section
- [x] **I.2** Add `financial_summary` param to `generate_quarterly_review()` — Financial Performance section + recommendations
- [x] **I.3** Add `FINANCIAL_REVIEW` to `ReportType` enum + template sections

### K. Tests

- [x] **K.1** Create `tests/test_financial_engine.py` (~20 tests — ROI, budget, impact, man-hours, large-scale 80M)
- [x] **K.2** Create `tests/test_financial_schemas.py` (~10 tests — all 8 models + 4 enums)
- [x] **K.3** Create `tests/test_financial_tools.py` (~8 tests — all 8 MCP tools registered + callable)
- [x] **K.4** Updated `tests/test_session_state_extended.py` (Session 1)
- [x] **K.5** Update `tests/test_navigation.py` (page count 23→24, financial API methods, financial i18n)
- [x] **K.6** Updated `tests/test_agent_tool_access.py` (Session 1)
- [x] **K.7** Updated `tests/test_skills_v2.py` (Session 1)

### Verification

- [x] **V.2** Full test suite passes — **2,888 passed, 0 failures**
- [x] **V.3** `POST /financial/roi` returns valid response — NPV 2,015,407 USD, BCR 5.03, "Strong ROI"
- [x] **V.4** Streamlit page 24 — AST valid, 5 tabs (tab1-tab5), 6 API methods wired

### L.2 Documentation

- [x] **L.2** Update `MASTER_PLAN.md` (T-45 DONE, counts)
- [x] **L.3** Update `SKILL_MASTER_REGISTRY.md`
- [x] **L.4** Update `AGENT_REGISTRY.md`
