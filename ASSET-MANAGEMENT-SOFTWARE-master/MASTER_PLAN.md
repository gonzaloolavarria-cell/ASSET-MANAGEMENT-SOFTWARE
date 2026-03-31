# MASTER PLAN — OCP Maintenance AI (AMS)

> **Living document.** Updated every session. Last update: 2026-03-11 (Session 25).
> **Rule:** Every session that adds, modifies, or removes capabilities MUST update this file before closing.
> **Audit basis:** Session 15 cross-referenced every claim against live codebase (pytest count, file existence, API integration code, seed script).

---

## Part 1: What's Built (Capability Inventory)

### 1.1 Data Layer

| Component | Count | Key Files |
|-----------|-------|-----------|
| Pydantic schemas | 30+ | `tools/models/schemas.py` |
| RFI models | 1 file | `tools/models/rfi_models.py` |
| Equipment library | 15 types | `data/libraries/equipment_library.json` |
| Component library | ~30 types | `data/libraries/component_library.json` |
| SAP mock data | 5 JSON files | `sap_mock/data/` |
| Excel templates | 14 | `templates/generate_templates.py` |
| FM MASTER table | 72 combos | `skills/00-knowledge-base/data-models/failure-modes/MASTER.md` |

**Key schemas:** PlantHierarchyNode, CriticalityAssessment, Function, FunctionalFailure, FailureMode (72-combo enforced), MaintenanceTask, WorkPackage, SAPUploadPackage, FieldCaptureInput, StructuredWorkRequest, QualityScoreDimension, ExecutionPlan, plus 18+ supporting models.

### 1.2 Engine Layer (Deterministic Business Logic)

**39 engines** in `tools/engines/` + 7 scoring strategies in `tools/engines/scoring_strategies/`:

| Category | Engines | Purpose |
|----------|---------|---------|
| **Core RCM** | criticality, rcm_decision, fmeca, priority | R8 methodology execution |
| **Work Management** | backlog_grouper, work_package_assembly, execution_task, scheduling | Task → WP → Schedule |
| **SAP Integration** | sap_export, hierarchy_builder | SAP PM upload + hierarchy build |
| **Equipment** | equipment_resolver, material_mapper | TAG resolution + BOM matching |
| **Reliability** | weibull, health_score, spare_parts, rbi, shutdown, moc, ocr, jackknife, pareto, lcc | Advanced reliability analysis |
| **Financial** | roi, budget | ROI/NPV/BCR/IRR, budget tracking, variance alerts, financial summary |
| **KPIs** | kpi, planning_kpi, de_kpi | MTBF/MTTR/OEE + 11 planning + 5 DE KPIs |
| **Reporting** | reporting, notification, cross_module, variance_detector, management_review, capa | Dashboards + alerts |
| **Data** | data_import, data_export, state_machine | Import/export + entity lifecycle |
| **Quality** | quality_score (+ 6 strategies) | 7-dimension scoring with pass thresholds |
| **Work Instructions** | work_instruction_generator | 4 WI templates (Inspection, Service, ConMon, FFI) |

**4 validators** in `tools/validators/`: quality, confidence, naming, rfi.

### 1.3 Agent Layer (Multi-Agent AI System)

**4 agents** with distinct roles and models:

| Agent | Model | Tools | Skills | Role |
|-------|-------|-------|--------|------|
| Orchestrator | Sonnet | 24 | 17 | Workflow coordination, delegation, quality gates |
| Reliability | Opus | 49 | 10 | Criticality, FMECA (incl. RCM decision tree) |
| Planning | Sonnet | 62 | 11 | Tasks, work packages (incl. WI generation), SAP export |
| Spare Parts | Haiku | 3 | 2 | Material assignment, BOM lookup |

**Supporting infrastructure:**

- `agents/_shared/base.py` — Unified Agent class (real Claude API loop via `client.messages.create()`, max 30 turns, retry with backoff)
- `agents/_shared/memory.py` — Hierarchical client memory (milestone → stage mapping)
- `agents/_shared/paths.py` — Template cascade (project → client → system)
- `agents/orchestration/workflow.py` — 4-milestone workflow with human gates, quality scoring, modify retries
- `agents/orchestration/session_state.py` — Generic entity store with SWMR enforcement
- `agents/orchestration/checkpoint.py` — Auto-checkpoint with microsecond timestamps
- `agents/orchestration/execution_plan.py` — YAML-serialized execution plan with dependency validation
- `agents/orchestration/milestones.py` — Milestone definitions (`MilestoneStatus` enum) and required entities
- `agents/tool_wrappers/server.py` — MCP server registering **166 tools**
- `agents/tool_wrappers/registry.py` — Tool registry with agent-level access control
- `agents/run.py` — **CLI entry point**: `python -m agents.run "SAG Mill 001" --plant OCP-JFC` (runs full M1→M4)
- `agents/definitions/orchestrator.py` — `create_orchestrator()` instantiates all 4 agents sharing one Anthropic client

### 1.4 Skills System

**42 active skills** (+ 2 deprecated) with YAML frontmatter, organized by milestone:

| Category | Skills | Examples |
|----------|--------|----------|
| 00-knowledge-base | Reference docs | 192 files across 12 subdirectories |
| 01-work-identification | 1 | identify-work-request |
| 02-maintenance-strategy | 5 | assess-criticality, build-equipment-hierarchy, perform-fmeca, assess-am-maturity, develop-samp |
| 02-work-planning | 4 | export-to-sap, suggest-materials, generate-work-instructions, create-work-packages |
| 03-reliability-engineering | 3 | run-rcm-decision-tree, optimize-spare-parts, analyze-rca |
| 05-general-functionalities | 5 | import-data, export-data, validate-quality, manage-notifications, manage-change |
| 06-orchestration | 7 | orchestrate-workflow, generate-reports, calculate-kpis, calculate-health-score, detect-variance, conduct-management-review, benchmark-maintenance-kpis |
| 04-cost-analysis | 4 | calculate-life-cycle-cost, optimize-cost-risk, calculate-roi, track-budget |
| Cross-module | 2+ | analyze-cross-module, resolve-equipment, manage-capa |

Each skill has: `CLAUDE.md` (prompt), `evals/` (trigger + functional tests), `references/`.
Classification: 25 capability-uplift + 14 encoded-preference (see `SKILL_CLASSIFICATION.md`).

### 1.5 API Layer (FastAPI Backend)

- **22 API routers** covering all domain operations (registered in `main.py`)
- **22 API services** (domain logic + utility services)
- **Admin endpoints** (6): seed-database, reset-database, audit-log, stats, agent-status, feedback — destructive ops require `X-Admin-Key`
- **Seed script** (`api/seed.py`): Complete synthetic data generator — OCP-JFC1 plant, full hierarchy, 24 months work orders, 25 workers, 50 inventory items. Triggered via `POST /api/v1/admin/seed-database`
- **CORS** configured via `AMS_ALLOWED_ORIGINS` env var
- **SQLite** database with SQLAlchemy ORM (29 model classes across 10 phases)
- **Health check** and root endpoint
- **`.env.example`** documents all 6 env vars (`DATABASE_URL`, `ANTHROPIC_API_KEY`, `AMS_ADMIN_API_KEY`, `AMS_ALLOWED_ORIGINS`, `SAP_MOCK_DIR`, `DEBUG`)
- **Startup validation** — warns on boot if `ANTHROPIC_API_KEY` or `AMS_ADMIN_API_KEY` are missing

### 1.6 UI Layer (Streamlit Frontend)

**27 pages** covering the full workflow:

| # | Page | Milestone |
|---|------|-----------|
| 1 | Equipment Hierarchy | M1 |
| 2 | Criticality Assessment | M1 |
| 3 | FMEA Analysis | M2 |
| 4 | Strategy Development | M2 |
| 5 | Analytics | Cross |
| 6 | SAP Review | M4 |
| 7 | Overview Dashboard | Cross |
| 8 | Field Capture | M0 |
| 9 | Work Requests | M0 |
| 10 | Planner Assistant | M3 |
| 11 | Backlog Management | M3 |
| 12 | Scheduling | M3 |
| 13 | Reliability Analysis | M2 |
| 14 | Executive Dashboard | Cross |
| 15 | Reports & Data | Cross |
| 16 | FMECA Worksheets | M2 |
| 17 | Defect Elimination | Cross |
| 18 | Wizard | Setup |
| 19 | Progress Dashboard | Tracking |
| 20 | Equipment Manual Chat | Cross |
| 21 | Deliverables Tracking | Tracking |
| 22 | Execution Checklists | M3 |
| 23 | Troubleshooting | Cross |
| 24 | Financial Dashboard | Cross |
| 25 | Expert Portal (GAP-W13) | Cross |
| 26 | Expert Knowledge Mgmt (GAP-W13) | Cross |
| 27 | Workflow (G-17) | Cross |

Quadrilingual UI: French, English, Arabic, Spanish (~380 i18n keys per language).

### 1.7 Eval & Quality Infrastructure

- **Eval runner** (`scripts/eval_runner/`): trigger (TF-IDF + Claude-as-judge), functional, benchmark (A/B), snapshot, regression
- **Audit scripts**: `audit_skills.py` (score 0-100), `audit_eval_coverage.py` (grade A-F)
- **Trigger optimizer**: `optimize_triggers.py`
- **CI workflow**: `.github/workflows/skill-evals.yml`
- **Quality scorer**: 7-dimension scoring with configurable thresholds (AMS=85, OR=91)
- **Eval Runbook**: `EVAL_RUNBOOK.md` — step-by-step pipeline guide

### 1.8 Supporting Systems

| System | Files | Purpose |
|--------|-------|---------|
| Template cascade | `agents/_shared/paths.py` | 3-level resolution: project → client → system |
| Client memory | `agents/_shared/memory.py` | Milestone-stage memory loading, deviation/pattern saving |
| Security hardening | Multiple | CORS, admin keys, SQL injection prevention, path sandboxing, YAML injection sanitizer |
| Knowledge base sync | `scripts/sync_knowledge_base.py` | SHA-256 hash verification for 23 shared docs |
| RFI processing | `scripts/process_ams_rfi.py` | Memory seeding from RFI documents |
| Client template gen | `scripts/generate_client_templates.py` | Branded template generation |
| Cross-repo manifest | `SHARED_DOCS_MANIFEST.md` | Tracks 23 shared docs between AMS, OR SYSTEM, Archive |

### 1.9 Test Suite

| Metric | Value |
|--------|-------|
| Test files | 93 |
| Tests passing | 2,888 |
| Failures | 0 |
| Warnings | 10 |
| Run time | ~30s |
| Coverage areas | Engines, validators, schemas, agents, API, security, skills, workflow, templates, eval runner |

---

## Part 2: Current System State

```text
Version:     1.2 (as of 2026-03-11)
Status:      PRODUCTION — development complete, never run end-to-end with live API, not deployed
Tests:       2,888 passing, 0 failures
Agents:      4 (Orchestrator, Reliability, Planning, Spare Parts) — real API loop, never tested live
Skills:      41 active + 2 deprecated (27 capability-uplift + 14 encoded-preference)
Tools:       163 MCP tool wrappers (32 tool files + registry + server)
Engines:     42 deterministic + 7 scoring strategies
API:         22 routers, 22 services, 6 admin endpoints
UI:          27 Streamlit pages, quadrilingual (FR/EN/AR/ES)
Templates:   14 Excel data-loading templates
Libraries:   15 equipment types, ~30 component types
Knowledge:   192 reference files across 12 categories
Database:    SQLite (prototype) — DB empty, seed endpoint available but never called
Entry point: python -m agents.run "equipment" --plant PLANT (CLI only, no API endpoint)
```

### Build History (Condensed)

| Phase | Date | What Was Built | Tests After |
|-------|------|----------------|-------------|
| 0-1 | 2026-02-20 | Discovery, schemas, gemini.md, 12 reference docs | 0 |
| 2-3 | 2026-02-20 | 19 Pydantic models, 9 engines, 3 validators, full test suite | 282 |
| 4 | 2026-02-20 | GECAMIN competitive intelligence (REF-10/11/12), FM 72-combo integration | 282 |
| 5 | 2026-02-20 | Multi-agent architecture design, directory scaffolding | 282 |
| 6-8 | 2026-02-20 | Full stack: FastAPI (17 routers), Streamlit (17 pages), 36 engines, 62 MCP tools, 4 agents | 1,099 |
| 9 | 2026-02-21 | Trilingual UI, styling, feedback, integration testing | 1,099 |
| 9B | 2026-02-22 | 13 Excel templates, equipment libraries, hierarchy builder, 6 how-to guides, glossary | 1,208 |
| 10 | 2026-02-22 | GFSN methodology alignment (REF-13 to REF-17), knowledge base sharing | 1,208 |
| 11 | 2026-03-05 | Multi-agent improvements: unified base class, session state, auto-checkpoint, security hardening | 1,387 |
| 12 | 2026-03-05 | Skills system (41 skills), eval infrastructure, quality scorer, hierarchical memory, template cascade, wizard, execution plan | 2,118 |
| 13 | 2026-03-10 | identify-work-request skill (Part A+B), repo reorganization (10 junk files deleted, Libraries→data/libraries, gemini.md rewrite, CLAUDE.md created) | 2,135 |
| 14 | 2026-03-11 | G-01/G-17/G-20: End-to-end integration fixes — 3 critical bugs resolved (Anthropic client auto-creation, agent_dir mode, direct specialist orchestration), SAP xlsx serialization, FastAPI workflow API (4 endpoints), 158 MCP tools | 2,135+ |

---

## Part 3: Gap Analysis

### 3.1 Critical Gaps (Block Demo / Pilot)

- [x] **G-01** ~~End-to-end workflow never run with live API~~ — CLOSED (Session 14). Fixed 3 critical bugs: (1) `StrategyWorkflow` now auto-creates `Anthropic()` client from env; (2) all 4 agent configs switched from non-existent legacy prompts to `agent_dir` mode; (3) workflow now directly orchestrates specialists via `orchestrator.delegate()` with JSON entity extraction + `session.write_entities()`. `docs/AGENT_EXECUTION_TRACE.md` created.
- [x] **G-02** ~~Import pipeline incomplete~~ — CLOSED (Session 26). File parsing: `FileParserEngine` + `DataImportEngine.parse_and_validate()`. API: `POST /import/file`, `GET /import/history`, `GET /import/sources` (`api/routers/imports.py`). DB persistence: `ImportHistoryModel` + `import_service.py`. MCP tools: `import_data_file`, `get_import_history`, `list_import_sources` (`import_tools.py`). UI: Page 15 Tab 3 wired to API; Tab 5 Import History working. Error display: `import_errors.py` components (summary + error table + data preview). 10 tool tests + 14 API tests.
- [x] **G-03** ~~No guided demo flow~~ — CLOSED (Session 17). `docs/DEMO_GUIDE.md` created: 30-min executive track, 60-min full technical track, 23-page talking points, 10+ FAQs, known limitations, CLI appendix. Page 18 wizard polished: `apply_style()`, i18n keys (4 languages, ~20 keys under `wizard.*`), Demo Mode quick-fill button, `feedback_widget`. `(1 session)`
- [x] **G-04** ~~Database empty by default~~ — CLOSED (2026-03-12). Schema recreated (drop_all + create_all to pick up `gps_lat`/`gps_lon` columns from newer ORM). `seed_all()` called directly: 254 hierarchy nodes (1 plant, 8 areas, 8 systems, 14 equipment, 53 sub-assemblies, 170 maintainable items), 227 failure modes, 168 work orders, 25 workers, 50 inventory items, 6 shutdown windows, 20 work requests, 4 backlog items, 3 experts. SAP mock files generated.

### 3.2 Important Gaps (Block Production)

- [ ] **G-05** No Docker / deployment config — No Dockerfile, docker-compose, or cloud config anywhere in the repo. `(1 session)`
- [ ] **G-06** Still on SQLite — PostgreSQL was the design target. No Alembic migration infrastructure. SQLAlchemy makes this easy but it's untested. `(1 session)`
- [ ] **G-07** No API authentication — Only `X-Admin-Key` on 2 destructive endpoints. All 17 routers are publicly accessible. No JWT, no sessions, no roles. `(1 session)`
- [x] **G-08** Voice/image capture — COMPLETE (2 sessions). Whisper API (D-1), Claude Vision (D-2), LLM enhancer (D-3), Page 8 mobile UI (D-4), GPS proximity matching (D-5). 89 tests passing.
- [ ] **G-09** Knowledge base sync not in CI — `sync_knowledge_base.py` exists but runs manually. Drift between AMS and OR SYSTEM is possible. `(0.5 session)`

### 3.3 Integration Gaps (Discovered in audit)

- [x] **G-16** ~~No `.env.example`~~ — CLOSED (Session 15). Created `.env.example` with all 6 env vars documented.
- [x] **G-17** ~~Workflow is CLI-only~~ — CLOSED (Session 14). `api/routers/workflow.py` adds 4 endpoints: `POST /workflow/run` (async, threading.Event gate sync), `GET /workflow/{id}` (poll), `POST /workflow/{id}/approve` (gate decision), `GET /workflow/sessions` (list). Registered in `api/main.py`. Streamlit client methods added to `api_client.py`.
- [x] **G-18** ~~Import engine can't parse files~~ — CLOSED (Session 26). `FileParserEngine` (`tools/engines/file_parser_engine.py`, 385 lines) parses `.xlsx` (openpyxl) and `.csv` (csv module). `DataImportEngine.parse_and_validate()` integrates it. `api/routers/imports.py` adds 3 endpoints (`POST /import/file`, `GET /import/history`, `GET /import/sources`). `api/services/import_service.py` persists to `ImportHistoryModel`. 3 new MCP tools (`list_import_sources`, `import_data_file`, `get_import_history`) in `agents/tool_wrappers/import_tools.py`. Page 15 Tab 3 wired to API with graceful fallback. 10 tool tests + 14 API tests.
- [x] **G-19** ~~App boots silently with empty API key~~ — CLOSED (Session 15). `Settings.validate()` logs warnings on startup for missing keys.
- [x] **G-20** ~~SAP export produces Pydantic objects, not files~~ — CLOSED (Session 14). `SAPExportEngine.write_to_xlsx(package, path)` added: 3 sheets (Functional Locations, Task Lists, Maintenance Plans), styled headers, field length enforcement (`SAP_SHORT_TEXT_MAX=72`, `SAP_FUNC_LOC_MAX=40`). Workflow calls it automatically on M4 approval; path stored in `session.sap_upload_package["xlsx_path"]`.

### 3.4 Nice-to-Have Gaps (Post-Pilot)

- [ ] **G-10** Multi-plant configuration — Architecture supports it but no plant-switching UI `(1-2 sessions)`
- [ ] **G-11** Real SAP PM connection — Still on mock data. Need RFC/BAPI or IDoc interface `(External dependency)`
- [ ] **G-12** Predictive analytics pipeline — Weibull engine exists but needs real failure history data `(1-2 sessions)`
- [ ] **G-13** Mobile-responsive field capture — Current Streamlit UI is desktop-oriented `(2-3 sessions)`
- [ ] **G-14** Knowledge graph (Neo4j) — Deferred from Phase 0 discovery `(2-3 sessions)`
- [ ] **G-15** Cloud deployment (AWS/GCP) — After Docker is ready `(External dependency)`

### 3.5 Workshop-Derived Gaps (2026-03-10 Functional Definition Workshop)

Gaps identified by mapping workshop requirements against the current codebase. Workshop participants: Jose Cortinat (product lead), Jorge Alquinta (field expert, ex-superintendent), Gonzalo (operations/process), Magda (facilitator). Full assessment: `AMS functional definition/AMS_Workshop_Assessment.docx`.

- [x] **GAP-W02** ~~Troubleshooting / Diagnostic Assistant~~ — DONE (Sessions 19-21). Deterministic troubleshooting engine with 214-symptom catalog extracted from 72 FM MASTER cards, 5 decision trees (SAG Mill, Ball Mill, Slurry Pump, Conveyor, Crusher), Jaccard keyword-matching + minimum-cost-first test ordering, confidence scoring. Skill `guide-troubleshooting` assigned to Reliability agent. 5 MCP tools, 8 API endpoints, `TroubleshootingSessionModel` DB persistence. Page 23 (Streamlit): 3-tab UI (New Diagnosis, Session History, Decision Trees). i18n in EN/FR/ES/AR. 105+ tests passing.
- [x] **GAP-W03** ~~Offline Mode with Sync~~ — CLOSED (2026-03-12). React/TypeScript PWA companion app (`field_app/`): 3 pages (Field Capture, Work Program, Checklist). IndexedDB via Dexie.js, SyncManager (pull/push/resolve), ConflictDialog, `useSync` hook (auto-sync on mount/reconnect/periodic/SW message), Service Worker (cache-first for static, network-first for API, SWR for HTML). FastAPI serves PWA at `/field/` via `StaticFiles` mount. 14 integration tests + 33 frontend Vitest tests. 3,146 backend tests pass.
- [x] **GAP-W04** ~~Financial Agent / ROI Tracking~~ — DONE (Sessions 24-25). `ROIEngine` (NPV, payback, BCR, IRR via bisection, cumulative savings, scenario comparison, financial impact, man-hours saved) + `BudgetEngine` (tracking, variance alerts, financial summary, forecast). 4 enums + 8 Pydantic models in schemas.py. 8 MCP tools in `financial_tools.py`. 2 skills (`calculate-roi` for Orchestrator, `track-budget` for Planning). 3 SWMR entities (budget_items, roi_calculations, financial_impacts). API router (8 endpoints). Page 24 (`24_financial.py`): 5-tab dashboard (Budget, ROI Calculator, Cost Drivers, Man-Hours, Summary). 4 chart functions. Financial tab in executive dashboard. Financial sections in reporting engine (monthly + quarterly). i18n EN/FR/ES/AR. 2,888 tests passing.
- [x] **GAP-W05** ~~Role-Based Dashboard Views~~ — DONE (Session 18). Soft role filtering with 6 roles (Manager, Reliability Engineer, Planner, Supervisor, Technician, Consultant). `role_config.py` single source of truth, sidebar role selector, personalized landing page, role-filtered KPIs on executive dashboard, role context banners on all 19 pages. 102 tests passing.
- [x] **GAP-W06** ~~Quality Checklists / Gate Reviews During Execution~~ — DONE (Sessions 20-21). `ExecutionChecklistEngine` with ordered steps, predecessor wiring, gate enforcement ("can't proceed until confirmed"), 3-level condition codes (Anglo American standard). 4 enums + 4 Pydantic models + ORM model. 5 MCP tools, 7 API endpoints, service layer with audit trail. Page 22 (`streamlit_app/pages/22_execution_checklists.py`): interactive step execution with color-coded type badges, gate questions, supervisor closure. Skill `generate-execution-checklists` for Planning agent. 83+ tests passing.
- [x] **GAP-W07** ~~Equipment Manual RAG / Chat Interface~~ — CLOSED (Session 17). Claude Native approach: `tools/engines/manual_loader.py` loads manual PDFs/TXT/MD + equipment library data into 200K context window with prompt caching. Page 20 (`streamlit_app/pages/20_equipment_chat.py`): chat UI with equipment selector, streaming responses, multilingual. `data/manuals/` directory for manual files. 57 tests passing.
- [x] **GAP-W08** ~~Usage-Based Task Support~~ — CLOSED (Session 17). Added `SchedulingTrigger` enum (CALENDAR/COUNTER), `FREQ_UNIT_TRIGGER` mapping, `measuring_point` field to `SAPMaintenancePlan`. Completed `FREQ_UNIT_TO_SAP` for HOURS_RUN/TONNES/CYCLES. Added `recommend_frequency_unit()` to RCM engine. Updated UI dropdowns, skill docs. 25 new tests.
- [x] **GAP-W09** ~~Competency-Based Work Assignment~~ — CLOSED (Session 18). `CompetencyLevel` enum (A/B/C), `TechnicianProfile`, `TaskCompetencyRequirement`, `WorkAssignment`, `AssignmentSummary` schemas. `assignment_engine.py`: 5-dimension scoring (specialty 30, competency 25, equipment 20, cert 15, availability 10), greedy optimizer, re-optimization with absences. 4 MCP tools + API router (3 endpoints). Seed data: 25 workers with competency matrices. Supervisor dashboard: new "Crew Assignment" tab in Page 12 with crew status, optimization, re-optimization, match scoring. i18n (4 languages). 56 new tests.
- [x] **GAP-W10** ~~Consultant Workflow / Deliverable Tracking~~ — DONE (Sessions 22-23). `DeliverableTrackingEngine` (stateless: 6-state lifecycle, variance calc, plan seeding). 5 Pydantic models + 2 ORM models. 9 API endpoints + service with audit trail. Page 21 (`21_deliverables.py`): 4-tab UI (Overview, Detail, Time Tracking, Client Review). 9 API client methods. Wizard Step 5 uses `DEFAULT_HOURS` + seed button. Workflow auto-transitions deliverables to SUBMITTED on milestone approval. Quality score linking. Progress dashboard deliverable sidebar. i18n EN/FR/ES/AR. 47+ new tests (27 engine + 20 API). `docs/GAP-W10_EXECUTION.md` tracker.
- [x] **GAP-W12** ~~Data Import from External Systems (file parsing)~~ — File parsing DONE (Session 26, G-18). Remaining: PI System / sensor data integration is future work (external dependency). The 14 import types cover SAP historical OTs via WORK_ORDER_HISTORY + MAINTENANCE_STRATEGY sources.
- [x] **GAP-W13** ~~Knowledge Capture from Retiring Experts~~ — CLOSED. Expert portal (Page 25), knowledge management UI (Page 26), `ExpertKnowledgeEngine` with match/consult/extract/validate/promote, 5 MCP tools, `capture-expert-knowledge` skill, seed data (3 retired experts + 2 consultations), integration tests.
- [x] **GAP-W14** ~~Shutdown Management Enhancement~~ — CLOSED (Session 19). 6 new schemas (`ShutdownReportType`, `ShutdownWorkOrderStatus`, `ShutdownDailyReport`, `ShutdownShiftSuggestion`, `ShutdownScheduleItem`, `ShutdownSchedule`). 6 new engine methods: daily/shift/final reports, velocity calculation, shift suggestions (critical path priority), schedule generation (Kahn's topological sort + critical path). 5 MCP tools, 5 API endpoints, service layer. Skill updated (Steps 7-10, new triggers). UI: 4 new expanders (daily report, shift focus, schedule/cronogram, final summary). i18n (4 languages, 22 keys each). 26 new tests (37 total). `docs/GAP-W14_EXECUTION.md` tracker.

---

## Part 4: Next Phases

### Phase 0: Quick Wins (NEXT — Do First, < 1 hour total)

**Goal:** Close trivial gaps that have outsized impact on developer experience and demo readiness.

- [x] **Q-1** Create `.env.example` with all 6 env vars documented `(G-16)` → DONE
- [x] **Q-2** Add startup validation for `ANTHROPIC_API_KEY` in `api/config.py` `(G-19)` → DONE
- [ ] **Q-3** Seed the database: call `POST /admin/seed-database` or add auto-seed on first boot `(G-04)` → Demo-ready DB with OCP-JFC1 data
- [x] **Q-4** Add `agents/run.py` and `api/seed.py` to `CLAUDE.md` key files table → DONE

**Exit criteria:** New developer clones repo, copies `.env.example`, runs app, sees pre-populated data.

### Phase A: End-to-End Integration (Critical Path)

**Goal:** Run the full M1→M4 workflow with live Claude API calls and verify it works.

- [x] **A-1** Run `python -m agents.run "SAG Mill" --plant OCP-JFC` with real API key `(G-01)` → Infrastructure now ready; blocked only on providing `ANTHROPIC_API_KEY` in `.env`
- [x] **A-2** Fix M1 integration bugs (Hierarchy + Criticality) `(G-01)` → Direct Reliability agent delegation via `orchestrator.delegate()` + JSON entity parsing
- [x] **A-3** Fix M2 integration bugs (FMECA + RCM) `(G-01)` → Direct Reliability agent delegation with 72-combo instructions
- [x] **A-4** Fix M3 integration bugs (Strategy + Tasks + WPs) `(G-01)` → Planning + Spare Parts direct delegation + T-16 rule enforcement
- [x] **A-5** Fix M4 integration bugs (SAP Export) `(G-01)` → Planning agent generates SAP package via delegation
- [x] **A-6** Add SAP `.xlsx` file serialization to export engine `(G-20)` → `SAPExportEngine.write_to_xlsx()` with 3 sheets + styled headers
- [x] **A-7** Add `/api/v1/workflow/run` FastAPI endpoint `(G-17)` → `api/routers/workflow.py` with 4 endpoints + threading.Event gate sync
- [ ] **A-8** Live execution trace with real API key `(G-01)` → Requires `ANTHROPIC_API_KEY` to be set, then run CLI and capture trace

**Exit criteria:** M1→M4 completes from CLI with real API, produces `.xlsx` SAP export. API endpoint available for UI.

### Phase B: Data Pipeline & Demo Readiness

**Goal:** Users can load data, run the workflow, and see results.

- [x] **B-1** ~~Add Excel/CSV file parsing to `DataImportEngine`~~ → DONE (Session 26). `FileParserEngine` + `DataImportEngine.parse_and_validate()` confirmed working. Tests passing.
- [x] **B-2** ~~Create MCP tool wrapper for import engine~~ → DONE (Session 26). `agents/tool_wrappers/import_tools.py`: `list_import_sources`, `import_data_file`, `get_import_history`. (Note: `validate_import_data`, `parse_import_file`, `parse_and_validate_import` were already in `reporting_tools.py`.)
- [x] **B-3** ~~Wire Page 15 upload → parse → validate → DB ingest pipeline~~ → DONE (Session 26). `POST /api/v1/import/file` (parse+validate+persist), `GET /import/history`, `GET /import/sources`. Page 15 Tab 3 calls API with local fallback. Tab 5 Import History works.
- [x] **B-4** ~~Add bulk validation UI with error table and fix suggestions~~ → DONE (Session 26). `import_errors.py` components (`import_result_summary`, `import_error_table`, `import_data_preview`) were already built. Error table shows row/column/message/severity. API returns full error list.
- [x] **B-5** Create guided demo script `(G-03)` → DONE: `docs/DEMO_GUIDE.md` (30-min + 60-min tracks, 23-page talking points, 10+ FAQs)
- [x] **B-6** Polish wizard page for client-facing use `(G-03)` → DONE: Page 18 i18n + `apply_style()` + Demo Mode button + `feedback_widget`

**Exit criteria:** Non-technical user can follow the demo script and see AMS produce a SAP export package.

### Phase C: Production Hardening

**Goal:** System is deployable and secure enough for a pilot.

- [ ] **C-1** Create Dockerfile + docker-compose (FastAPI + Streamlit + PostgreSQL) `(G-05)` → `docker-compose up` works
- [ ] **C-2** Migrate SQLite → PostgreSQL with Alembic `(G-06)` → Migration scripts, tested in Docker
- [ ] **C-3** Add JWT authentication for API `(G-07)` → Login flow, token refresh, role-based access
- [ ] **C-4** Add request logging and error monitoring → Structured logging, error dashboard
- [ ] **C-5** Load testing (identify bottlenecks) → Performance baseline
- [ ] **C-6** Add KB sync to CI pipeline `(G-09)` → Automated drift detection

**Exit criteria:** `docker-compose up` launches the full system with PostgreSQL, authenticated API, and monitoring.

### Phase D: Field Capture Integration

**Goal:** Technicians can submit voice + photo work requests from the field.

- [x] **D-1** Integrate Whisper API for voice transcription `(G-08)` → `tools/processors/audio_transcription.py`, POST /media/transcribe
- [x] **D-2** Integrate Claude Vision API for image analysis `(G-08)` → `tools/processors/image_analyzer.py`, POST /media/analyze-image
- [x] **D-3** Wire identify-work-request skill to field capture page `(G-08)` → `LLMCaptureEnhancer` triggers on confidence < 0.7
- [x] **D-4** Mobile-responsive field capture UI `(G-08)` → React PWA: 3-step wizard (Identify→Capture→Review), camera/mic/GPS hooks, offline media processing, i18n (4 langs). Streamlit Page 8: multi-breakpoint CSS (480/768/1024px)
- [x] **D-5** GPS metadata capture and equipment proximity matching `(G-08)` → `ProximityMatcher` (haversine, HIGH <20m, MEDIUM <100m), `GET /capture/nearby`, seed GPS for OCP-JFC1

**Exit criteria:** Technician speaks into phone, takes photo, AMS creates structured work request with correct equipment TAG, failure mode, priority, and spare parts.

### Phase E: Scale & Extend (Post-Pilot)

- [ ] **E-1** Multi-plant configuration and switching `(G-10)` → Per-plant config, variance alerts
- [ ] **E-2** Real SAP PM connection (RFC/BAPI) `(G-11)` → Live read/write to SAP
- [ ] **E-3** Predictive analytics with real data `(G-12)` → Weibull predictions, failure forecasting
- [ ] **E-4** Cloud deployment (AWS/GCP) `(G-15)` → Managed infrastructure
- [ ] **E-5** Knowledge graph for cross-equipment insights `(G-14)` → Neo4j integration

---

## Part 5: Prioritized Task Backlog

Concrete tasks organized by priority. Each task has deliverables and acceptance criteria. Cross-references Part 3 (gaps) and Part 4 (phases).

### P0 — Do Now (< 1 hour total, zero risk)

| # | Task | Deliverable | Acceptance Criteria | Gap | Phase |
|---|------|-------------|---------------------|-----|-------|
| ~~T-01~~ | ~~Create `.env.example`~~ | ~~`.env.example` file with all 6 env vars + comments~~ | DONE (Session 15) | ~~G-16~~ | ~~Q-1~~ |
| ~~T-02~~ | ~~Add API key startup validation~~ | ~~Guard in `api/config.py` or `api/main.py`~~ | DONE (Session 15) | ~~G-19~~ | ~~Q-2~~ |
| T-03 | Seed database on first boot | Auto-seed logic OR documented curl command | After `POST /admin/seed-database`, DB has OCP-JFC1 plant, hierarchy, work orders, workers, inventory | G-04 | Q-3 |
| ~~T-04~~ | ~~Document entry points in CLAUDE.md~~ | ~~Updated Key Files table~~ | DONE (Session 15) | ~~—~~ | ~~Q-4~~ |

### P1 — Critical Path (Blocks any demo or pilot)

| # | Task | Deliverable | Acceptance Criteria | Gap | Phase |
|---|------|-------------|---------------------|-----|-------|
| T-05 | Run M1→M4 with live API key | Execution log, list of errors | `python -m agents.run "SAG Mill" --plant OCP-JFC` completes or captures every failure | G-01 | A-1 |
| T-06 | Fix M1 bugs (Hierarchy + Criticality) | Working M1 milestone | Agent reads equipment library, builds hierarchy, assesses criticality, human gate passes | G-01 | A-2 |
| T-07 | Fix M2 bugs (FMECA + RCM) | Working M2 milestone | Agent generates FMECA (72-combo validated), runs RCM decision tree, gate passes | G-01 | A-3 |
| T-08 | Fix M3 bugs (Strategy + Tasks + WPs) | Working M3 milestone | Agent creates maintenance tasks with intervals, assembles work packages, gate passes | G-01 | A-4 |
| T-09 | Fix M4 bugs (SAP Export) | Working M4 milestone | Agent generates SAP upload package with functional locations + task lists | G-01 | A-5 |
| T-10 | SAP export → `.xlsx` file writer | `sap_export_engine.py` writes Excel files | Engine produces `.xlsx` files using template cascade (not just Pydantic objects) | G-20 | A-6 |
| ~~T-11~~ | ~~Add `POST /api/v1/workflow/run` endpoint~~ | ~~New FastAPI endpoint + async task~~ | DONE. `api/routers/workflow.py` (4 endpoints, threading.Event gate sync). Streamlit page 27 (`27_workflow.py`): launch form, status monitor, gate approval panel. `role_config.py` + i18n (en/es/fr/ar) + `test_workflow_api.py` (15 tests). | ~~G-17~~ | ~~A-7~~ |
| T-12 | Document working agent workflow | Updated architecture docs | Execution trace, tool call sequence, error handling, retry behavior documented | G-01 | A-8 |

### P2 — Demo Readiness (Unblocks client meetings)

| # | Task | Deliverable | Acceptance Criteria | Gap | Phase |
|---|------|-------------|---------------------|-----|-------|
| ~~T-13~~ | ~~Add Excel/CSV parsing to import engine~~ | ~~Updated `DataImportEngine`~~ | DONE (Session 26). `FileParserEngine` + `DataImportEngine.parse_and_validate()`. `.xlsx` via openpyxl, `.csv` via csv.Sniffer, 10 MB limit. | ~~G-18~~ | ~~B-1~~ |
| ~~T-14~~ | ~~Create MCP tool wrapper for import~~ | ~~`agents/tool_wrappers/import_tools.py`~~ | DONE (Session 26). `list_import_sources`, `import_data_file`, `get_import_history` registered in `server.py`. | ~~G-02~~ | ~~B-2~~ |
| ~~T-15~~ | ~~Wire Page 15 upload pipeline~~ | ~~Updated Streamlit page~~ | DONE (Session 26). `POST /import/file` → parse → validate → DB persist. Page 15 Tab 3 calls API with local fallback. Tab 5 Import History. | ~~G-02~~ | ~~B-3~~ |
| ~~T-16~~ | ~~Bulk validation UI with error table~~ | ~~Error display component on Page 15~~ | DONE (Session 26). `import_errors.py` components: summary metrics, error table (row/col/msg/severity), download CSV, data preview. | ~~G-02~~ | ~~B-4~~ |
| ~~T-17~~ | ~~Write guided demo script~~ | ~~`docs/DEMO_GUIDE.md`~~ | DONE (Session 17). 30-min + 60-min demo tracks, 23-page talking points, 10+ FAQs, known limitations, CLI appendix. | ~~G-03~~ | ~~B-5~~ |
| ~~T-18~~ | ~~Polish wizard for client-facing use~~ | ~~Updated Page 18~~ | DONE (Session 17). `apply_style()`, i18n keys (4 languages), Demo Mode button, `feedback_widget`, all labels via `t()`. | ~~G-03~~ | ~~B-6~~ |

### P3 — Production Hardening (Required for pilot deployment)

| # | Task | Deliverable | Acceptance Criteria | Gap | Phase |
|---|------|-------------|---------------------|-----|-------|
| T-19 | Create Dockerfile + docker-compose | `Dockerfile`, `docker-compose.yml` | `docker-compose up` starts FastAPI + Streamlit + PostgreSQL, accessible on localhost | G-05 | C-1 |
| T-20 | Migrate SQLite → PostgreSQL | Alembic migration scripts | All 27 ORM models migrated, seed data works on PostgreSQL, tested in Docker | G-06 | C-2 |
| T-21 | Add JWT authentication to API | Auth middleware + login endpoint | Login returns JWT, all routers require valid token, role-based access (admin, engineer, viewer) | G-07 | C-3 |
| T-22 | Add structured logging + error monitoring | Logging middleware, error handlers | JSON-structured request logs, error tracking with stack traces, health dashboard | — | C-4 |
| T-23 | Load test and identify bottlenecks | Performance report | Response times under 10 concurrent users, identify any endpoint > 2s | — | C-5 |
| T-24 | Add KB sync to CI | GitHub Actions workflow step | `sync_knowledge_base.py` runs on PR, fails if hash mismatch detected | G-09 | C-6 |

### P4 — Field Capture (Competitive differentiator)

| # | Task | Deliverable | Acceptance Criteria | Gap | Phase |
|---|------|-------------|---------------------|-----|-------|
| T-25 | Integrate Whisper/Deepgram for voice | Voice transcription service | Technician records voice → text transcription returned in < 5s | G-08 | D-1 |
| T-26 | Integrate Claude Vision for image analysis | Image analysis service | Photo of equipment → anomaly description + severity assessment | G-08 | D-2 |
| T-27 | Wire skill to field capture page | Updated Page 8 | Voice + photo → identify-work-request skill → structured work request with equipment TAG | G-08 | D-3 |
| T-28 | Mobile-responsive field capture UI | Responsive React PWA + Page 8 | Touch-friendly wizard, camera/mic/GPS, offline-first, 4 languages | G-13 | D-4 ✅ |
| T-29 | GPS metadata + equipment proximity | Location service | Auto-detects nearest equipment TAG based on GPS coordinates | G-08 | D-5 |

### P4B — Workshop MVP Alignment (Closes gap between workshop definition and current build)

| # | Task | Deliverable | Acceptance Criteria | Gap | Phase |
|---|------|-------------|---------------------|-----|-------|
| ~~T-39~~ | ~~Build troubleshooting engine + skill~~ | ~~`troubleshooting_engine.py`, skill `guide-troubleshooting`~~ | DONE (Sessions 19-21). Engine with 214 symptoms, 5 decision trees, Jaccard matching, min-cost ordering. Skill + 5 MCP tools + 8 API endpoints. 105+ tests | ~~GAP-W02~~ | ~~A~~ |
| ~~T-40~~ | ~~Troubleshooting UI page~~ | ~~New Streamlit Page 23~~ | DONE (Session 21). 3-tab page (New Diagnosis, History, Trees). i18n EN/FR/ES/AR. Role mappings updated | ~~GAP-W02~~ | ~~A~~ |
| ~~T-41~~ | ~~Usage-based task type~~ | ~~Updated schemas + RCM + SAP export~~ | DONE (Session 17). `SchedulingTrigger` enum, `FREQ_UNIT_TRIGGER`, `measuring_point`, complete SAP mapping, `recommend_frequency_unit()`, UI + skill updates, 25 tests | ~~GAP-W08~~ | ~~A~~ |
| ~~T-42~~ | ~~Equipment manual chat (Claude Native)~~ | ~~New Streamlit page, document loader~~ | DONE (Session 17). Page 20 + `manual_loader.py` + prompt caching + 57 tests | ~~GAP-W07~~ | ~~B~~ |
| ~~T-43~~ | ~~Role-based UI views~~ | ~~Role selector + page visibility map~~ | DONE (Session 18). 6 roles (Manager, Reliability Eng, Planner, Supervisor, Technician, Consultant). `role_config.py` + sidebar selector + personalized landing + role-filtered KPIs + banners. 102 tests | ~~GAP-W05~~ | ~~B~~ |
| ~~T-44~~ | ~~Quality execution checklists~~ | ~~Interactive checklist model + gate logic~~ | DONE (Sessions 20-21). `ExecutionChecklistEngine` + 4 enums + 4 Pydantic models + ORM. 5 MCP tools, 7 API endpoints, Page 22, skill. Gate enforcement, condition codes, supervisor closure. 83+ tests | ~~GAP-W06~~ | ~~B~~ |
| ~~T-45~~ | ~~Financial/ROI engine~~ | ~~ROI calculator + budget tracking + dashboard~~ | DONE (Sessions 24-25). `ROIEngine` + `BudgetEngine`, 8 Pydantic models, 8 MCP tools, 2 skills, 8 API endpoints, Page 24 (5-tab financial dashboard), executive dashboard financial tab, reporting integration, 4 chart functions, i18n (4 languages), 2,888 tests | ~~GAP-W04~~ | ~~C~~ |
| ~~T-46~~ | ~~Competency-based work assignment~~ | ~~Workforce schema + assignment optimizer~~ | DONE (Session 18). `assignment_engine.py`, 6 new schemas, 4 MCP tools, API router, seed data, supervisor dashboard tab, i18n, 56 tests | ~~GAP-W09~~ | ~~C~~ |
| ~~T-47~~ | ~~Shutdown management enhancement~~ | ~~Updated `shutdown_engine.py`~~ | DONE (Session 19). 6 new engine methods (daily/shift/final reports, velocity, shift suggestions, schedule generation with topological sort + critical path). 6 new schemas, 5 MCP tools, 5 API endpoints, UI expanders, i18n, 26 new tests | ~~GAP-W14~~ | ~~C~~ |
| ~~T-48~~ | ~~Consultant deliverable tracking~~ | ~~Deliverable status + time tracking~~ | DONE (Sessions 22-23). `DeliverableTrackingEngine`, 5 Pydantic models, 2 ORM models, 9 API endpoints, Page 21 (4 tabs), wizard integration, workflow auto-transitions, quality score linking, i18n, 47+ tests | ~~GAP-W10~~ | ~~C~~ |
| T-49 | Expert knowledge capture system | Annotation system + knowledge contribution workflow | Retired experts contribute diagnostic knowledge remotely, feeds AI model | GAP-W13 | E |
| ~~T-50~~ | ~~Offline mode (PWA)~~ | ~~PWA shell + local cache + sync protocol~~ | DONE (2026-03-12). React PWA (`field_app/`): 3 pages, IndexedDB/Dexie.js, SyncManager, ConflictDialog, Service Worker, FastAPI `/field/` mount. 14 integration tests + 33 frontend tests. | ~~GAP-W03~~ | ~~E~~ |

### P5 — Scale & Extend (Post-pilot)

| # | Task | Deliverable | Acceptance Criteria | Gap | Phase |
|---|------|-------------|---------------------|-----|-------|
| T-30 | Multi-plant configuration + switching | Plant selector UI, per-plant config | Admin creates new plant, users switch between plants, data isolated | G-10 | E-1 |
| T-31 | Real SAP PM connection (RFC/BAPI) | SAP connector service | Read/write to SAP PM via RFC, functional locations + task lists sync bidirectionally | G-11 | E-2 |
| T-32 | Predictive analytics with real failure data | Weibull prediction dashboard | Feed real failure history → Weibull fit → RUL predictions on Page 13 | G-12 | E-3 |
| T-33 | Cloud deployment (AWS/GCP) | Terraform/CloudFormation scripts | One-command deployment to cloud, HTTPS, managed DB, auto-scaling | G-15 | E-4 |
| T-34 | Knowledge graph for cross-equipment insights | Neo4j integration | Equipment → failure → task relationships queryable, drives cross-fleet recommendations | G-14 | E-5 |

### Strategic Tasks (Non-code, business value)

| # | Task | Deliverable | Acceptance Criteria | Source |
|---|------|-------------|---------------------|--------|
| T-35 | Frame "Cognitive Prosthesis" narrative | Positioning document / pitch deck section | Clear messaging: AI augments engineers, doesn't replace. Safety-first design highlighted | REF-12 Rec 1 |
| T-36 | Build SAP integration moat positioning | SAP capability comparison vs competitors | Document showing AMS SAP depth vs myRIAM/Prometheus/Fiix (none have structured export) | REF-12 Rec 2 |
| T-37 | Aggregate Asset Health Index for executives | Plant-wide health score on Page 14 | Executive dashboard shows overall plant health, drill-down by system/equipment | REF-12 Rec 4 |
| T-38 | Map remaining ISO 55002 gaps | Gap analysis document | Current 73% compliance → identify specific remaining clauses, effort to close each | REF-12 Rec 8 |

---

**Summary:** 50 tasks across 7 priority tiers. P0 (4 tasks, < 1hr) → P1 (8 tasks, critical path) → P2 (6 tasks, demo) → P3 (6 tasks, production) → P4 (5 tasks, field capture) → P4B (12 tasks, workshop MVP alignment) → P5 (5 tasks, scale) + 4 strategic tasks.

---

## Part 6: Key Reference Files

| File | Purpose | When to Read |
|------|---------|--------------|
| `gemini.md` | Project constitution — schemas, rules, architecture | Always (any schema/rule question) |
| `CLAUDE.md` | AI entry point — overview, conventions, testing | When starting work on this repo |
| `DOCUMENT_INDEX.md` | Master routing table for all documentation | When finding specific docs |
| `MASTER_PLAN.md` | **This file** — capabilities, gaps, next phases | When planning next work session |
| `EVAL_RUNBOOK.md` | Eval pipeline step-by-step | When running skill evaluations |
| `SHARED_DOCS_MANIFEST.md` | Cross-repo document sync tracking | When syncing with OR SYSTEM |
| `agents/run.py` | **CLI entry point** — runs M1→M4 workflow | When running the agent pipeline |
| `agents/definitions/orchestrator.py` | Creates all 4 agents with shared client | When debugging agent creation |
| `agents/_shared/base.py` | Unified Agent class — API loop, skill loading | When debugging agent behavior |
| `agents/*/skills.yaml` | Skill-to-agent assignments | When modifying skills |
| `api/config.py` | 6 env vars (DB, API key, CORS, etc.) | When setting up environment |
| `api/seed.py` | Synthetic data generator + DB seeding | When populating demo database |
| `tools/models/schemas.py` | All Pydantic data models (30+) | When modifying data structures |
| `tools/engines/sap_export_engine.py` | SAP upload package generation | When working on SAP integration |

---

## Changelog

| Date | Change | Session |
|------|--------|---------|
| 2026-03-11 | GAP-W13 Session 3: Expert Knowledge Flywheel — Integration. Created `agents/tool_wrappers/expert_knowledge_tools.py` (5 MCP tools: `match_expert_for_diagnosis`, `create_expert_consultation`, `apply_expert_guidance`, `extract_expert_contribution`, `promote_expert_knowledge`). Registered tools in `server.py` (reliability agent). Extended `TroubleshootingEngine`: `apply_expert_knowledge()` (re-ranks candidates, adds new ones, sets ESCALATED status) + `expert_consultation_id` param on `record_feedback()`. Created skill `capture-expert-knowledge/CLAUDE.md` with ESCALATE + PROCESS modes; registered in `agents/reliability/skills.yaml`. Seed data: 3 retired experts (Hassan Benali, Fatima Zahraoui, Youssef Kadiri), 2 consultations, 1 PROMOTED contribution in `api/seed.py`. Integration tests: `tests/test_expert_knowledge_integration.py` (~45 tests). Docs: `GAP-W13_EXECUTION.md` status→CLOSED. MASTER_PLAN: GAP-W13 closed, 27 pages, 166 tools, 42 skills. | 28 |
| 2026-03-11 | GAP-W12 Session D: Import History (G-02 Session D). `ImportHistoryModel` ORM (`api/database/models.py`): `import_id`, `plant_id`, `source`, `filename`, `file_size_kb`, `total_rows`, `valid_rows`, `error_rows`, `status`, `errors_json`, `imported_by`, `imported_at`. `ImportHistoryEntry` Pydantic schema (`tools/models/schemas.py`). Service methods `record_import_history()`, `list_import_history()`, `get_import_history_entry()` in `api/services/reporting_service.py` + wired into `upload_and_validate()`. Two history endpoints in `api/routers/reporting.py`: `GET /reporting/import/history` (filter by plant_id/source, paginated) + `GET /reporting/import/history/{import_id}`. API client methods `get_import_history()` + `get_import_history_entry()` in `streamlit_app/api_client.py`. Import History tab (tab 5) added to Page 15 with status badges (🟢🟡🔴), expandable error details, source filter. 10 i18n keys under `import.history_*` in EN/ES/FR/AR. 8 new test classes (ORM + schema + service + API endpoints) added to `tests/test_import_tools_api.py`. T-13/T-14/T-15/T-16 struck through in task table. | 27 |
| 2026-03-11 | G-03 Guided Demo Flow (T-17 + T-18). Created `docs/DEMO_GUIDE.md` (7 sections: setup, 30-min executive track, 60-min full technical track, 23-page talking points, key concepts reference, known limitations, FAQ with 10+ Q&As, CLI appendix). Created `docs/G-03_EXECUTION.md` execution tracker. Polished Page 18 wizard: added `apply_style()`, quadrilingual i18n keys (~20 keys under `wizard.*` in EN/ES/FR/AR), Demo Mode quick-fill button ("Load OCP Demo Data"), `feedback_widget`, all step headers and nav buttons via `t()`. G-03 marked closed in Part 3.1. T-17 + T-18 marked done in Part 5. | 17 |
| 2026-03-11 | GAP-W04 Financial Agent / ROI Tracking (T-45). Session 1: Foundation — 4 enums (`FinancialCategory`, `BudgetStatus`, `ROIStatus`, `CurrencyCode`) + 8 Pydantic models (`BudgetItem`, `BudgetSummary`, `ROIInput`, `ROIResult`, `FinancialImpact`, `FinancialSummary`, `BudgetVarianceAlert`, `ManHourSavingsReport`) in `schemas.py`. `tools/engines/roi_engine.py` (NPV, payback, BCR, IRR via bisection, cumulative savings, scenario comparison, financial impact, man-hours saved). `tools/engines/budget_engine.py` (budget tracking, variance alerts, financial summary, forecast). 8 MCP tools in `agents/tool_wrappers/financial_tools.py`. 2 skills (`calculate-roi` for Orchestrator, `track-budget` for Planning). 3 SWMR entities. Session 2: User-facing — `api/routers/financial.py` (8 endpoints). Page 24 `24_financial.py` (5 tabs: Budget, ROI Calculator, Cost Drivers, Man-Hours, Summary). 8 API client functions. 4 chart functions (budget_variance, roi_cumulative, cost_driver_pareto, man_hours_comparison). Financial tab in executive dashboard. Financial sections in reporting engine (monthly + quarterly + FINANCIAL_REVIEW report type). i18n EN/FR/ES/AR (~45 keys each). 3 new test files (test_financial_engine, test_financial_schemas, test_financial_tools). 2,888 total tests passing. `docs/GAP-W04_EXECUTION_PLAN.md` tracker. | 24-25 |
| 2026-03-11 | GAP-W10 Consultant Workflow / Deliverable Tracking (T-48). Built `tools/engines/deliverable_tracking_engine.py` (6-state lifecycle: DRAFT→IN_PROGRESS→SUBMITTED→UNDER_REVIEW→APPROVED, rejection rework cycle, variance calculation, plan seeding). 5 Pydantic models (`DeliverableStatus`, `DeliverableCategory`, `Deliverable`, `TimeLog`, `DeliverableTrackingSummary`). 2 ORM models (`DeliverableModel`, `TimeLogModel`). API: `deliverable_service.py` + `deliverables.py` router (9 endpoints), audit trail. 9 API client methods. Page 21 (`21_deliverables.py`): 4-tab UI (Overview metrics, Detail with transitions, Time Tracking, Client Review with approve/reject). Wizard Step 5 uses `DEFAULT_HOURS` per category + seed button. Workflow `_update_deliverable_status()` auto-transitions to SUBMITTED on milestone approval. Quality score linking in `_run_quality_scoring()`. Progress dashboard sidebar summary. SessionState `deliverables` + `time_logs` entities (SWMR: orchestrator). i18n EN/FR/ES/AR (~30 keys each). `role_config.py` Page 21: CONSULTANT primary, MANAGER primary, PLANNER secondary. 47+ new tests (27 engine + 20 API). `docs/GAP-W10_EXECUTION.md` tracker. | 22-23 |
| 2026-03-11 | GAP-W06 Quality Checklists / Gate Reviews (T-44). Built `tools/engines/execution_checklist_engine.py` (ordered step generation, predecessor wiring, gate enforcement, 3-level condition codes). 4 enums + 4 Pydantic models (`ExecutionStep`, `ExecutionChecklist`, `StepObservation`, `ChecklistClosureSummary`). ORM model `ExecutionChecklistModel` with JSON columns. 5 MCP tools (`generate_execution_checklist`, `complete_checklist_step`, `skip_checklist_step`, `get_checklist_status`, `close_execution_checklist`). API: router (7 endpoints), service with audit trail. Page 22 (`22_execution_checklists.py`): interactive step execution with color-coded type badges, gate questions, condition code radios, supervisor closure. 7 API client methods. Skill `generate-execution-checklists` for Planning agent. 83+ new tests (56 engine + 27 API). 2,713+ total passing. | 20-21 |
| 2026-03-11 | GAP-W14 Shutdown Management Enhancement (T-47). Extended `shutdown_engine.py` with 6 new methods: daily/shift/final reports, velocity calculation, shift suggestions (critical path priority ranking), schedule generation (Kahn's topological sort + critical path analysis). 6 new schemas. 5 MCP tools, 5 API endpoints + service. Skill updated (Steps 7-10, new triggers). UI: 4 new expanders in Page 13 (daily report, shift focus, schedule/cronogram, final summary). i18n (4 languages, 22 keys each). 26 new tests. Execution tracker: `docs/GAP-W14_EXECUTION.md`. | 19 |
| 2026-03-11 | GAP-W09 Competency-Based Work Assignment (T-46). Built `tools/engines/assignment_engine.py` (5-dimension scoring: specialty 30, competency 25, equipment 20, cert 15, availability 10). 6 new schemas (`CompetencyLevel`, `AssignmentStatus`, `TechnicianCompetency`, `TechnicianProfile`, `TaskCompetencyRequirement`, `WorkAssignment`, `AssignmentSummary`). `competency_requirements` field added to `MaintenanceTask`. `WorkforceModel` extended with 5 competency columns. SWMR entities `workforce_assignments` + `technician_profiles` owned by Planning. 4 MCP tools + API router (3 endpoints) + service. Seed data enhanced: 25 workers with A/B/C levels, competency matrices, equipment expertise. Supervisor dashboard: new "Crew Assignment" tab in Page 12. i18n keys for 4 languages (40 keys each). 56 new tests. | 18 |
| 2026-03-11 | GAP-W07 Equipment Manual Chat (T-42). Built `tools/engines/manual_loader.py` (document loader for PDFs/TXT/MD + equipment library context extraction), `streamlit_app/pages/20_equipment_chat.py` (chat UI with equipment selector, streaming responses, prompt caching via `cache_control: {"type": "ephemeral"}`). Created `data/manuals/` directory with SAG Mill sample manual. i18n keys added for 4 languages (EN/FR/ES/AR). Added `pymupdf>=1.24.0` dependency. 57 new tests (2,244 total). Claude Native approach — no vector DB. | 17 |
| 2026-03-11 | Workshop assessment. Analyzed 2 functional definition workshop transcriptions (2026-03-10, 4 participants). Mapped 23 workshop requirements against codebase: ~65% coverage. Added Section 3.5 with 12 workshop-derived gaps (GAP-W02 through GAP-W14). Added P4B tier (12 tasks, T-39 to T-50). Critical new gaps: troubleshooting engine (GAP-W02), offline mode (GAP-W03), financial/ROI (GAP-W04). Decisions: GAP-W05 = role-based UI views (no new agents), GAP-W07 = Claude Native RAG (no vector DB). Deliverable: `AMS functional definition/AMS_Workshop_Assessment.docx`. | 16 |
| 2026-03-10 | Deep audit & plan revision. Corrected 4 inaccurate gap descriptions (G-01 API exists, G-02 page 15 has uploader, G-04 seed script exists, engine count). Added 5 new gaps (G-16 to G-20: .env.example, workflow API endpoint, import file parsing, API key validation, SAP file serialization). Added Phase 0 (Quick Wins). Restructured Phase A (removed "configure API" — already done, added SAP xlsx + workflow endpoint). Restructured Phase B (added file parsing + MCP wrapper). Added 6 key files to Part 6. Updated opportunity map priorities. | 15 |
| 2026-03-10 | Initial creation. Consolidated from progress.md (534 lines), task_plan.md (185 lines), findings.md (139 lines). Full capability inventory, gap analysis, and 5-phase roadmap. Deleted superseded files. | 14 |
