# GAP-W08: Usage-Based Task Support — Execution Plan

> **Goal:** Add usage-based (odometer/hours/tonnes/cycles) task scheduling to the AMS platform, covering schema, engines, SAP export, UI, skills, and tests.
> **Estimated effort:** 0.5 session (~400 lines net across 10 files)
> **Prerequisite:** None — self-contained change with full backward compatibility.

---

## Context

### Why this change is needed

In the functional definition workshop (2026-03-10), Jorge Alquinta (reliability/maintenance expert) identified that the platform handles condition-based and fixed-time tasks but is **missing usage-based tasks** — tasks triggered by accumulated operating hours, tonnes processed, or machine cycles rather than calendar time.

**Jorge's exact words:**
> "Está tareas de monitoreo de condición, tareas de tiempo fijo y faltan las tareas por uso, que la diferencia de tiempo fijo es cuando tu defines ya vamos a cambiar una pieza cada seis meses. El de por uso es en función de horas. Si el equipo no opera, el odómetro no avanza hasta que llegue un odómetro."

**Jose Cortinat confirmed immediately:**
> "Sí, claro. Para ciertas actividades o modos de falla, que sean en base a horas operacionales y no tiempo fijo, vamos, digamos tiempo calendario."

### What already works (partially)

The data model already has usage-based frequency units (`HOURS_RUN`, `OPERATING_HOURS`, `TONNES`, `CYCLES` in `FrequencyUnit` enum). Seed data uses them (e.g., "8KH BRY-SAG LINER REPLACE OFFLINE" with 8000 `HOURS_RUN`). The RCM engine has `OPERATIONAL_CAUSES` and `OPERATIONAL_UNITS` sets. But the infrastructure to handle them correctly through the full pipeline is incomplete.

### What's broken

1. **SAP export silently produces wrong data** — `FREQ_UNIT_TO_SAP` dict at `sap_export_engine.py:40` maps only 6 of 9 units. `HOURS_RUN`, `TONNES`, `CYCLES` fall through to `"DAY"` default — **incorrect SAP plan type**
2. **No counter-based SAP plan support** — `SAPMaintenancePlan` lacks `measuring_point` and `scheduling_trigger` fields required for SAP PM counter-based maintenance plans
3. **`HOURS_RUN` missing from RCM validation** — `OPERATIONAL_UNITS` set at `rcm_decision_engine.py:79` omits `HOURS_RUN`, causing false warnings
4. **RCM engine doesn't recommend frequency units** — `validate_frequency_unit()` warns after the fact but doesn't proactively recommend the right unit
5. **UI hides 3 frequency units** — `4_strategy.py` dropdowns (lines 309 and 506) only show 6 of 9 `FrequencyUnit` values
6. **Skills don't guide usage-based decisions** — `perform-fmeca` and `export-to-sap` skills don't document operational unit selection

### Design decision: NO new StrategyType

Per R8 methodology, usage-based is **not** a separate strategy. It is `FIXED_TIME` with an operational `frequency_unit`. The distinction between calendar-triggered and counter-triggered scheduling is modeled via a new `SchedulingTrigger` enum that governs only SAP plan generation.

---

## Files to Modify

| # | File | Change |
|---|------|--------|
| 1 | `tools/models/schemas.py` | Add `SchedulingTrigger` enum, `FREQ_UNIT_TRIGGER` constant, `measuring_point` + `scheduling_trigger` to `SAPMaintenancePlan` |
| 2 | `tools/engines/rcm_decision_engine.py` | Add `HOURS_RUN` to `OPERATIONAL_UNITS`, add `recommend_frequency_unit()` method |
| 3 | `tools/engines/sap_export_engine.py` | Complete `FREQ_UNIT_TO_SAP` mapping, populate `scheduling_trigger` in plan generation, add counter-plan validation |
| 4 | `streamlit_app/pages/4_strategy.py` | Add `HOURS_RUN`, `TONNES`, `CYCLES` to frequency dropdowns |
| 5 | `skills/02-maintenance-strategy-development/perform-fmeca/CLAUDE.md` | Add usage-based frequency unit guidance |
| 6 | `skills/02-work-planning/export-to-sap/CLAUDE.md` | Add operational unit SAP mapping documentation |
| 7 | `tests/test_rcm_decision_tree.py` | Add `HOURS_RUN` validation + `recommend_frequency_unit()` tests |
| 8 | `tests/test_sap_upload.py` | Add counter-based plan generation tests |
| 9 | `tests/test_schemas_usage_based.py` (NEW) | Schema coherence tests for new enum/mapping |
| 10 | `skills/02-maintenance-strategy-development/run-rcm-decision-tree/references/decision-tree-details.md` | Add `HOURS_RUN` to operational units table |

---

## Execution Steps

### Group 1: Foundation — Schema Changes (schemas.py)

- [x] **1.1** Add `SchedulingTrigger` enum after `FrequencyUnit` (line ~199)
  - Values: `CALENDAR`, `COUNTER`
  - Docstring explaining R8 convention: both are FIXED_TIME strategy

- [x] **1.2** Add `FREQ_UNIT_TRIGGER` constant dict mapping each `FrequencyUnit` → `SchedulingTrigger`
  - Calendar: HOURS, DAYS, WEEKS, MONTHS, YEARS
  - Counter: HOURS_RUN, OPERATING_HOURS, TONNES, CYCLES
  - Note: `HOURS` stays CALENDAR for backward compatibility (it was already mapped to `"H"` as time-hours)

- [x] **1.3** Add fields to `SAPMaintenancePlan` class (line 1263)
  - `scheduling_trigger: Optional[SchedulingTrigger] = None` — CALENDAR or COUNTER
  - `measuring_point: Optional[str] = None` — SAP measuring point ID for counter-based plans
  - Both Optional with None defaults for full backward compatibility

### Group 2: RCM Engine Fix (rcm_decision_engine.py)

- [x] **2.1** Add `FrequencyUnit.HOURS_RUN` to `OPERATIONAL_UNITS` set (line 79)
  - Currently missing despite existing in enum and being used in seed data

- [x] **2.2** Update warning message in `validate_frequency_unit()` (line 243) to include `HOURS_RUN`
  - Change: `"(HOURS/OPERATING_HOURS/TONNES/CYCLES)"` → `"(HOURS_RUN/HOURS/OPERATING_HOURS/TONNES/CYCLES)"`

- [x] **2.3** Add `_CAUSE_DEFAULT_UNIT` module-level dict mapping each `Cause` → default `FrequencyUnit`
  - Calendar causes → MONTHS (default)
  - Operational causes → OPERATING_HOURS (default), with TONNES for IMPACT_SHOCK_LOADING, CYCLES for CYCLIC_LOADING

- [x] **2.4** Add `recommend_frequency_unit(cause, equipment_category=None)` static method
  - Returns best `FrequencyUnit` for a given cause
  - Optional `equipment_category` hint refines recommendations:
    - CRUSHER/CONVEYOR/MILL + abrasion → TONNES
    - PUMP/COMPRESSOR/MOTOR + rubbing → HOURS_RUN
  - Always returns valid value (never raises)

### Group 3: SAP Export Engine Fix (sap_export_engine.py)

- [x] **3.1** Replace `FREQ_UNIT_TO_SAP` dict (line 40-47) with complete mapping
  - Add: `"HOURS_RUN": "H"`, `"TONNES": "T"`, `"CYCLES": "CYC"`
  - No more silent fallback to `"DAY"` for unmapped units
  - Import `SchedulingTrigger` and `FREQ_UNIT_TRIGGER` from schemas

- [x] **3.2** Update `generate_upload_package()` (line 130-143) to populate counter-plan fields
  - Determine `scheduling_trigger` from `FREQ_UNIT_TRIGGER[first_wp.frequency_unit]`
  - Pass `scheduling_trigger` to `SAPMaintenancePlan` constructor
  - Leave `measuring_point=None` (must be filled by human planner — SAP measuring points are plant-specific)

- [x] **3.3** Extend `validate_sap_field_lengths()` (line 177) with counter-plan warning
  - If `scheduling_trigger == COUNTER` and `measuring_point is None`: add error message
  - Message: "Counter-based plan requires measuring_point to be filled before SAP upload"

### Group 4: Streamlit UI Fix (4_strategy.py)

- [x] **4.1** Add `FREQUENCY_UNITS` constant near top of file with all 9 units
  - Order: calendar first (HOURS, DAYS, WEEKS, MONTHS, YEARS), then operational (HOURS_RUN, OPERATING_HOURS, TONNES, CYCLES)

- [x] **4.2** Replace hardcoded list in task creation dropdown (line ~309) with `FREQUENCY_UNITS`

- [x] **4.3** Replace hardcoded list in work package creation dropdown (line ~506) with `FREQUENCY_UNITS`

### Group 5: Skill Documentation Updates

- [x] **5.1** Update `perform-fmeca/CLAUDE.md` — add "Determine Frequency Unit" subsection
  - Table: cause type → frequency unit rule
  - Guidance on selecting among operational units (OPERATING_HOURS vs HOURS_RUN vs TONNES vs CYCLES)
  - Explicit note: usage-based is FIXED_TIME strategy (no new StrategyType)
  - Common mistake example: using WEEKS for liner replacement when cause is ABRASION

- [x] **5.2** Update `export-to-sap/CLAUDE.md` — add complete frequency unit mapping
  - Separate time-based and counter-based mapping tables
  - Document `scheduling_trigger` and `measuring_point` fields
  - Add pitfall: counter-plan missing measuring_point

- [x] **5.3** Update `run-rcm-decision-tree/references/decision-tree-details.md`
  - Add `HOURS_RUN` to operational units table (currently lists only HOURS, OPERATING_HOURS, TONNES, CYCLES)

### Group 6: Tests

- [x] **6.1** Add `TestHoursRunInOperationalUnits` class to `tests/test_rcm_decision_tree.py`
  - Test HOURS_RUN is in OPERATIONAL_UNITS set
  - Test HOURS_RUN passes validation for ABRASION and USE causes
  - Test all 5 operational units pass for ABRASION

- [x] **6.2** Add `TestRecommendFrequencyUnit` class to `tests/test_rcm_decision_tree.py`
  - AGE cause → calendar unit
  - ABRASION → operational unit
  - CYCLIC_LOADING → CYCLES
  - MILL + ABRASION → TONNES (equipment context)
  - PUMP + RUBBING → HOURS_RUN (equipment context)
  - Every Cause enum member returns a valid FrequencyUnit (no crash)

- [x] **6.3** Add `TestCounterBasedPlanGeneration` class to `tests/test_sap_upload.py`
  - HOURS_RUN → cycle_unit="H", scheduling_trigger=COUNTER
  - OPERATING_HOURS → scheduling_trigger=COUNTER
  - TONNES → cycle_unit="T", scheduling_trigger=COUNTER
  - CYCLES → cycle_unit="CYC", scheduling_trigger=COUNTER
  - WEEKS → scheduling_trigger=CALENDAR (backward compat)
  - Counter plan without measuring_point → validation error
  - Counter plan with measuring_point → validation passes
  - Existing time-based test case still passes

- [x] **6.4** Create `tests/test_schemas_usage_based.py` (new file)
  - SchedulingTrigger enum values exist
  - Every FrequencyUnit has entry in FREQ_UNIT_TRIGGER
  - Operational units map to COUNTER trigger
  - Calendar units map to CALENDAR trigger
  - SAPMaintenancePlan backward compat (no new required fields)
  - SAPMaintenancePlan counter fields instantiation

### Group 7: Final Verification

- [x] **7.1** Run full test suite: `python -m pytest --tb=short -q`
  - All existing 2,135+ tests must pass
  - New tests must pass (~25 new tests expected)
  - Zero new warnings

- [x] **7.2** Verify seed data consistency
  - `templates/generate_templates.py` already uses `HOURS_RUN` and `OPERATING_HOURS` in seed data
  - Confirm no breakage after schema changes

- [x] **7.3** Update MASTER_PLAN.md — mark GAP-W08 and T-41 as closed

---

## Execution Order

```
1.1 → 1.2 → 1.3  (schemas — foundation for everything)
      ↓
2.1 → 2.2 → 2.3 → 2.4  (RCM engine — independent of SAP)
      ↓
3.1 → 3.2 → 3.3  (SAP export — depends on schemas)
      ↓
4.1 → 4.2 → 4.3  (UI — independent, fast)
      ↓
5.1, 5.2, 5.3  (skills — docs only, independent)
      ↓
6.1 → 6.2 → 6.3 → 6.4  (tests — depend on all engine changes)
      ↓
7.1 → 7.2 → 7.3  (verification)
```

Groups 2, 3, 4, and 5 are independent of each other (all depend only on Group 1). Tests in Group 6 depend on their respective engine groups.

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| No new `StrategyType.USAGE_BASED` | R8 methodology: usage-based IS `FIXED_TIME` with operational frequency_unit. Adding a new strategy type would break the 16-path RCM decision tree. |
| `HOURS` stays CALENDAR | Existing `HOURS` was mapped to `"H"` (SAP time-hours) and in `CALENDAR_UNITS`. Changing would break existing tests/seed. `HOURS_RUN` and `OPERATING_HOURS` are the unambiguous operational variants. |
| `measuring_point` is Optional/None | SAP measuring points are plant-specific master data objects. AMS cannot auto-generate them. Validation warning tells the human planner what to do. |
| `SchedulingTrigger` is separate from `StrategyType` | These are orthogonal concepts. A CONDITION_BASED task could theoretically also have a counter-based schedule. Keeping them separate avoids enum explosion. |
| `recommend_frequency_unit()` uses equipment_category hint | Different equipment types in mining have different primary wear drivers (hours vs tonnes vs cycles). The hint makes recommendations more accurate without requiring full equipment data. |
