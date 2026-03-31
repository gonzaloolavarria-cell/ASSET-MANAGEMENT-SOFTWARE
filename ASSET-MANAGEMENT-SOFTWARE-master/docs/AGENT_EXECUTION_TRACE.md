# Agent Execution Trace — G-01 Integration Fixes

> **Status:** Pre-live-run analysis complete. Ready for first live execution with real API key.
> **Date:** 2026-03-11 (Session 14)
> **Author:** VSC Engineering

---

## Summary of Integration Bugs Found and Fixed

During the G-01 analysis (static code review without live API), 3 critical integration bugs were discovered and fixed. A live execution trace will be appended when `ANTHROPIC_API_KEY` is available.

---

## Bug 1: StrategyWorkflow Never Created Anthropic Client

**File:** `agents/orchestration/workflow.py`

**Problem:**
```python
# BEFORE (broken)
def __init__(self, ..., client: Anthropic | None = None, ...):
    self.orchestrator = create_orchestrator(client=client)  # client=None always from CLI
```
When called from CLI (`agents/run.py`), no client was passed → all agents had `self.client = None` → `agent.run()` immediately raised `RuntimeError: Agent has no Anthropic client`.

**Fix:**
```python
# AFTER (fixed)
if client is None:
    client = Anthropic()  # reads ANTHROPIC_API_KEY from env automatically
self.orchestrator = create_orchestrator(client=client)
```

---

## Bug 2: All 4 Agent Configs Referenced Non-Existent Legacy Prompts

**Files:** `agents/definitions/orchestrator.py`, `reliability.py`, `planning.py`, `spare_parts.py`

**Problem:**
```python
# BEFORE (broken) — 'agents/definitions/prompts/' directory does not exist
ORCHESTRATOR_CONFIG = AgentConfig(
    system_prompt_file="orchestrator_prompt.md",  # FileNotFoundError
    use_skills=True,
    ...
)
```
The new `agent_dir`-based CLAUDE.md files existed at `agents/orchestrator/CLAUDE.md`, etc., but were not being used.

**Fix:** Switch all 4 configs to `agent_dir` mode:
```python
# AFTER (fixed)
ORCHESTRATOR_CONFIG = AgentConfig(
    agent_dir="agents/orchestrator",  # loads agents/orchestrator/CLAUDE.md
    model="claude-sonnet-4-6",        # updated model
    ...
)
```

---

## Bug 3: Workflow Called Only Orchestrator — Specialists Never Invoked

**File:** `agents/orchestration/workflow.py`

**Problem:**
```python
# BEFORE (broken)
response = self.orchestrator.run(instruction)  # Claude Sonnet as orchestrator
# ↑ Orchestrator's 27 tools are for validation/reporting — NOT hierarchy/FMECA/tasks
# ↑ Specialists (reliability=54 tools, planning=58 tools) were NEVER called
# ↑ session.entities (hierarchy_nodes, failure_modes, etc.) were NEVER populated
```

**Architectural gap:** The orchestrator's CLAUDE.md says "delegate to specialists," but no delegation tools existed in the MCP registry. The `orchestrator.delegate()` method existed but was never called.

**Fix:** Add direct specialist orchestration in `_execute_milestone()`:
```python
# AFTER (fixed) — workflow directly orchestrates specialists
def _execute_milestone(self, gate):
    response = self._run_milestone_agents(gate)  # dispatches to correct specialist
    ...

def _run_milestone_1(self, context) -> str:
    response = self.orchestrator.delegate("reliability", instruction)  # calls Reliability agent
    entities = _extract_entities_from_response(response)  # parses JSON from response
    self.session.write_entities("hierarchy_nodes", entities["hierarchy_nodes"], "reliability")
    self.session.write_entities("criticality_assessments", entities["criticality_assessments"], "reliability")
    return response
```

**JSON extraction:** `_extract_entities_from_response()` module-level function tries:
1. ` ```json ... ``` ` fenced block
2. First `{...}` JSON object
3. Entire response as raw JSON

---

## G-20 Fix: SAP Export to .xlsx

**File:** `tools/engines/sap_export_engine.py`

**Added:** `SAPExportEngine.write_to_xlsx(package, output_path)` method:
- 3 sheets: Functional Locations, Task Lists, Maintenance Plans
- Styled headers (dark blue with white text)
- Field length enforcement: `SAP_SHORT_TEXT_MAX=72`, `SAP_FUNC_LOC_MAX=40`
- Auto-column sizing
- Output: `sap_export/{session_id}_sap_upload.xlsx`
- Called automatically by workflow on M4 approval

---

## G-17 Fix: FastAPI Workflow Endpoint

**File:** `api/routers/workflow.py`

**4 new endpoints:**
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/workflow/run` | Start session (returns 202 + session_id) |
| GET | `/api/v1/workflow/{id}` | Poll status + entity counts |
| POST | `/api/v1/workflow/{id}/approve` | Submit gate decision |
| GET | `/api/v1/workflow/sessions` | List all sessions |

**Gate synchronization:** Uses `threading.Event` — workflow thread blocks at each gate until `/approve` is called from the UI.

**Session states:** `STARTING → RUNNING → AWAITING_APPROVAL → RUNNING → ... → COMPLETED | FAILED | REJECTED`

---

## Live Execution Checklist (TODO when API key available)

- [ ] Set `ANTHROPIC_API_KEY` in `.env`
- [ ] Run: `python -m agents.run "SAG Mill 001" --plant OCP-JFC --output session_live_01.json`
- [ ] Capture full stdout + stderr to `docs/traces/live_run_01.log`
- [ ] Record: first M1 agent response, entity counts after each milestone, gate summaries
- [ ] Document any additional integration bugs found
- [ ] Verify `.xlsx` file generated at `sap_export/`
- [ ] Update this document with actual execution trace

---

## Architecture After Fixes

```
CLI: python -m agents.run "SAG Mill" --plant OCP-JFC
  └── StrategyWorkflow(human_approval_fn=cli_approval)
        └── create_orchestrator(client=Anthropic())  ← auto-created from env
              ├── OrchestratorAgent (claude-sonnet-4-6, 27 tools)
              ├── ReliabilityAgent  (claude-opus-4-6,  54 tools)
              ├── PlanningAgent     (claude-sonnet-4-6, 58 tools)
              └── SparePartsAgent   (claude-haiku-4-5, 3 tools)

M1: orchestrator.delegate("reliability", hierarchy+criticality instruction)
     → ReliabilityAgent.run() → uses build_hierarchy_from_vendor, assess_criticality tools
     → returns JSON → workflow parses → session.write_entities("hierarchy_nodes", ...)
     → human gate → approve/modify/reject

M2: orchestrator.delegate("reliability", fmeca+rcm instruction)
     → ReliabilityAgent.run() → uses validate_fm_combination, rcm_decide tools
     → returns JSON → session.write_entities("failure_modes", ...)
     → human gate

M3: orchestrator.delegate("planning", tasks+wp instruction)
     orchestrator.delegate("spare_parts", materials instruction)
     → PlanningAgent + SparePartsAgent → session.write_entities(...)
     → human gate

M4: orchestrator.delegate("planning", sap instruction)
     → PlanningAgent → session.sap_upload_package = {...}
     → human gate → approve → SAPExportEngine.write_to_xlsx() → sap_export/*.xlsx
```
