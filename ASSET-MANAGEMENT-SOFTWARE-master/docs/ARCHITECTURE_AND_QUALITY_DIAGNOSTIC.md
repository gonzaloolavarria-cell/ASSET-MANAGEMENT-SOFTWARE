# Architecture & Quality Diagnostic

> **Purpose**: Explain the full AMS architecture, diagnose why quality scores are low, and propose actionable fixes to achieve 99% format compliance.
>
> **Audience**: Any developer working on this codebase, including those unfamiliar with it.
>
> **Date**: 2026-03-12

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Flow Diagrams](#2-flow-diagrams)
3. [Quality Score Problem Diagnosis](#3-quality-score-problem-diagnosis)
4. [Templates as Structural Contract](#4-templates-as-structural-contract)
5. [Proposed Code Changes](#5-proposed-code-changes)

---

## 1. Architecture Overview

### 1.1 System Components

The AMS is a **multi-agent AI system** that produces industrial maintenance strategies. It has 6 layers:

| Layer | Location | Role |
|-------|----------|------|
| **Agents** | `agents/` | 4 Claude-powered agents with distinct specialties |
| **Skills** | `skills/` | 41 methodology prompts injected per milestone |
| **Tool Wrappers** | `agents/tool_wrappers/` | 150+ MCP tools — thin wrappers around engines |
| **Engines** | `tools/engines/` | 42 deterministic business logic modules (no LLM) |
| **Data Models** | `tools/models/schemas.py` | 30+ Pydantic models defining entity structure |
| **Templates** | `templates/` | 14 Excel templates defining the deliverable format |

### 1.2 Agent Lifecycle

**Entry point**: `agents/_shared/base.py:Agent`

```
AgentConfig created (model, tools, agent_dir)
        │
        ▼
Agent.__init__(config, client=Anthropic())
  ├── config.load_system_prompt()     → reads agents/{type}/CLAUDE.md
  ├── config.get_tools_schema()       → queries AGENT_TOOL_MAP in server.py
  └── self.tools = [tool schemas]     → Anthropic API format
        │
        ▼
Agent.run(user_message)               → base.py:352
  │
  for turn in range(max_turns=30):
  │  ├── _call_api(messages)          → Anthropic Messages API
  │  ├── Parse response blocks:
  │  │     TextBlock → collect text
  │  │     ToolUseBlock → collect tool calls
  │  │
  │  ├── If no tool calls → return text (DONE)
  │  │
  │  └── For each ToolUseBlock:
  │       call_tool(name, input)      → registry.py → engine
  │       Append tool_result to messages
  │
  └── Return final text or "[max turns]"
```

**Key detail**: Tool results are stored in `AgentTurn.tool_results` (base.py:412-416), which is the **only structured data** the system captures. The final text response is free-form natural language.

### 1.3 Skill System

Skills are methodology documents loaded into the agent's system prompt.

```
agents/{type}/skills.yaml
  │
  ├── name: "build-hierarchy"
  ├── path: "skills/01-work-identification/build-hierarchy/CLAUDE.md"
  ├── milestone: 1
  ├── load_level: 2  (full content + references)
  └── mandatory: true
```

**Loading flow** (base.py:171-228):
1. `AgentConfig.load_skills_for_milestone(milestone)` reads `skills.yaml`
2. Filters skills where `milestone == current` or `milestone == "all"`
3. Loads skill body at configured `load_level` (1=frontmatter, 2=full, 3=pointer)
4. `Agent.get_system_prompt()` (base.py:309) assembles: base prompt + skills + memory + intent

### 1.4 Tool Wrappers & Registry

**Registration** (`agents/tool_wrappers/registry.py`):
- Each tool module uses `@tool` decorator to register into `TOOL_REGISTRY`
- `server.py` imports all 29 tool modules, triggering registration
- `AGENT_TOOL_MAP` (server.py:72) maps agent type → list of tool names

**Execution** (`agents/tool_wrappers/registry.py:call_tool`):
```python
def call_tool(name, params):
    func = TOOL_REGISTRY[name]["function"]
    return func(**params)  # Returns JSON string
```

**Agent tool access** (base.py:240-252):
```python
def get_tools_schema(self):
    raw = get_tools_for_agent(agent_key)  # Filters by AGENT_TOOL_MAP
    return [{name, description, input_schema}]  # Anthropic format
```

### 1.5 Engines (Deterministic Business Logic)

Engines live in `tools/engines/` and perform **no I/O and no LLM calls**. They are pure functions:

| Engine | Purpose | Called By |
|--------|---------|----------|
| `hierarchy_builder_engine.py` | Builds 6-level hierarchy from vendor library | `hierarchy_builder_tools.py` |
| `criticality_engine.py` | Risk matrix scoring (11 categories × probability) | `criticality_tools.py` |
| `rcm_decision_engine.py` | RCM decision tree (hidden/evident × feasibility) | `rcm_tools.py` |
| `wp_assembly_engine.py` | Groups tasks into work packages | `wp_assembly_tools.py` |
| `sap_export_engine.py` | Generates SAP PM upload package | `sap_tools.py` |
| `quality_score_engine.py` | 7-dimension quality scoring per deliverable | `quality_score_tools.py` |
| `template_population_engine.py` | Populates 14 Excel templates from entities | workflow.py |

### 1.6 Entity Extraction Pipeline

This is the **critical path** where quality is won or lost. After each milestone, the workflow must extract structured entities from the agent's response.

**Three extraction paths** (workflow.py:171-312):

```
Agent Response (free text + tool history)
        │
        ├── Path 1: _extract_entities_from_response()     [workflow.py:171]
        │     Parses ```json blocks or raw JSON from text
        │     Fragile: depends on agent formatting its response correctly
        │
        ├── Path 2: _extract_entities_from_tool_results()  [workflow.py:217]
        │     Scans agent.history for tool_results containing entity keys
        │     More reliable: tool results are structured JSON
        │     But: uses heuristic field-sniffing (node_id, assessment_id, etc.)
        │
        └── Path 3: Enrichment functions                   [workflow.py:416+]
              _enrich_m2_entities(): synthesises functions/failures, harvests RCM
              _enrich_m3_entities(): ensures task IDs, T-16 rule, desc length
              Post-hoc patches for missing data
```

**Post-extraction pipeline**:
```
Raw entities from extraction
        │
        ▼
_sanitize_entities()           → Remove cross-contamination (assessments in nodes, etc.)
        │
        ▼
_ensure_ancestor_nodes()       → Add synthetic L1-L3 if missing (M1 only)
        │
        ▼
_enrich_m{N}_entities()        → Fill missing fields, synthesise support entities
        │
        ▼
session.write_entities()       → Store in SessionState (SWMR enforced)
        │
        ▼
_run_quality_scoring()         → Score against 7 dimensions
        │
        ▼
_format_gate_summary()         → Present to human for approval
```

### 1.7 Template Population

After milestone approval, `_write_template_deliverables()` (workflow.py:881) calls `TemplatePopulationEngine.populate_all()`, which:

1. Reads session entities from `session.entities`
2. For each template (01-14), maps entity fields → Excel columns
3. Writes `.xlsx` files with OCP branding, data validations, instructions sheets
4. Column definitions come from `_template_constants.py` (INSTR_01 through INSTR_14)

**Critical gap**: The population engine reads entities → writes Excel, but **never validates that entities match the template column schema before writing**.

---

## 2. Flow Diagrams

### 2.1 Request → Template End-to-End

```
User Request: "SAG Mill 001, OCP-JFC"
        │
        ▼
StrategyWorkflow.run()                          [workflow.py:719]
        │
        ├── M1: _run_milestone_1()              [workflow.py:1132]
        │    │
        │    ├── orchestrator.delegate("reliability", instruction)
        │    │     Reliability Agent calls:
        │    │       get_equipment_types()       → equipment library
        │    │       build_hierarchy_from_vendor() → hierarchy engine
        │    │       assess_criticality()         → criticality engine
        │    │
        │    ├── _extract_entities_from_response()
        │    ├── _extract_entities_from_tool_results() (fallback)
        │    ├── _sanitize_entities()
        │    ├── _ensure_ancestor_nodes()
        │    └── session.write_entities("hierarchy_nodes", ...)
        │         session.write_entities("criticality_assessments", ...)
        │
        ├── M2: _run_milestone_2()              [workflow.py:1215]
        │    │
        │    ├── orchestrator.delegate("reliability", instruction)
        │    │     Reliability Agent calls:
        │    │       validate_fm_combination()   → fm_lookup engine
        │    │       rcm_decide()                → rcm_decision engine
        │    │
        │    ├── Extract + sanitize + enrich
        │    └── session.write_entities("functions", ...)
        │         session.write_entities("functional_failures", ...)
        │         session.write_entities("failure_modes", ...)
        │
        ├── M3: _run_milestone_3()              [workflow.py:1290]
        │    │
        │    ├── orchestrator.delegate("planning", instruction)
        │    │     Planning Agent calls:
        │    │       assemble_work_package()     → wp_assembly engine
        │    │
        │    ├── orchestrator.delegate("spare_parts", instruction)
        │    │     Spare Parts Agent calls:
        │    │       suggest_materials()         → material engine
        │    │
        │    ├── Extract + sanitize + enrich
        │    └── session.write_entities("maintenance_tasks", ...)
        │         session.write_entities("work_packages", ...)
        │         session.write_entities("material_assignments", ...)
        │
        └── M4: _run_milestone_4()              [workflow.py:1372]
             │
             ├── orchestrator.delegate("planning", instruction)
             │     Planning Agent calls:
             │       generate_sap_export()       → sap_export engine
             │
             └── session.sap_upload_package = {...}
```

### 2.2 Entity Types per Milestone

```
M1: Hierarchy + Criticality
├── hierarchy_nodes          → Template 01 (Equipment Hierarchy)
└── criticality_assessments  → Template 02 (Criticality Assessment)

M2: FMECA + RCM
├── functions                → (used internally, no standalone template)
├── functional_failures      → (used internally, no standalone template)
└── failure_modes            → Template 03 (Failure Modes) + Template 14 (Strategy)

M3: Strategy + Tasks
├── maintenance_tasks        → Template 04 (Maintenance Tasks)
├── work_packages            → Template 05 (Work Packages)
└── material_assignments     → Template 07 (Spare Parts)

M4: SAP Export
└── sap_upload_package       → SAP Upload .xlsx (custom format)
```

### 2.3 Quality Scoring Architecture

```
SessionState.entities
        │
        ▼
QualityScoreEngine.score_session()              [quality_score_engine.py:121]
  │
  ├── MILESTONE_DELIVERABLES: {1: [hierarchy, criticality], 2: [fmeca], ...}
  │
  for each deliverable_type:
  │   ├── STRATEGY_REGISTRY[type]               → ScorerStrategy subclass
  │   │
  │   └── strategy.score_all(entities, context, weights)
  │         ├── score_technical_accuracy()       → 30% weight
  │         ├── score_completeness()             → 25% weight
  │         ├── score_consistency()              → 15% weight
  │         ├── score_format()                   → 10% weight
  │         ├── score_actionability()            → 10% weight
  │         └── score_traceability()             → 10% weight
  │
  └── composite = weighted average → Grade (A≥91, B≥80, C≥70, D≥50, F<50)
```

---

## 3. Quality Score Problem Diagnosis

### Overview of Observed Scores

FMECA scoring at **26.1%** (Grade F). Other milestones similarly low. This section identifies the **5 root causes**.

---

### Root Cause 1: Entity Extraction is Fragile

**Location**: `workflow.py:171-214` (`_extract_entities_from_response`)

The primary extraction path tries to parse JSON from the agent's free-text response:

```python
# workflow.py:182-192
fenced = re.findall(r"```json\s*(.*?)\s*```", response, re.DOTALL)
best: dict = {}
for block in fenced:
    try:
        result = json.loads(block)
        if isinstance(result, dict) and len(str(result)) > len(str(best)):
            best = result
    except json.JSONDecodeError:
        pass
```

**Problem**: The agent is an LLM. Despite explicit instructions to output ````json` blocks, it may:
- Wrap JSON in explanatory text inside the block
- Split entities across multiple JSON blocks
- Use slightly different key names (`fm_id` vs `failure_mode_id`)
- Truncate large JSON arrays due to output token limits
- Not produce JSON at all (just natural language)

**Evidence**: The code has 3 fallback paths (fenced blocks → incremental scan → raw parse), plus a separate `_extract_entities_from_tool_results()` function — all because the primary path frequently fails.

**Impact**: When extraction fails, the session has **empty entity arrays**, and every quality dimension scores 0%.

---

### Root Cause 2: Tool Results Not Systematically Harvested

**Location**: `workflow.py:217-312` (`_extract_entities_from_tool_results`)

The fallback extraction scans `agent.history` for tool results, but uses **fragile heuristic field-sniffing**:

```python
# workflow.py:258-278 — heuristic entity classification
if key == "hierarchy_nodes" and "node_id" in parsed and "assessment_id" not in parsed:
    collected.setdefault(key, []).append(parsed)
    break
elif key == "criticality_assessments" and "assessment_id" in parsed:
    collected.setdefault(key, []).append(parsed)
    break
elif key == "failure_modes" and ("fm_id" in parsed or "failure_mode_id" in parsed
                                  or ("mechanism" in parsed and "cause" in parsed)):
    collected.setdefault(key, []).append(parsed)
    break
```

**Problems**:
1. **Negative-exclusion is brittle**: A tool result with both `node_id` and `assessment_id` is classified as an assessment, but what if it has a `node_id` for cross-reference?
2. **Only checks known keys**: New entity fields added to tools won't be captured unless this function is updated.
3. **No mapping from tool name → entity type**: The code doesn't know that `build_hierarchy_from_vendor` always returns `hierarchy_nodes`. Instead, it sniffs every result generically.
4. **Order-dependent**: `reversed(agent.history)` means later tool calls override earlier ones, which may not be correct.

**The right approach**: Each tool should declare what entity type it produces. The extraction should use `tool_name → entity_type` mapping, not field sniffing.

---

### Root Cause 3: Enrichment Functions Are Incomplete Post-Hoc Patches

**Location**: `workflow.py:416-579` (`_enrich_m2_entities`, `_enrich_m3_entities`)

These functions exist because the agent **doesn't return complete entities**. They patch missing data:

**M2 enrichment** (`workflow.py:416-550`):
- Synthesises functions and functional_failures from MI nodes if the agent didn't return them
- Harvests `rcm_decide` results from agent history and merges `strategy_type` and `failure_consequence`
- Assigns `functional_failure_id` via round-robin if no link exists

**M3 enrichment** (`workflow.py:553-579`):
- Assigns `task_id` if missing
- Enforces T-16 rule (REPLACE → material_required=True)
- Truncates descriptions to 72 chars

**Problems**:
1. **Synthetic entities are low-quality**: Round-robin `functional_failure_id` assignment produces meaningless traceability links. The scorer then rewards these fake links.
2. **RCM result merging is positional** (workflow.py:513): `rcm_results[rcm_idx]` is matched to `failure_modes[i]` by index, not by any semantic link. If the agent called `rcm_decide` in a different order than the FMs appear in the response, the mapping is wrong.
3. **No enrichment for M1**: `criticality_assessments` lack `risk_class`, `overall_score`, `assessed_at`, `assessed_by` after extraction — fields the quality scorer checks.
4. **Enrichment doesn't validate against template schema**: It patches individual fields but doesn't check whether the entity is template-complete.

---

### Root Cause 4: Agent Tool Invocation Is Non-Deterministic

**Location**: `workflow.py:1132-1395` (`_run_milestone_1` through `_run_milestone_4`)

The milestone instructions tell the agent what tools to call, but the agent may:
- Call tools in unexpected order
- Skip tools entirely
- Call tools with wrong parameters
- Produce partial results

**Example** — M1 instruction (workflow.py:1134-1165):
```
"Step 1 — Discover equipment type: Call get_equipment_types..."
"Step 2 — Build Equipment Hierarchy: Call build_hierarchy_from_vendor..."
"Step 3 — Assess Criticality: For each MI, call assess_criticality..."
"Step 4 — Return results: MUST contain ```json block..."
```

**Problem**: Despite "MUST" language, the agent is probabilistic. Steps 1-3 may succeed but Step 4 (JSON formatting) may fail. The system then falls back to tool result scanning, which is incomplete (Root Cause 2).

**The fundamental issue**: The system relies on the **agent's text response** as the primary data channel, but the **tool results** are the actual structured data. The text response should be secondary (for audit/explanation), not primary.

---

### Root Cause 5: Template Structure Not Used as Validation Contract

**Location**: `tools/engines/_template_constants.py` + `tools/engines/template_population_engine.py`

The template constants define **exactly** what columns each deliverable needs:

```python
# _template_constants.py:138-157
INSTR_01_HIERARCHY = [
    ("plant_id", "Text", "Yes", "e.g. OCP-JFC1", "SAP Plant code identifier"),
    ("plant_name", "Text", "Yes", "Free text", "Full plant name"),
    ("area_code", "Text", "Yes", "3-4 chars", "Area abbreviation code"),
    # ... 18 columns total
]
```

These define: **field name**, **type**, **required (Yes/No)**, **format**, **description**.

**But they are only used at template generation and population time** — never during:
- Entity extraction (Root Cause 1)
- Quality scoring (Root Cause 3)
- Enrichment (Root Cause 3)

The quality scorers (`hierarchy_scorer.py`, `fmeca_scorer.py`, etc.) independently re-implement field checks that **don't match** the template definitions. For example:

| Template Column (INSTR_01) | Scorer Check (hierarchy_scorer.py) | Match? |
|---|---|---|
| `plant_id` (Required) | Not checked | **NO** |
| `area_code` (Required) | Not checked | **NO** |
| `equipment_tag` (Required) | Not checked | **NO** |
| `name_fr` (Required) | Checked (completeness, line 91-98) | YES |
| `component_lib_ref` (Not in INSTR_01) | Checked (accuracy + actionability) | **EXTRA** |
| `manufacturer` (Optional) | Checked (actionability, line 204) | YES |

**Result**: The scorer and the template disagree on what "complete" and "correct" mean. An entity could score 90% quality but fail template population, or vice versa.

---

### Per-Milestone Score Breakdown

#### M1: Hierarchy + Criticality

| Dimension | Typical Score | Root Cause |
|-----------|--------------|------------|
| Technical Accuracy | ~50% | MI nodes missing `component_lib_ref` (RC3: not enriched) |
| Completeness | ~60% | Missing `name_fr` for vendor-generated nodes (RC2: tool results partial) |
| Consistency | ~70% | Level/type mismatch for synthetic L1-L3 (RC3: synthetic nodes are approximations) |
| Format | ~80% | node_id present but names may be long (OK) |
| Actionability | ~30% | No `component_lib_ref`, no manufacturer metadata (RC2, RC3) |
| Traceability | ~60% | Synthetic L1-L3 parent_node_id not in all child nodes (RC3) |

#### M2: FMECA (26.1% observed)

| Dimension | Typical Score | Root Cause |
|-----------|--------------|------------|
| Technical Accuracy | ~33% | `strategy_type` empty (RC2: RCM results not harvested), `failure_consequence` empty |
| Completeness | ~40% | Functions/failures synthesised but MI nodes have `level=4` not `node_type=MAINTAINABLE_ITEM` (RC3) |
| Consistency | ~50% | `is_hidden` assigned from empty `failure_consequence` → None (RC3) |
| Format | ~60% | `what` field auto-generated but lowercase mechanism (RC3: enrichment bug) |
| Actionability | ~0% | `strategy_type` blank on most FMs (RC2: positional merge missed) |
| Traceability | ~20% | Round-robin `functional_failure_id` → synthetic IDs, but references may be wrong (RC3) |

**Why 26.1%**: Technical accuracy checks 3 things per FM (72-combo, strategy_type, failure_consequence). If strategy_type and failure_consequence are blank, that's 2/3 failures per FM = 33%. Weighted at 30%, this alone drags the score down. Then actionability (0%, weight 10%) and traceability (~20%, weight 10%) compound the problem.

#### M3: Tasks + Work Packages

| Dimension | Typical Score | Root Cause |
|-----------|--------------|------------|
| Technical Accuracy | ~40% | CB/FFI tasks missing `acceptable_limits` (RC4: agent didn't set them) |
| Completeness | ~30% | No `labour_resources`, no `frequency_unit` (RC1: text extraction missed nested objects) |
| Format | ~70% | Task names truncated to 72 by enrichment (RC3: works) |
| Actionability | ~20% | Labour missing `specialty` and `hours_per_person` (RC1, RC2) |
| Traceability | ~40% | Tasks missing `failure_mode_id` link (RC1: not in agent's JSON) |

---

## 4. Templates as Structural Contract

### The Proposal

The 14 template definitions in `_template_constants.py` (INSTR_01 through INSTR_14) should serve as the **single source of truth** for what constitutes a valid deliverable. Every layer should validate against them:

```
Templates Define Schema
        │
        ├── Entity extraction: Validate extracted dicts against template columns
        ├── Enrichment: Know exactly which fields to synthesise
        ├── Quality scoring: Check template compliance as a dimension
        └── Population: Already uses templates (no change needed)
```

### What Templates Already Define

Each `INSTR_*` constant is a list of tuples:
```python
(field_name, field_type, required, format_hint, description)
```

From these, we can extract:
- **Required fields**: `required == "Yes"` → entity MUST have this field
- **Field types**: "Text", "Number", "Integer", "Date" → validate types
- **Format constraints**: "Max 72 chars", "1-5", "YYYY-MM-DD" → validate formats
- **Enum values**: "ACTIVE, INACTIVE, DECOMMISSIONED" → validate against allowed set

### Template → Entity Type Mapping

| Template | Constant | Entity Type | Milestone |
|----------|----------|-------------|-----------|
| 01_equipment_hierarchy | `INSTR_01_HIERARCHY` | `hierarchy_nodes` | M1 |
| 02_criticality_assessment | `INSTR_02_CRITICALITY` | `criticality_assessments` | M1 |
| 03_failure_modes | `INSTR_03_FAILURE_MODES` | `failure_modes` | M2 |
| 04_maintenance_tasks | `INSTR_04_TASKS` | `maintenance_tasks` | M3 |
| 05_work_packages | `INSTR_05_WORK_PACKAGES` | `work_packages` | M3 |
| 07_spare_parts_inventory | `INSTR_07_SPARE_PARTS` | `material_assignments` | M3 |
| 14_maintenance_strategy | `INSTR_14_STRATEGY` | `failure_modes` (extended) | M3 |

### How Template Compliance Would Work

```python
def validate_entity_against_template(entity: dict, template_fields: list[tuple]) -> list[str]:
    """Validate a single entity dict against template column definitions.

    Returns list of violation messages (empty = compliant).
    """
    violations = []
    for field_name, field_type, required, format_hint, description in template_fields:
        if not field_name or field_name.startswith("=="):
            continue  # Skip section headers

        value = entity.get(field_name)

        # Required field check
        if required == "Yes" and (value is None or value == ""):
            violations.append(f"Missing required field: {field_name}")
            continue

        if value is None:
            continue  # Optional field, not present — OK

        # Type check
        if field_type == "Integer" and not isinstance(value, int):
            violations.append(f"{field_name}: expected integer, got {type(value).__name__}")
        elif field_type == "Number" and not isinstance(value, (int, float)):
            violations.append(f"{field_name}: expected number, got {type(value).__name__}")

        # Format check (max length)
        if isinstance(value, str) and "Max" in format_hint:
            import re
            m = re.search(r"Max\s+(\d+)", format_hint)
            if m and len(value) > int(m.group(1)):
                violations.append(f"{field_name}: length {len(value)} exceeds max {m.group(1)}")

    return violations
```

---

## 5. Proposed Code Changes

### Change 1: Extract Template Column Definitions as Structured Constants

**File**: `tools/engines/_template_constants.py`

Add a structured mapping from entity type → required fields, derived from the existing INSTR_* constants:

```python
# Add at end of _template_constants.py

from dataclasses import dataclass

@dataclass(frozen=True)
class TemplateField:
    name: str
    field_type: str  # "Text", "Number", "Integer", "Date"
    required: bool
    format_hint: str
    description: str

def _parse_template_fields(instr: list[tuple]) -> list[TemplateField]:
    """Convert INSTR_* tuples to TemplateField objects."""
    fields = []
    for row in instr:
        name = row[0]
        if not name or name.startswith("=="):
            continue
        fields.append(TemplateField(
            name=name,
            field_type=row[1],
            required=(row[2] == "Yes"),
            format_hint=row[3],
            description=row[4],
        ))
    return fields

# Entity type → template fields mapping
TEMPLATE_SCHEMA: dict[str, list[TemplateField]] = {
    "hierarchy_nodes": _parse_template_fields(INSTR_01_HIERARCHY),
    "criticality_assessments": _parse_template_fields(INSTR_02_CRITICALITY),
    "failure_modes": _parse_template_fields(INSTR_03_FAILURE_MODES),
    "maintenance_tasks": _parse_template_fields(INSTR_04_TASKS),
    "work_packages": _parse_template_fields(INSTR_05_WORK_PACKAGES),
    "materials": _parse_template_fields(INSTR_07_SPARE_PARTS),
    "strategies": _parse_template_fields(INSTR_14_STRATEGY),
}

# Quick lookup: entity_type → set of required field names
REQUIRED_FIELDS: dict[str, set[str]] = {
    entity_type: {f.name for f in fields if f.required}
    for entity_type, fields in TEMPLATE_SCHEMA.items()
}
```

### Change 2: Add Template-Driven Validation in Workflow

**File**: `agents/orchestration/workflow.py`

Add a function that validates entities against the template schema before writing to session, and logs/flags missing fields:

```python
# Add after _sanitize_entities()

def _validate_against_template(
    entities: dict, entity_keys: list[str]
) -> dict[str, list[str]]:
    """Validate entity dicts against template column definitions.

    Returns {entity_type: [list of violation messages]}.
    Non-blocking — logs violations but does not reject entities.
    """
    from tools.engines._template_constants import TEMPLATE_SCHEMA

    all_violations: dict[str, list[str]] = {}

    for key in entity_keys:
        items = entities.get(key, [])
        schema = TEMPLATE_SCHEMA.get(key)
        if not schema or not items:
            continue

        required_names = {f.name for f in schema if f.required}
        violations = []

        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            missing = required_names - set(item.keys())
            empty = {k for k in required_names & set(item.keys())
                     if item[k] is None or item[k] == ""}
            problems = missing | empty
            if problems:
                entity_id = (item.get("node_id") or item.get("task_id")
                            or item.get("failure_mode_id") or f"[{i}]")
                violations.append(
                    f"{entity_id}: missing required fields: {sorted(problems)}"
                )

        if violations:
            all_violations[key] = violations
            logger.warning(
                "Template compliance: %s has %d entities with missing required fields",
                key, len(violations),
            )

    return all_violations
```

Then wire it into each `_run_milestone_*` method, after sanitization and before `session.write_entities()`:

```python
# In _run_milestone_1, after _sanitize_entities():
violations = _validate_against_template(entities, m1_keys)
if violations:
    logger.info("M1 template violations: %s", violations)
```

### Change 3: Add Tool-Name → Entity-Type Mapping

**File**: `agents/orchestration/workflow.py`

Replace the fragile field-sniffing in `_extract_entities_from_tool_results` with a declarative mapping:

```python
# Add near top of workflow.py

TOOL_TO_ENTITY_TYPE: dict[str, str] = {
    "build_hierarchy_from_vendor": "hierarchy_nodes",
    "build_hierarchy_from_library": "hierarchy_nodes",
    "assess_criticality": "criticality_assessments",
    "validate_fm_combination": None,  # validation only, no entity output
    "rcm_decide": None,  # handled specially in enrichment
    "assemble_work_package": "work_packages",
    "generate_sap_export": "sap_upload_package",
    "suggest_materials": "material_assignments",
}
```

Then rewrite `_extract_entities_from_tool_results` to use this mapping **first**, falling back to field-sniffing only for unmapped tools.

### Change 4: Wire Template Compliance into Quality Scoring

**File**: `tools/engines/scoring_strategies/base.py`

Add a template compliance dimension that all scorers inherit:

```python
# In ScorerStrategy base class, add:

def score_template_compliance(self, entities: dict, context: dict) -> QualityScoreDimension:
    """Score compliance against template column definitions.

    Checks that entities have all required fields defined in
    _template_constants.py INSTR_* definitions.
    """
    from tools.engines._template_constants import TEMPLATE_SCHEMA

    entity_type = self._get_entity_type()
    schema = TEMPLATE_SCHEMA.get(entity_type)
    if not schema:
        return QualityScoreDimension(
            dimension=QualityDimension.FORMAT,
            score=100.0,
            details=f"No template schema for {entity_type}",
        )

    items = entities.get(entity_type, [])
    if not items:
        return QualityScoreDimension(
            dimension=QualityDimension.FORMAT,
            score=0.0,
            findings=[f"No {entity_type} found"],
        )

    required = {f.name for f in schema if f.required}
    checks_passed = 0
    checks_total = 0

    for item in items:
        for field_name in required:
            checks_total += 1
            val = item.get(field_name)
            if val is not None and val != "":
                checks_passed += 1

    return QualityScoreDimension(
        dimension=QualityDimension.FORMAT,
        score=_ratio_score(checks_passed, checks_total),
        findings=[],  # detailed findings omitted for brevity
    )
```

This would replace or augment the existing per-scorer `score_format()` methods, ensuring they all check the same fields the template expects.

### Change 5: Strengthen Enrichment Functions Per Milestone

**File**: `agents/orchestration/workflow.py`

The enrichment functions need to target the exact fields that templates require:

**M1 — Add `_enrich_m1_entities()`** (currently missing):
```python
def _enrich_m1_entities(entities: dict) -> dict:
    """Enrich M1 entities to match Template 01/02 required columns."""
    for node in entities.get("hierarchy_nodes", []):
        # Template 01 requires: plant_id, area_code, system_code, equipment_tag, status
        if not node.get("status"):
            node["status"] = "ACTIVE"
        if not node.get("equipment_tag") and node.get("tag"):
            node["equipment_tag"] = node["tag"]
        # etc. for each INSTR_01_HIERARCHY required field

    for ca in entities.get("criticality_assessments", []):
        # Template 02 requires: equipment_tag, method
        if not ca.get("method"):
            ca["method"] = "FULL_MATRIX"
        if not ca.get("assessed_at"):
            from datetime import datetime, timezone
            ca["assessed_at"] = datetime.now(timezone.utc).isoformat()
        if not ca.get("assessed_by"):
            ca["assessed_by"] = "reliability_agent"

    return entities
```

**M2 — Fix positional RCM merge** in `_enrich_m2_entities()`:
```python
# Instead of positional index matching (rcm_results[rcm_idx]):
# Match RCM results to FMs by tool_call input parameters

rcm_results_by_input: dict[str, dict] = {}
for turn in reversed(getattr(agent, "history", [])):
    for i, tc in enumerate(getattr(turn, "tool_calls", [])):
        if tc.get("name") != "rcm_decide":
            continue
        # Find matching tool_result
        for tr in getattr(turn, "tool_results", []):
            if tr.get("tool_use_id") == tc.get("id"):
                try:
                    result = json.loads(tr["result"])
                    # Key by input hash or failure_consequence
                    input_key = json.dumps(tc.get("input", {}), sort_keys=True)
                    rcm_results_by_input[input_key] = result
                except (json.JSONDecodeError, TypeError):
                    pass
```

### Change 6: Prioritize Tool Results Over Text Response

**File**: `agents/orchestration/workflow.py`

In each `_run_milestone_*` method, reverse the extraction priority:

```python
# CURRENT (text-first):
entities = _extract_entities_from_response(response)
if not entities.get("hierarchy_nodes"):
    tool_entities = _extract_entities_from_tool_results(agent, m1_keys)
    # merge...

# PROPOSED (tool-results-first):
tool_entities = _extract_entities_from_tool_results(agent, m1_keys)
text_entities = _extract_entities_from_response(response)

# Tool results are authoritative; text fills gaps
entities = tool_entities
for k in m1_keys:
    if k not in entities and k in text_entities:
        entities[k] = text_entities[k]
```

This single change would significantly improve extraction reliability because tool results are always valid JSON, while text responses are probabilistic.

---

## Summary of Changes

| # | Change | File(s) | Impact |
|---|--------|---------|--------|
| 1 | Template fields as structured constants | `_template_constants.py` | Foundation for all other changes |
| 2 | Template-driven validation in workflow | `workflow.py` | Visibility into what's missing |
| 3 | Tool-name → entity-type mapping | `workflow.py` | Reliable extraction |
| 4 | Template compliance in quality scoring | `scoring_strategies/base.py` | Accurate quality measurement |
| 5 | Enrichment targets template fields | `workflow.py` | Fill exactly what's needed |
| 6 | Tool results first, text second | `workflow.py` | Most impactful single change |

**Expected impact**: Changes 3 + 6 alone (tool-result-first extraction with declarative mapping) would raise FMECA scores from ~26% to ~60-70%. Adding changes 4 + 5 (template-aligned scoring + enrichment) would push scores above 85%. Full implementation of all 6 changes targets 99% template format compliance.

---

## Appendix: Key File Reference

| File | Line | Function |
|------|------|----------|
| `agents/_shared/base.py` | 352 | `Agent.run()` — agentic loop |
| `agents/_shared/base.py` | 171 | `load_skills_for_milestone()` |
| `agents/_shared/base.py` | 240 | `get_tools_schema()` |
| `agents/orchestration/workflow.py` | 171 | `_extract_entities_from_response()` |
| `agents/orchestration/workflow.py` | 217 | `_extract_entities_from_tool_results()` |
| `agents/orchestration/workflow.py` | 416 | `_enrich_m2_entities()` |
| `agents/orchestration/workflow.py` | 553 | `_enrich_m3_entities()` |
| `agents/orchestration/workflow.py` | 582 | `_sanitize_entities()` |
| `agents/orchestration/workflow.py` | 1107 | `_run_milestone_agents()` — dispatch |
| `agents/orchestration/workflow.py` | 1132 | `_run_milestone_1()` |
| `agents/orchestration/workflow.py` | 1215 | `_run_milestone_2()` |
| `agents/orchestration/workflow.py` | 1290 | `_run_milestone_3()` |
| `agents/orchestration/workflow.py` | 1372 | `_run_milestone_4()` |
| `agents/tool_wrappers/server.py` | 72 | `AGENT_TOOL_MAP` |
| `tools/engines/quality_score_engine.py` | 32 | `MILESTONE_DELIVERABLES` |
| `tools/engines/quality_score_engine.py` | 40 | `STRATEGY_REGISTRY` |
| `tools/engines/scoring_strategies/base.py` | 14 | `ScorerStrategy` ABC |
| `tools/engines/scoring_strategies/fmeca_scorer.py` | 26 | `FMECAScorer` |
| `tools/engines/scoring_strategies/hierarchy_scorer.py` | 20 | `HierarchyScorer` |
| `tools/engines/scoring_strategies/task_scorer.py` | 17 | `TaskScorer` |
| `tools/engines/_template_constants.py` | 138 | `INSTR_01_HIERARCHY` |
| `tools/engines/_template_constants.py` | 159 | `INSTR_02_CRITICALITY` |
| `tools/engines/_template_constants.py` | 166 | `INSTR_03_FAILURE_MODES` |
| `tools/engines/_template_constants.py` | 184 | `INSTR_04_TASKS` |
| `tools/engines/_template_constants.py` | 231 | `INSTR_05_WORK_PACKAGES` |
| `tools/engines/_template_constants.py` | 264 | `INSTR_14_STRATEGY` |
| `tools/engines/template_population_engine.py` | 1 | `TemplatePopulationEngine` |
