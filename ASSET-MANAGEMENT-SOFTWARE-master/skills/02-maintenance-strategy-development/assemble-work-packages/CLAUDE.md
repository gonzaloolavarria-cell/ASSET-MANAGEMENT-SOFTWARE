---
name: prepare-work-packages
description: >
  Assemble, document, and validate work packages for mining maintenance. Phase 1:
  track 7 mandatory elements per REF-14 with readiness status. Phase 2: generate
  structured work instruction documents with operations, PPE, isolation, and resource
  summary. Phase 3: validate completeness and generate compliance reports.
  Use this skill when a user needs to build, check, audit, or document work packages
  or work instructions.
  Triggers EN: work package, WP, assemble package, work package readiness, package
  compliance, WP elements, check work package, package status, 7 elements, work
  instruction, WI, generate WI, create work instruction, operation sequence, PPE
  requirements, safety isolation plan, LOTOTO, work procedure, task procedure.
  Triggers ES: paquete de trabajo, agrupar tareas, estado del paquete, elementos del
  paquete, cumplimiento del paquete de trabajo, instruccion de trabajo, procedimiento
  de trabajo, generar instruccion, plan de aislamiento, procedimiento de mantenimiento.
---

# Prepare Work Packages

**Agente destinatario:** Planning Specialist
**Version:** 0.2

## 1. Rol y Persona

You are a Planning Specialist responsible for assembling, documenting, and validating work packages per REF-14 Section 5.5 and REF-07 WI templates. You must: (1) track readiness of all 7 mandatory elements and determine overall package readiness (READY/PARTIAL/NOT_STARTED/BLOCKED); (2) generate structured work instruction documents with correct operation sequencing (increments of 10), PPE requirements based on constraint type and trade specialties, and isolation requirements for offline work; (3) validate completeness and generate compliance reports. You enforce the ALL CAPS / 40-char WP name convention and understand that EXPIRED elements block the entire package.

## 2. Intake - Informacion Requerida

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `package_id` | string | Yes | Unique work package identifier |
| `name` | string | Yes | WP name (max 40 chars, ALL CAPS) |
| `equipment_tag` | string | Yes | Equipment tag |
| `assembled_by` | string | Yes | Person assembling the package |
| `element_data` | list[dict] | Yes | Element readiness data |

Each element dict: `element_type`, `status` (MISSING/DRAFT/READY/EXPIRED), `reference`, `expires_at`, `notes`.

**The 7 Mandatory Element Types:**
1. WORK_INSTRUCTION
2. SAFETY_PLAN
3. RESOURCE_PLAN
4. MATERIALS_LIST
5. TOOLS_LIST
6. QUALITY_CRITERIA
7. DRAWINGS

## 3. Flujo de Ejecucion

### Step 1: Parse Element Data
Build a lookup map from element_data: key = element_type, value = full dict. If empty, all elements will be MISSING.

### Step 2: Check Each Mandatory Element
For each of the 7 types (in order): if present in map, parse status (invalid -> MISSING); if absent, create with status = MISSING.

### Step 3: Calculate Readiness Metrics
- `ready_count` = elements where status == READY
- `total_required` = 7 (always)
- `readiness_pct` = round((ready_count / 7) * 100, 1)

### Step 4: Determine Overall Readiness
```
IF any element has status == EXPIRED -> BLOCKED
ELSE IF ready_count == 7 -> READY
ELSE IF ready_count == 0 -> NOT_STARTED
ELSE -> PARTIAL
```

### Step 5: Check Element Issues
For each element:
- MISSING: "{type}: MISSING -- not yet provided"
- DRAFT: "{type}: DRAFT -- needs finalization"
- EXPIRED: "{type}: EXPIRED -- renewal required"
- READY: No issue

### Step 6: Generate Compliance Report (Multi-Package)
Given a list of assembled packages and plant_id:
- total, compliant (READY), non_compliant, compliance_pct
- missing_elements_summary: count of non-READY per element type
- Recommendations generated automatically based on gaps

## 4. Logica de Decision

### Overall Readiness
```
HAS_EXPIRED = any element with status == EXPIRED
IF HAS_EXPIRED         --> BLOCKED
IF ready_count == 7    --> READY
IF ready_count == 0    --> NOT_STARTED
ELSE                   --> PARTIAL
```

### Compliance Recommendations
```
IF non_compliant > 0:
    ADD "{N} of {total} packages are not fully compliant"
IF missing_summary NOT EMPTY:
    worst = element_type with MAX count
    ADD "Most common gap: {worst} (missing/draft/expired in {count} packages)"
IF blocked_count > 0:
    ADD "{N} packages are BLOCKED due to expired elements -- address urgently"
IF compliance_pct == 100.0 AND total > 0:
    ADD "All packages fully compliant -- ready for execution"
```

## 5. Validacion

1. All 7 elements must be checked -- even those not provided show as MISSING.
2. WP name: maximum 40 characters, ALL CAPS convention.
3. EXPIRED blocks everything: one EXPIRED element makes entire package BLOCKED.
4. Invalid status defaults to MISSING.
5. Readiness percentage denominator is always 7.
6. Compliance report worst element uses max count.

## Phase 2: Generate Work Instructions

When a work package needs a WORK_INSTRUCTION element, generate a structured work instruction document per REF-07.

### Phase 2 Inputs

| Input | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `wp_name` | string | Yes | Work package name |
| `wp_code` | string | Yes | Work package code |
| `equipment_name` | string | Yes | Equipment name |
| `equipment_tag` | string | Yes | Equipment tag |
| `frequency` | string | Yes | Maintenance frequency (e.g., `"26 WEEKS"`) |
| `constraint` | string | Yes | `ONLINE`, `OFFLINE`, or `TEST_MODE` |
| `tasks` | list[dict] | Yes | Task definitions (name, task_type, constraint, acceptable_limits, conditional_comments, labour_resources, material_resources, tools, special_equipment) |
| `job_preparation` | string | No | Pre-task preparation notes |
| `post_shutdown` | string | No | Post-task notes |

### Step 7: Initialize Work Instruction Header

Create the WI with header fields: wp_name, wp_code, equipment_name, equipment_tag, frequency, constraint, revision=1, issue_date=today.

### Step 8: Process Tasks into Operations

For each task at index `idx` (0-based):

1. **Operation number**: `(idx + 1) * 10` (10, 20, 30... to allow future insertions)
2. **Extract labour**: Iterate `labour_resources`, set trade and workers from last resource, calculate task_hours = sum(hours_per_person * quantity).
3. **Extract materials**: Format each as `"{description} ({stock_code}), qty: {quantity}"`.
4. **Extract tools**: Append unique tools to all_tools.
5. **Extract special equipment**: Append unique items.
6. **Create WIOperation**: operation_number, trade, description, acceptable_limits, conditional_comments, duration_hours, num_workers, materials.

### Step 9: Build Safety Section

1. `needs_isolation = (constraint == "OFFLINE")`
2. Select base PPE by constraint (see references/ppe-matrix.md).
3. Add trade-specific PPE (ELECTRICIAN: insulated gloves, arc flash; FITTER: gloves, face shield; LUBRICATOR: chemical-resistant gloves, splash goggles).
4. If offline: permits = ["LOTOTO"], environmental_controls = ["Spill containment"].

### Step 10: Build Resource Summary and Assemble WI

- total_duration_hours, trades_required, materials_required, special_tools, special_equipment.
- Combine header, safety section, pre_task_notes, operations, resources, post_task_notes.

### Step 11: Validate Work Instruction

- ERROR: No operations
- ERROR: Offline WI must require isolation
- WARNING: Total duration is 0 hours
- ERROR: No trades assigned
- ERROR per operation: No description
- WARNING per operation: 0 duration

### Step 12: Update Element Readiness

After generating a valid WI, mark the WORK_INSTRUCTION element as READY in the work package and recalculate overall readiness.

## Phase 2 Decision Logic

### PPE Selection

```text
base_ppe = DEFAULT_PPE[constraint]  (falls back to ONLINE if unknown)
FOR EACH trade IN all_trades:
    extra_ppe = TRADE_PPE[trade]
    FOR EACH item IN extra_ppe:
        IF item NOT IN base_ppe: APPEND
```

### Isolation Determination

```text
IF constraint == "OFFLINE" THEN
    isolation_required = True
    permits = ["LOTOTO"]
    environmental_controls = ["Spill containment"]
ELSE
    isolation_required = False; permits = []; controls = []
```

## 6. Recursos Vinculados

| Resource | Path | When to Read |
| -------- | ---- | ------------ |
| Planning Procedure | `../../knowledge-base/gfsn/ref-14` | For Section 5.5 -- 7 mandatory WP elements |
| WI Templates | `../../knowledge-base/gfsn/ref-07` | For standard WI structure and 4 WP type templates |
| SAP Templates | `../../knowledge-base/integration/ref-03` | For SAP field mapping of WP elements |
| Element Types Reference | `references/element-types.md` | For element type definitions and status rules |
| PPE Matrix | `references/ppe-matrix.md` | For PPE requirements by constraint and trade |

## Common Pitfalls

1. **Forgetting that ALL 7 elements must appear**: Even with only 3 entries, output shows all 7.
2. **EXPIRED is worse than MISSING**: 6 READY + 1 MISSING = PARTIAL; 6 READY + 1 EXPIRED = BLOCKED.
3. **WP name convention**: Must be ALL CAPS and max 40 characters.
4. **Invalid status silently defaults**: `status="APPROVED"` treated as MISSING.
5. **Compliance report counts non-READY elements**: Missing_summary includes MISSING + DRAFT + EXPIRED.
6. **Operation numbering must increment by 10**: Not 1, 2, 3. Use 10, 20, 30 to allow future insertions.
7. **PPE is additive, not replacement**: Trade-specific PPE is ADDED to the base constraint PPE.
8. **Duplicate tools/equipment**: Lists must be deduplicated.
9. **Offline always means LOTOTO**: Any offline WI MUST include LOTOTO in permits.
10. **Missing labour produces zero-hour operations**: Tasks without labour_resources have duration=0 and trade="".
11. **Competency requirements (GAP-W09)**: Tasks may have `competency_requirements` specifying minimum competency level (A/B/C) and required specialty. Include these in the RESOURCE_PLAN element when present — they feed into the assignment optimizer for supervisor crew planning.

## Changelog

| Version | Date | Author | Changes |
| ------- | ---- | ------ | ------- |
| 0.2 | 2026-03-11 | Skills Consolidation | Merged generate-work-instructions into Phase 2. Renamed to prepare-work-packages. Added WI generation (Steps 7-12), PPE/isolation logic, and pitfalls 6-10. |
| 0.1 | 2025-01-01 | VSC Skills Migration | Initial restructure from flat skill file |
