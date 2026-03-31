# CLAUDE.md — OCP Maintenance AI (AMS)

## Project Overview

AI-powered asset management and maintenance solution for industrial plants (mining, energy, chemicals). Multi-agent system that executes the R8 maintenance strategy methodology: from equipment hierarchy to SAP PM upload. The human approves at 4 milestone gates; AI agents perform the analysis.

- **Client:** OCP (Office Chérifien des Phosphates) — Phosphate Mining, Morocco
- **Firm:** Value Strategy Consulting (VSC)
- **Stack:** Python, FastAPI, Streamlit, Claude API, SQLite (prototype)

## Repository Structure

```
agents/                  4 AI agents + orchestration + tool wrappers (150 MCP tools)
  orchestrator/          Coordinator agent (Sonnet) — workflow, delegation, quality
  reliability/           Reliability Engineer (Opus) — criticality, FMECA, RCM
  planning/              Planning Specialist (Sonnet) — tasks, WPs, SAP export
  spare-parts/           Spare Parts Specialist (Haiku) — materials, BOM
  _shared/               Base class, memory, paths, observability
  orchestration/         Workflow, milestones, session state, execution plan
  tool_wrappers/         150 MCP tool wrappers for deterministic engines

skills/                  41 skills organized by milestone category (00-06)
  00-knowledge-base/     Reference documents, data models, methodologies
  01-work-identification/ Field capture → structured work request
  02-*/                  Maintenance strategy, work planning skills
  03-*/                  Reliability engineering, defect elimination
  05-*/                  General functionalities (import, export, quality)
  06-*/                  Orchestration (KPIs, reports, health score)

tools/                   39 deterministic engines + validators + data models
  engines/               Business logic (hierarchy, criticality, RCM, SAP, KPI, etc.)
  models/                Pydantic schemas (schemas.py — 30+ models)
  validators/            Data validation (hierarchy, SAP, quality rules)

api/                     FastAPI backend (18 routers, services, middleware)
streamlit_app/           23-page Streamlit UI (pages/ directory)
data/libraries/          Equipment + Component JSON libraries (source of truth)
templates/               14 AMS templates + client project structure
tests/                   2,400+ pytest tests
scripts/                 Wizards, eval runner, audit, generators
docs/                    Technical docs (governance, architecture, glossary)
sap_mock/                Synthetic SAP PM data for testing
asset-management-methodology/  Source PDFs (RCM textbook, ISO 14224, SAP R8)
```

## Key Conventions

- **Safety-first:** AI outputs are always DRAFT; human validates before SAP submission
- **72-combo rule:** All failure modes MUST use valid Mechanism+Cause from MASTER table (`skills/00-knowledge-base/data-models/failure-modes/MASTER.md`)
- **T-16 rule:** REPLACE tasks MUST have materials assigned
- **SAP_SHORT_TEXT_MAX = 72** characters for structured descriptions
- **Multilingual:** French + English + Arabic + Spanish (field input)
- **SWMR:** Single Writer, Multiple Reader — each entity type owned by one agent
- **Confidence scoring:** Fields with confidence < 0.7 flagged as REQUIRES_REVIEW

## Key Files

| File | Purpose |
|------|---------|
| `gemini.md` | Project constitution — schemas, behavioral rules, architecture |
| `DOCUMENT_INDEX.md` | Master routing table for all documentation |
| `MASTER_PLAN.md` | Living plan — capabilities, gaps, phases, task backlog |
| `agents/run.py` | CLI entry point — `python -m agents.run "SAG Mill" --plant OCP-JFC` |
| `agents/_shared/base.py` | Unified Agent class (Claude API loop + skill loading) |
| `agents/definitions/orchestrator.py` | Creates all 4 agents sharing one Anthropic client |
| `agents/orchestration/workflow.py` | 4-milestone workflow with human gates |
| `agents/*/skills.yaml` | Source of truth for skill→agent assignments |
| `api/config.py` | Environment variables (6 vars, see `.env.example`) |
| `api/seed.py` | Synthetic data generator — `POST /admin/seed-database` |
| `tools/models/schemas.py` | All Pydantic data models (30+ schemas) |
| `tools/engines/sap_export_engine.py` | SAP PM upload package generation |
| `tools/engines/assignment_engine.py` | Competency-based work assignment optimizer (GAP-W09) |
| `api/routers/assignments.py` | REST endpoints for crew assignment optimization |

## Workflow

4-milestone gates with human approval:

```
M1: Hierarchy + Criticality  →  M2: FMECA + RCM  →  M3: Strategy + Tasks  →  M4: SAP Export
```

Gate flow: `PENDING → IN_PROGRESS → PRESENTED → APPROVED / MODIFIED / REJECTED`

## Testing

```bash
python -m pytest --tb=short -q                    # Full suite (2,400+ tests)
python -m pytest tests/test_equipment_library.py   # Library integrity
python -m scripts.eval_runner.cli trigger          # Skill trigger accuracy
```

## Skills System

41 skills with YAML frontmatter, assigned to agents via `skills.yaml` files.
Each skill has: `CLAUDE.md` (prompt), `evals/` (trigger + functional tests), `references/`.
Classification: 27 capability-uplift + 14 encoded-preference.
Registry: `skills/SKILL_MASTER_REGISTRY.md`.
