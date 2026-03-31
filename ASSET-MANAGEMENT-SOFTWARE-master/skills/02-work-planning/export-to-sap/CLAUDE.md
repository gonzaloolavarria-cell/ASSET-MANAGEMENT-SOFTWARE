---
name: export-to-sap
description: >
  Generate SAP PM upload templates from work packages for mining maintenance operations.
  Produces: linked Maintenance Items, Task Lists, and Maintenance Plan in DRAFT status with
  cross-reference and field-length validation. Use this skill when a user needs to export
  maintenance data to SAP format or prepare upload templates.
  Triggers EN: SAP export, SAP upload, maintenance item, task list SAP, SAP template,
  export to SAP, SAP PM, SAP work order, upload to SAP, SAP maintenance plan.
  Triggers ES: exportar a SAP, plantilla SAP, item de mantenimiento SAP, lista de tareas
  SAP, subir a SAP, plan de mantenimiento SAP.
---

# Export to SAP

**Agente destinatario:** Planning Specialist
**Version:** 0.1

## 1. Rol y Persona

You are a Planning Specialist responsible for generating SAP PM upload templates per REF-03 (3 Linked SAP Templates). You must produce correctly linked Maintenance Items ($MI), Task Lists ($TL), and a Maintenance Plan, validate cross-references and field lengths, and always output in DRAFT status for human review. You enforce SAP field constraints (72-char short_text, minimum 0.5h duration, minimum 1 worker) and map constraints/frequencies to SAP codes.

## 2. Intake - Informacion Requerida

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `work_packages` | list[WorkPackage] | Yes | At least 1 work package |
| `plant_code` | string | Yes | SAP plant code |
| `plan_description` | string | No | Maintenance plan description |
| `tasks` | dict[str, Task] | No | Map of task_id to task details |

WorkPackage fields: name, constraint (ONLINE/OFFLINE), frequency_value, frequency_unit, allocated_tasks.
Task fields: name (truncated to 72 chars), labour_resources (specialty, quantity, hours_per_person).

## 3. Flujo de Ejecucion

### Step 1: Validate Input
At least one work package required. ValueError if empty. Initialize tasks dict to empty if not provided.

### Step 2: Generate 3 SAP Templates Per Work Package
For each WP at index `idx` (1-based):

**Maintenance Item ($MI{idx}):**
- item_ref: "$MI{idx}", description: wp.name, order_type: "PM03"
- func_loc: "" (filled later), main_work_center: "" (filled later)
- planner_group: 1, task_list_ref: "$TL{idx}", priority: "4"

**Task List ($TL{idx}) with Operations:**
For each allocated task: look up in tasks dict. If found: short_text = task.name[:72], duration = max(sum(qty*hrs), 0.5), num_workers = max(sum(qty), 1). If not found: placeholder values.
- SAPOperation: operation_number, work_centre, control_key="PMIN", short_text, duration_hours, unit="H", num_workers
- system_condition: ONLINE->1, OFFLINE->3

**Maintenance Plan (one per export, from first WP):**
- category: "PM", cycle_value/unit from first WP frequency
- call_horizon_pct: 50, scheduling_period: 14 DAY

### Step 3: Assemble Upload Package
CRITICAL: Always DRAFT. Must be reviewed by human planner before SAP upload.

### Step 4: Validate Cross-References
- Every $MI.task_list_ref must exist in task list set
- Every $TL must be referenced by at least one $MI

### Step 5: Validate SAP Field Lengths
- short_text max 72 characters per operation

## 4. Logica de Decision

### Constraint Mapping
```
ONLINE  --> 1 (Running)
OFFLINE --> 3 (Stopped)
Default --> 1
```

### Frequency Unit Mapping

**Time-based plans (SAP single-cycle, calendar-triggered):**
```
DAYS -> "DAY", WEEKS -> "WK", MONTHS -> "MON"
YEARS -> "YR", HOURS -> "H"
```

**Counter-based plans (SAP performance-based, usage-triggered):**
```
HOURS_RUN -> "H", OPERATING_HOURS -> "H"
TONNES -> "T", CYCLES -> "CYC"
```

When `scheduling_trigger=COUNTER`, the exported plan requires a SAP measuring point ID (`measuring_point` field) which must be filled by the human planner before upload. The system leaves this blank with a validation warning.

### Task Duration
```
duration = SUM(lr.quantity * lr.hours_per_person)
IF duration == 0 THEN duration = 0.5
num_workers = SUM(lr.quantity)
IF num_workers == 0 THEN num_workers = 1
```

## 5. Validacion

1. At least one work package required.
2. Cross-reference integrity: $MI <-> $TL bidirectional.
3. short_text max 72 characters.
4. ALWAYS DRAFT -- never production-ready.
5. Minimum duration 0.5h, minimum workers 1.
6. Plan frequency from first WP only.

## 6. Recursos Vinculados

| Resource | Path | When to Read |
|----------|------|-------------|
| SAP Templates | `../../knowledge-base/integration/ref-03` | For 3 linked SAP template structures and field definitions |
| Planning Procedure | `../../knowledge-base/gfsn/ref-14` | For WP element requirements feeding SAP export |
| SAP Field Constraints | `references/sap-field-constraints.md` | For field length limits and code mappings |

## Common Pitfalls

1. **ALWAYS DRAFT -- never auto-upload**: func_loc and main_work_center must be completed by human.
2. **short_text truncation**: SAP limits to 72 chars. Long task names lose meaning when cut.
3. **Frequency from first WP only**: Plan cycle may be incorrect for subsequent packages.
4. **Missing task lookup**: Unknown task_id produces placeholder with generic text.
5. **Constraint mapping defaults**: Unrecognized constraint defaults to 1 (Running).
6. **Orphaned task lists**: Validation catches $TL not referenced by any $MI.
7. **Counter-plan missing measuring_point**: When frequency_unit is HOURS_RUN/OPERATING_HOURS/TONNES/CYCLES, the plan has scheduling_trigger=COUNTER. Validation flags missing measuring_point. Do NOT upload to SAP until the measuring point ID is assigned.
8. **HOURS vs HOURS_RUN confusion**: HOURS is calendar-based (backward compat). HOURS_RUN is counter-based. For a liner replacement at 8000 running hours, use HOURS_RUN.

## Cross-System Alignment (OR SYSTEM)

**OR Equivalents:** `design-sap-pm-blueprint` (AG-003, Gate G3) + `load-sap-master-data` (AG-003, Gate G3)

### Complementarity

| Aspect | AMS `export-to-sap` | OR `design-sap-pm-blueprint` | OR `load-sap-master-data` |
|--------|---------------------|------------------------------|---------------------------|
| Focus | Generate upload files | Design FL hierarchy + PM/MM config | Load equipment, BOMs, PM plans |
| Output | CSV/JSON for SAP upload | Blueprint document (.docx) | SAP master data packages |
| Scope | Task lists, maintenance items | Full PM/MM configuration | Equipment, BOMs, PM plans |
| Validation | Field-length, cross-ref | Configuration rules | Data quality >95% |

**Shared SAP Field Validations:**
- Functional location: max 40 chars, format `SITE-PLANT-AREA-SYS-EQUIP`
- Task list description: max 40 chars
- Maintenance item: linked to exactly 1 task list
- Damage code groups: mapped from 18 VSC FM mechanisms
- Cause codes: mapped from 46 VSC FM causes

AMS generates the data; OR designs the blueprint and loads it. Both share the same SAP field constraints.

## Changelog

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.2 | 2026-03-05 | Phase 5 Alignment | Added cross-system alignment with OR SAP skills |
| 0.1 | 2025-01-01 | VSC Skills Migration | Initial restructure from flat skill file |
