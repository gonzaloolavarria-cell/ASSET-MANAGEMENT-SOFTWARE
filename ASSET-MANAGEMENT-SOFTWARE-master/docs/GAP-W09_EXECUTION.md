# GAP-W09: Competency-Based Work Assignment — Execution Plan

> **Gap:** GAP-W09 | **Task:** T-46 | **Priority:** P4B (Workshop MVP Alignment)
> **Estimate:** 1-2 sessions | **Status:** DONE
> **Last updated:** 2026-03-11 | **Completed:** Session 18

---

## 1. Problem Statement

**From the workshop (2026-03-10):**

Jorge Alquinta (ex-superintendent, field expert) described the supervisor's core challenge:

> "El supervisor asigna los trabajos a los técnicos y se los asigna en base a las competencias que tienen los técnicos. Por eso a tal personal o a los, gente que tiene más experiencia, más conocimiento en ciertas cosas, en ciertos equipos, le asigna esas tareas y no a otros. Él también conoce las habilidades, fortalezas y habilidades de su equipo desde el punto de vista de conocimiento."

Jose Cortinat (product lead) proposed the AI-assisted solution:

> "Analiza, tengo estas órdenes de trabajo... tengo estos perfiles actualmente, estos viejitos que además esos viejitos los tengo ya preseteados de qué capacidades tienen. Prepárame un plan, sabes como ayúdame un poco como un diagnóstico [...] lo revisa y dice, puta, sí, la verdad que me hace unos planes bastante cercanos a lo que yo diría que debemos hacer."

**Key pain points from the workshop:**
1. Supervisor has 15-person crew but 3 may be absent (sick, vacation) → must re-plan with 12
2. Equipment failures compete with planned maintenance for the same crew
3. Assignment is currently based on supervisor's tacit knowledge of each technician's strengths
4. No digital tool supports this — everything is paper, email, or verbal
5. Quality and safety are the two pillars of execution (bad assignment → rework, accidents)

---

## 2. What Already Exists

### 2.1 Schemas (`tools/models/schemas.py`)

| Schema | Lines | Status | Gap |
|--------|-------|--------|-----|
| `LabourSpecialty` (enum) | 487-490 | `FITTER`, `ELECTRICIAN`, `INSTRUMENTIST` | Missing competency level |
| `LabourResource` | 1148-1152 | Specialty + quantity + hours/person | No competency requirement |
| `WorkforceAvailability` | 699-702 | Available technicians by specialty | No competency data |
| `TradeCapacity` | 2741-2746 | Per-specialty/shift headcount + hours | No competency dimension |
| `ExpertCard` | 1590-1607 | Expert knowledge card (TMS) | Has domains, equipment_expertise, certifications — closest to what we need |
| `StakeholderRole` (enum) | 1368-1373 | `MAINTENANCE_MANAGER`, `RELIABILITY_ENGINEER`, `PLANNER`, `TECHNICIAN` | Missing `SUPERVISOR` |
| `MaintenanceTask` | 1165-1189 | Has `labour_resources: list[LabourResource]` | No competency requirement per task |

### 2.2 Database Models (`api/database/models.py`)

| Model | Lines | Status | Gap |
|-------|-------|--------|-----|
| `WorkforceModel` | 470-481 | `worker_id`, `name`, `specialty`, `shift`, `plant_id`, `available`, `certifications` | No competency_level, no equipment_expertise, no years_experience |
| `ExpertCardModel` | 334-349 | Full expert profile | Different purpose (TMS), not used for assignment |

### 2.3 Engines (`tools/engines/scheduling_engine.py`)

| Method | Lines | Status | Gap |
|--------|-------|--------|-----|
| `create_weekly_program()` | 32-76 | Creates DRAFT from backlog | No crew assignment |
| `level_resources()` | 141-191 | Balances by (shift, specialty) | No competency matching |
| `detect_conflicts()` | 193-261 | Multi-crew + specialist overallocation | No competency conflicts |
| `level_resources_enhanced()` | 334-432 | Multi-day splitting | No competency dimension |

### 2.4 Seed Data (`api/seed.py`)

- 25 workers, 5 specialties, 3 shifts, 80% available
- No competency level, no equipment expertise

### 2.5 UI Pages

- Page 10 (`10_planner.py`): Shows `workforce_available` read-only, no assignment
- Page 12 (`12_scheduling.py`): Weekly programs + Gantt + utilization, no worker assignment
- **No supervisor dashboard exists**

### 2.6 Session State (`agents/orchestration/session_state.py`)

- SWMR map has no `workforce_assignments` entity
- Planning agent owns `maintenance_tasks` and `work_packages`

---

## 3. Design Decisions

### 3.1 Competency Model

Based on workshop discussion, use a **3-level competency scheme per specialty per equipment type:**

| Level | Code | Description (from workshop) | Can do |
|-------|------|-----------------------------|--------|
| A | Senior | "Gente que tiene más experiencia, más conocimiento en ciertos equipos" | All tasks including complex diagnostics |
| B | Standard | Mid-level, can work independently on routine tasks | Routine PM, simple corrective |
| C | Junior | "Técnicos que no son de tanto nivel como un senior" | Assisted tasks only, needs supervisor or A-level oversight |

### 3.2 Assignment Approach

**Hybrid: AI-suggested + Supervisor-approved.** The system recommends optimal assignment, the supervisor reviews and adjusts.

This matches Jose's vision: "Prepárame un plan [...] no te digo que lo vaya a ejecutar a rajatabla, pero [...] lo revisa y dice, puta, sí."

### 3.3 Agent Ownership

- **Planning agent** owns `workforce_assignments` (extends existing task/WP ownership)
- **Orchestrator** triggers assignment optimization during M3 milestone
- Supervisor interacts via UI only (not a separate agent)

### 3.4 Scope Boundaries (This GAP only)

**IN scope:**
- Technician competency profiles (A/B/C per specialty per equipment type)
- Task competency requirements (minimum level needed)
- Assignment optimizer engine (match tasks to available technicians)
- Supervisor dashboard widget (view crew, review suggestions, adjust)
- Updated seed data with competency levels
- Tests

**OUT of scope (other GAPs):**
- Offline mode (GAP-W03)
- Quality checklists during execution (GAP-W06)
- Role-based page visibility (GAP-W05)
- Financial impact of assignments (GAP-W04)

---

## 4. Implementation Steps

### Phase 1: Data Model Layer (schemas + DB models)

- [x] **1.1** Add `CompetencyLevel` enum to `tools/models/schemas.py`
  ```python
  class CompetencyLevel(str, Enum):
      A = "A"  # Senior — complex diagnostics, all equipment
      B = "B"  # Standard — routine PM, simple corrective
      C = "C"  # Junior — assisted tasks, needs oversight
  ```

- [x] **1.2** Add `TechnicianCompetency` schema to `tools/models/schemas.py`
  ```python
  class TechnicianCompetency(BaseModel):
      specialty: LabourSpecialty
      equipment_type: str  # Equipment type TAG (e.g., "SAG_MILL", "CONVEYOR")
      level: CompetencyLevel
      certified: bool = False
      certified_date: Optional[date] = None
      notes: str = ""
  ```

- [x] **1.3** Add `TechnicianProfile` schema to `tools/models/schemas.py`
  ```python
  class TechnicianProfile(BaseModel):
      worker_id: str
      name: str
      specialty: LabourSpecialty  # Primary specialty
      shift: str  # MORNING, AFTERNOON, NIGHT
      plant_id: str
      available: bool = True
      competencies: list[TechnicianCompetency] = Field(default_factory=list)
      years_experience: int = 0
      equipment_expertise: list[str] = Field(default_factory=list)  # Equipment TAGs
      certifications: list[str] = Field(default_factory=list)
      safety_training_current: bool = True
      notes: str = ""
  ```

- [x] **1.4** Add `TaskCompetencyRequirement` schema to `tools/models/schemas.py`
  ```python
  class TaskCompetencyRequirement(BaseModel):
      specialty: LabourSpecialty
      min_level: CompetencyLevel = CompetencyLevel.B
      equipment_type: Optional[str] = None  # If specific equipment expertise needed
      requires_certification: bool = False
      supervision_required: bool = False  # True if C-level assigned, needs A/B oversight
  ```

- [x] **1.5** Add `WorkAssignment` schema to `tools/models/schemas.py`
  ```python
  class AssignmentStatus(str, Enum):
      SUGGESTED = "SUGGESTED"    # AI-recommended
      CONFIRMED = "CONFIRMED"    # Supervisor approved
      MODIFIED = "MODIFIED"      # Supervisor changed assignment
      IN_PROGRESS = "IN_PROGRESS"
      COMPLETED = "COMPLETED"

  class WorkAssignment(BaseModel):
      assignment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
      work_package_id: str
      task_id: Optional[str] = None
      worker_id: str
      worker_name: str
      specialty: LabourSpecialty
      competency_level: CompetencyLevel
      scheduled_date: date
      scheduled_shift: str
      estimated_hours: float
      status: AssignmentStatus = AssignmentStatus.SUGGESTED
      match_score: float = 0.0  # 0-100, how well worker matches task requirements
      match_reasons: list[str] = Field(default_factory=list)
      supervisor_notes: str = ""
      created_at: datetime = Field(default_factory=datetime.now)
  ```

- [x] **1.6** Add `competency_requirements` field to `MaintenanceTask` schema
  ```python
  # In MaintenanceTask class, add:
  competency_requirements: list[TaskCompetencyRequirement] = Field(default_factory=list)
  ```

- [x] **1.7** Update `WorkforceModel` in `api/database/models.py`
  ```python
  # Add columns:
  competency_level: Mapped[str] = mapped_column(String(1), default="B")
  years_experience: Mapped[int] = mapped_column(Integer, default=0)
  equipment_expertise: Mapped[list | None] = mapped_column(JSON, nullable=True)
  safety_training_current: Mapped[bool] = mapped_column(Boolean, default=True)
  competencies: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list[TechnicianCompetency]
  ```

- [x] **1.8** Register `workforce_assignments` in SessionState SWMR map
  ```python
  # In session_state.py ENTITY_OWNERSHIP:
  "workforce_assignments": EntityOwner.PLANNING,
  "technician_profiles": EntityOwner.PLANNING,
  ```

### Phase 2: Assignment Optimizer Engine

- [x] **2.1** Create `tools/engines/assignment_engine.py` with `AssignmentEngine` class

- [x] **2.2** Implement `score_match()` method — calculates fit score (0-100) between a technician and a task
  ```
  Scoring algorithm:
  - Specialty match: 30 pts (exact match)
  - Competency level: 25 pts (A→25, B→15 if min_B, C→5 if min_C)
  - Equipment expertise: 20 pts (has specific equipment type experience)
  - Certification match: 15 pts (required cert present)
  - Availability: 10 pts (not overloaded in shift)
  ```

- [x] **2.3** Implement `optimize_assignments()` method — assigns technicians to tasks in a work package
  ```
  Algorithm:
  1. Build list of (task, competency_requirement) pairs
  2. Build list of available technicians for the shift/date
  3. For each task, score all available technicians
  4. Use greedy assignment: highest-priority tasks first, best-match technician
  5. Handle conflicts: if technician assigned to overlapping tasks, pick highest-priority
  6. Flag under-qualified assignments (C-level on B-required task) with REQUIRES_SUPERVISION
  7. Flag unassignable tasks (no available technician with required specialty)
  ```

- [x] **2.4** Implement `reoptimize_with_absences()` method — handles the "15 planned, 12 showed up" scenario
  ```
  Input: existing assignments + list of absent worker_ids
  Output: new assignments for affected tasks, list of tasks that can't be covered
  Priority logic: criticality of equipment > task priority > cost of delay
  ```

- [x] **2.5** Implement `generate_assignment_summary()` — creates supervisor-friendly summary
  ```
  Output:
  - Per-technician: list of assigned tasks, total hours, equipment locations
  - Unassigned tasks (if any) with reason
  - Under-qualified assignments with supervision recommendation
  - Overall crew utilization % by specialty
  ```

- [x] **2.6** Add unit tests in `tests/test_assignment_engine.py`
  - Test `score_match()` with various competency combinations
  - Test `optimize_assignments()` with happy path (all tasks covered)
  - Test `optimize_assignments()` with insufficient crew
  - Test `reoptimize_with_absences()` — remove 3 workers, verify reassignment
  - Test edge cases: empty workforce, no tasks, all C-level technicians
  - Test priority ordering: critical equipment tasks assigned to A-level first
  - Minimum 30 tests

### Phase 3: MCP Tool Wrappers

- [x] **3.1** Create `agents/tool_wrappers/assignment_tools.py` with tool functions:
  ```
  Tools:
  - optimize_work_assignments(work_package_id, date, shift, available_workers) → list[WorkAssignment]
  - reoptimize_assignments(existing_assignments, absent_worker_ids) → list[WorkAssignment]
  - score_technician_match(worker_id, task_id) → MatchScore
  - get_technician_profiles(plant_id, shift?, specialty?) → list[TechnicianProfile]
  - update_assignment_status(assignment_id, new_status, supervisor_notes?) → WorkAssignment
  ```

- [x] **3.2** Register tools in `agents/tool_wrappers/server.py`

- [x] **3.3** Add tools to Planning agent's tool list in `agents/planning/skills.yaml` or registry

- [x] **3.4** Add tool access tests in `tests/test_agent_tool_access.py`

### Phase 4: API Endpoints

- [x] **4.1** Create `api/routers/assignments.py` router
  ```
  POST   /assignments/optimize              → Generate optimized assignments for a work package
  GET    /assignments/                       → List assignments (filter by date, shift, worker_id, status)
  GET    /assignments/{assignment_id}        → Get assignment detail
  PUT    /assignments/{assignment_id}        → Update assignment (supervisor modifies)
  PUT    /assignments/{assignment_id}/confirm → SUGGESTED → CONFIRMED
  PUT    /assignments/{assignment_id}/start   → CONFIRMED → IN_PROGRESS
  PUT    /assignments/{assignment_id}/complete → IN_PROGRESS → COMPLETED
  POST   /assignments/reoptimize             → Reoptimize with absences
  GET    /assignments/summary                → Shift summary for supervisor dashboard
  ```

- [x] **4.2** Create `api/services/assignment_service.py` connecting router ↔ engine

- [x] **4.3** Register router in `api/main.py`

- [x] **4.4** Add API endpoint tests in `tests/test_api/test_assignments.py`

### Phase 5: Seed Data Enhancement

- [x] **5.1** Update `api/seed.py` to add competency levels to the 25 workers
  ```
  Distribution:
  - Per specialty (5 workers each):
    - 1 A-level (Senior), 2 B-level (Standard), 2 C-level (Junior)
  - Equipment expertise: A-level knows 3-5 equipment types, B knows 2-3, C knows 1-2
  - Certifications: A has 3+, B has 2, C has 1 (SAFETY_BASIC)
  - Years experience: A=10-20, B=5-10, C=1-5
  ```

- [x] **5.2** Add sample `TaskCompetencyRequirement` data to seeded maintenance tasks
  ```
  Rules:
  - Critical equipment tasks → min_level A, requires_certification
  - Standard PM tasks → min_level B
  - Basic inspection tasks → min_level C, supervision_required=False
  ```

- [x] **5.3** Update `tests/test_equipment_library.py` or add `tests/test_seed_competency.py`

### Phase 6: Supervisor Dashboard Widget (Streamlit UI)

- [x] **6.1** Create supervisor assignment view as a new tab in Page 12 (`12_scheduling.py`)
  ```
  Tab: "Crew Assignment" (new tab alongside existing Weekly Programs, Resource Utilization, Gantt)

  Layout:
  ┌─────────────────────────────────────────────────────────┐
  │  [Date picker]  [Shift selector]  [🔄 Optimize]       │
  ├─────────────────────────────────────────────────────────┤
  │  CREW STATUS                                            │
  │  ┌──────────┬───────┬────────┬──────────┬────────────┐ │
  │  │ Nombre   │ Espec │ Nivel  │ Estado   │ Horas asig │ │
  │  ├──────────┼───────┼────────┼──────────┼────────────┤ │
  │  │ García   │ MEC   │ A      │ ✅ Disp  │ 6.0 / 8.0  │ │
  │  │ López    │ MEC   │ B      │ ✅ Disp  │ 4.0 / 8.0  │ │
  │  │ Martínez │ ELEC  │ A      │ ❌ Lic   │ -          │ │
  │  │ ...      │       │        │          │            │ │
  │  └──────────┴───────┴────────┴──────────┴────────────┘ │
  ├─────────────────────────────────────────────────────────┤
  │  SUGGESTED ASSIGNMENTS                                  │
  │  ┌────────────────────────┬──────────┬───────┬───────┐ │
  │  │ Tarea                  │ Técnico  │ Match │ Estado│ │
  │  ├────────────────────────┼──────────┼───────┼───────┤ │
  │  │ PM SAG Mill Bearings   │ García A │  95%  │ [✓]  │ │
  │  │ Insp Conveyor Belt     │ López B  │  82%  │ [✓]  │ │
  │  │ ⚠ Pump Overhaul       │ Ruiz C   │  45%  │ [✎]  │ │
  │  └────────────────────────┴──────────┴───────┴───────┘ │
  │  ⚠ Pump Overhaul: C-level on B-required task.          │
  │     Recommendation: Assign García (A) or add oversight  │
  ├─────────────────────────────────────────────────────────┤
  │  UNASSIGNED (2 tasks)                                   │
  │  • Motor Alignment (requires INSTRUMENTIST — none avail)│
  │  • Crane Inspection (requires cert CRANE_OP — no match) │
  ├─────────────────────────────────────────────────────────┤
  │  [Mark Absent: _______ ] [Re-optimize] [Confirm All]   │
  └─────────────────────────────────────────────────────────┘
  ```

- [x] **6.2** Add crew status metrics (available/absent/total, utilization by specialty)

- [x] **6.3** Add "Mark Absent" functionality — select workers, click re-optimize

- [x] **6.4** Add "Confirm All" / individual confirm buttons for assignments

- [x] **6.5** Add match score color coding (green ≥80, yellow ≥60, red <60) and warnings

- [x] **6.6** Add i18n translations for new UI strings (FR/EN/AR/ES)

### Phase 7: Integration & Skill Update

- [x] **7.1** Update `skills/02-work-planning/create-work-packages/CLAUDE.md` to reference competency requirements when creating WPs

- [x] **7.2** Update scheduling engine (`scheduling_engine.py`) to call assignment optimizer after `create_weekly_program()`

- [x] **7.3** Update workflow integration — after M3 approval, auto-generate assignments for the approved work packages

- [x] **7.4** Add integration test: full flow from work package → optimize assignment → supervisor confirm → status update

### Phase 8: Documentation & Plan Update

- [x] **8.1** Update `MASTER_PLAN.md`: mark GAP-W09 as CLOSED, update T-46 status

- [x] **8.2** Update `CLAUDE.md` key files table with new engine and router

- [x] **8.3** Update `DOCUMENT_INDEX.md` if needed

- [x] **8.4** Update memory files with implementation decisions

---

## 5. File Change Summary

### New Files (7)

| File | Type | Purpose |
|------|------|---------|
| `tools/engines/assignment_engine.py` | Engine | Assignment optimizer (score_match, optimize, reoptimize) |
| `agents/tool_wrappers/assignment_tools.py` | MCP Tools | 5 tool wrappers for agent access |
| `api/routers/assignments.py` | API Router | 8 REST endpoints for assignments |
| `api/services/assignment_service.py` | Service | Router ↔ Engine bridge |
| `tests/test_assignment_engine.py` | Tests | 30+ unit tests for engine |
| `tests/test_api/test_assignments.py` | Tests | API endpoint tests |
| `docs/GAP-W09_EXECUTION.md` | Docs | This file |

### Modified Files (10)

| File | Changes |
|------|---------|
| `tools/models/schemas.py` | Add CompetencyLevel, TechnicianCompetency, TechnicianProfile, TaskCompetencyRequirement, WorkAssignment, AssignmentStatus |
| `tools/models/__init__.py` | Export new schemas |
| `api/database/models.py` | Extend WorkforceModel with competency columns |
| `api/main.py` | Register assignments router |
| `api/seed.py` | Add competency levels to 25 workers, add task competency requirements |
| `agents/orchestration/session_state.py` | Register workforce_assignments + technician_profiles in SWMR |
| `agents/tool_wrappers/server.py` | Register 5 assignment tools |
| `streamlit_app/pages/12_scheduling.py` | Add "Crew Assignment" tab |
| `MASTER_PLAN.md` | Close GAP-W09, update T-46 |
| `tools/engines/__init__.py` | Export AssignmentEngine |

---

## 6. Testing Strategy

| Test File | Tests | Focus |
|-----------|-------|-------|
| `test_assignment_engine.py` | 30+ | score_match, optimize, reoptimize, edge cases |
| `test_api/test_assignments.py` | 15+ | CRUD endpoints, status transitions, validation |
| `test_seed_competency.py` | 5+ | Seed data integrity, competency distribution |
| `test_agent_tool_access.py` | 5+ (update) | Assignment tools registered to correct agents |

**Total new tests: ~55+**

---

## 7. Acceptance Criteria (from MASTER_PLAN.md T-46)

- [x] Technician profiles with A/B/C competency levels per specialty per equipment type
- [x] Task-competency matching: system suggests which technician should do which task
- [x] Supervisor dashboard widget: view crew, see suggestions, confirm/modify assignments
- [x] Re-optimization when workers are absent
- [x] Match score with explanation (why this technician for this task)
- [x] Warnings for under-qualified assignments
- [x] All new code covered by tests (55+ new tests)
- [x] Seed data includes competency profiles

---

## 8. Session Execution Tracking

### Session 18 (Completed in single session)

- [x] Phase 1: Data Model Layer (steps 1.1-1.8)
- [x] Phase 2: Assignment Engine (steps 2.1-2.6)
- [x] Phase 3: MCP Tool Wrappers (steps 3.1-3.4)
- [x] Phase 4: API Endpoints (steps 4.1-4.4)
- [x] Phase 5: Seed Data (steps 5.1-5.3)
- [x] Phase 6: Supervisor Dashboard (steps 6.1-6.6)
- [x] Phase 7: Integration (steps 7.1-7.4)
- [x] Phase 8: Documentation (steps 8.1-8.4)

### Final Verification

- [x] `python -m pytest --tb=short -q` — 2,435 passed (56 new tests)
- [x] New Streamlit tab renders correctly
- [x] Seed data includes competency profiles
- [x] MASTER_PLAN.md updated

---

## 9. Risk Register

| Risk | Mitigation |
|------|------------|
| Schema changes break existing tests | Run full test suite after each schema change |
| DB migration needed for WorkforceModel columns | Add columns as nullable with defaults (backward-compatible) |
| Assignment optimizer too complex | Start with greedy algorithm, upgrade to Hungarian/LP later if needed |
| Supervisor dashboard scope creep | Strict boundary: assignment only, no execution tracking (GAP-W06) |
| i18n missing for new strings | Add to all 4 languages upfront, use consistent key naming |
