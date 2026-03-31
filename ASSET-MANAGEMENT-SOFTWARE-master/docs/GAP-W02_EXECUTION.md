# GAP-W02: Troubleshooting / Diagnostic Assistant — Execution Tracker

> **Living document.** Updated each session. Last update: 2026-03-11 (Session 3 complete — GAP-W02 CLOSED).

## Context

**Why:** Workshop funcional (2026-03-10) identifico que los tecnicos de campo diagnostican fallas por experiencia/adivinanza, reemplazando piezas innecesariamente. Los manuales OEM no llegan al terreno. Jorge Alquinta (ex-superintendente): "hay una oportunidad tremenda de poder entregar una solucion profesional." Metrica de exito: >85% precision diagnostica, reduccion medible de MTTR.

**What:** Motor de troubleshooting determinista + skill para el agente de Reliability + pagina Streamlit interactiva. El tecnico describe sintomas → el sistema sugiere 2-3 vias de testeo (minimo-costo-primero) → diagnostico mapeado a los 72 combos FM MASTER.

**Foundation:** Ya existen: 72-combo FM MASTER (216 pre-failure conditions), equipment library (15 tipos, ~150 failure modes), component library (30 tipos), 4 agentes con Reliability en Opus, 128 MCP tools, 19 paginas Streamlit, i18n EN/FR/ES/AR.

---

## Session 1: Engine + Knowledge Base + Tests

**Goal:** Motor de troubleshooting funcionando con tests unitarios.

### 1.1 Data Models (schemas.py)

- [x] Add `DiagnosticTestType` enum (9 values: SENSORY → SPECIALIST_ANALYSIS)
- [x] Add `DiagnosisStatus` enum (IN_PROGRESS, COMPLETED, ESCALATED, ABANDONED)
- [x] Add `SymptomEntry` model
- [x] Add `DiagnosticTest` model
- [x] Add `DiagnosticPath` model
- [x] Add `DiagnosisSession` model

### 1.2 Symptom Catalog (Knowledge Base)

- [x] Create directory `skills/00-knowledge-base/data-models/troubleshooting/`
- [x] Create `symptom-catalog.json` (216 P-conditions from FM MASTER)
- [x] Create `trees/` subdirectory
- [x] Create `trees/tree-sag-mill.json` (first decision tree)

### 1.3 Troubleshooting Engine

- [x] Create `tools/engines/troubleshooting_engine.py`
- [x] Add import in `tools/engines/__init__.py`

### 1.4 Unit Tests

- [x] Create `tests/test_troubleshooting_engine.py`
- [x] All tests pass: `python -m pytest tests/test_troubleshooting_engine.py -v`

### Session 1 Results

- **92 unit tests** — all passing (0.31s)
- **214 symptoms** extracted from 72 FM MASTER cards into `symptom-catalog.json`
- **SAG Mill decision tree** — 6 entry categories, ~160 nodes, bilingual (EN/FR)
- **Full suite**: 2,355 passed, 4 pre-existing failures (tool count mismatches — to be fixed in Session 2)
- **Zero regressions** introduced

---

## Session 2: Skill + MCP Tools + API + Service

**Goal:** El agente Reliability puede hacer troubleshooting via MCP tools, endpoints API funcionan.

### 2.1 Skill

- [x] Create `skills/02-maintenance-strategy-development/guide-troubleshooting/CLAUDE.md`
- [x] Create `evals/trigger-eval.json`
- [x] Create `evals/evals.json`

### 2.2 MCP Tool Wrappers

- [x] Create `agents/tool_wrappers/troubleshooting_tools.py` (5 tools)
- [x] Update `agents/tool_wrappers/server.py` (import + AGENT_TOOL_MAP)

### 2.3 Agent Assignment

- [x] Update `agents/reliability/skills.yaml`

### 2.4 API Router + Service + DB Model

- [x] Create `api/routers/troubleshooting.py` (8 endpoints)
- [x] Create `api/services/troubleshooting_service.py`
- [x] Add `TroubleshootingSessionModel` to `api/database/models.py`
- [x] Register router in `api/main.py`

### 2.5 Integration Tests

- [x] Create `tests/test_api/test_troubleshooting.py` (13 tests)
- [x] Update `tests/test_skills_v2.py` (+guide-troubleshooting to reliability)
- [x] Update `tests/test_agent_tool_access.py` (reliability 49→54)

### Session 2 Results

- **13 API integration tests** — all passing
- **92 engine unit tests** — all passing
- **5 MCP tools** registered: create_troubleshooting_session, add_troubleshooting_symptom, get_recommended_diagnostic_tests, record_troubleshooting_test_result, get_equipment_troubleshooting_info
- **8 API endpoints** under `/api/v1/troubleshooting/`
- **guide-troubleshooting skill** with 12 trigger + 10 anti-trigger + 5 functional evals
- **4 previously-failing tests FIXED** (tool count, skill count, SWMR ownership, mandatory skills)
- **Full suite**: 2,541 passed, 12 pre-existing failures (navigation/resource-leveling), 0 regressions

---

## Session 3: UI + i18n + More Trees + Full Integration

**Goal:** Feature completo end-to-end.

### 3.1 Streamlit API Client

- [x] Add 7 client functions to `streamlit_app/api_client.py`

### 3.2 Streamlit Page 23

- [x] Create `streamlit_app/pages/23_troubleshooting.py` (3 tabs: New Diagnosis, History, Trees)

### 3.3 i18n Translations

- [x] Add `troubleshooting.*` keys to `en.json` (~40 keys)
- [x] Add `troubleshooting.*` keys to `fr.json`
- [x] Add `troubleshooting.*` keys to `es.json`
- [x] Add `troubleshooting.*` keys to `ar.json`

### 3.4 Additional Decision Trees

- [x] `trees/tree-ball-mill.json` (56 nodes, 20 terminals)
- [x] `trees/tree-slurry-pump.json` (48 nodes, 20 terminals)
- [x] `trees/tree-belt-conveyor.json` (58 nodes, 22 terminals)
- [x] `trees/tree-crusher.json` (55 nodes, 22 terminals)

### 3.5 Registry & Documentation Updates

- [x] Update `tests/test_navigation.py` (page 23, page count 23, API methods, i18n)
- [x] Update `streamlit_app/role_config.py` (PAGE_REGISTRY + ROLE_PAGE_MAP)
- [x] Update `skills/SKILL_MASTER_REGISTRY.md` (40 skills, +guide-troubleshooting)
- [x] Update `MASTER_PLAN.md` (GAP-W02 closed, T-39 + T-40 done)
- [x] Update `agents/AGENT_REGISTRY.md` (reliability 16 skills, 54 tools)

### 3.6 Full Verification

- [x] Full test suite passes: **2,719 passed, 0 failures**
- [x] All 5 decision trees load via engine
- [x] Fixed pre-existing duplicate NotificationModel bug in models.py

### Session 3 Results

- **Page 23** — 3-tab Streamlit page (New Diagnosis, Session History, Decision Trees)
- **7 API client functions** — full troubleshooting workflow from Streamlit
- **i18n in 4 languages** — EN, FR, ES, AR (~40 keys each)
- **5 decision trees total** — SAG Mill + Ball Mill + Slurry Pump + Belt Conveyor + Crusher (279 nodes, 84 terminal diagnoses)
- **Role mappings** — Reliability Engineer (primary), Technician (primary), Supervisor (secondary)
- **Full suite**: 2,719 passed, 0 failures (up from 2,541 in Session 2)
- **Pre-existing bug fixed**: duplicate NotificationModel in models.py removed
- **GAP-W02 CLOSED** — all 3 sessions complete

---

## Design Decisions

1. **Engine is deterministic** — no LLM calls. The Reliability agent (Opus) provides intelligence on top.
2. **Symptom catalog derived from FM MASTER** — 72 cards x 3 P-conditions = 216 structured symptoms.
3. **Minimum-cost-first** ordering — SENSORY ($0) before SPECIALIST ($2000).
4. **72-combo enforcement** — all diagnoses MUST map to valid Mechanism+Cause pairs.
5. **Decision trees are JSON** — serializable, exportable for future offline mode.
6. **Confidence scoring** — HIGH>=0.8, MEDIUM 0.5-0.79, LOW<0.5. Below 0.5 after 3 tests → escalate.
7. **Feedback loop** — `actual_cause_feedback` field captures real-world outcome.
