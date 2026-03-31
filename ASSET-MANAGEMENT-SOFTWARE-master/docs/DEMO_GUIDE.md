# AMS Demo Guide — OCP Maintenance AI

> **Version:** 1.0 — 2026-03-11
> **Audience:** VSC consultants, product managers, technical leads presenting to OCP
> **Platform:** AMS v1.2 (23 Streamlit pages, 4 AI agents, 155 MCP tools)
> **Client context:** OCP (Office Chérifien des Phosphates) — Phosphate Mining, Morocco — Jerada processing facility

---

## Table of Contents

1. [Setup (5 min)](#1-setup-5-min)
2. [Demo Scenarios](#2-demo-scenarios)
   - [2A. 30-Minute Executive Overview](#2a-30-minute-executive-overview)
   - [2B. 60-Minute Full Technical Demo](#2b-60-minute-full-technical-demo)
3. [Page-by-Page Talking Points](#3-page-by-page-talking-points)
4. [Key Concepts Reference](#4-key-concepts-reference)
5. [Known Limitations & Honest Answers](#5-known-limitations--honest-answers)
6. [Frequently Asked Questions](#6-frequently-asked-questions)
7. [Appendix: CLI Agent Execution (Advanced)](#7-appendix-cli-agent-execution-advanced)

---

## 1. Setup (5 min)

### Prerequisites

- Python 3.11+
- Installed dependencies: `pip install -r requirements.txt`
- `.env` file configured (copy from `.env.example`, fill in `ANTHROPIC_API_KEY` and `AMS_ADMIN_API_KEY`)

### Start Sequence

Open **two terminals** in the project root:

```bash
# Terminal 1 — FastAPI backend
uvicorn api.main:app --reload --port 8000

# Terminal 2 — Streamlit UI
streamlit run streamlit_app/app.py
```

### Seed the Database

The database is empty by default. Populate it with OCP-JFC1 demo data (25 workers, 50 inventory items, full equipment hierarchy, 24 months of work order history):

```bash
# Using curl
curl -X POST http://localhost:8000/api/v1/admin/seed-database \
     -H "X-Admin-Key: your_admin_key_from_env"

# Or open Swagger UI at http://localhost:8000/docs → POST /admin/seed-database
```

Expected response: `{"status": "success", "plant": "OCP-JFC1", "workers": 25, "inventory_items": 50}`

### Pre-Demo Verification Checklist

- [ ] Backend responds at `http://localhost:8000/health`
- [ ] Streamlit app loads at `http://localhost:8501`
- [ ] Sidebar shows language selector (FR/EN/AR/ES) and role selector
- [ ] Page 1 (Equipment Hierarchy) shows OCP-JFC1 data
- [ ] Set role to **Consultant** for the full feature view

---

## 2. Demo Scenarios

### 2A. 30-Minute Executive Overview

**Target audience:** Plant Manager, VP Operations, Chief Maintenance Officer, Executive sponsor

**Narrative:** "AMS is a cognitive assistant that makes your reliability engineers 3× more productive. They approve every decision — the AI does the analysis."

| Minute | Page | What to show | Key talking point |
|--------|------|--------------|-------------------|
| 0–3 | **P18 Wizard** | Fill client "ocp" / project "jfc-maintenance-strategy", click "Load OCP Demo Data", advance to Step 4 (execution plan) | "Every engagement starts here. The wizard interviews us about the project, then generates a tailored execution plan with milestones and effort estimates." |
| 3–8 | **P14 Executive Dashboard** | MTBF, MTTR, OEE, Asset Health Index tiles; role selector (switch to Manager — watch KPIs change) | "Management sees one number: the Asset Health Index. Drill down by system or equipment class. Role-filtered — the CFO sees costs, the reliability engineer sees failure rates." |
| 8–15 | **P1 Equipment Hierarchy** | 6-level tree: Plant → Area → System → Subsystem → Equipment → Component; show SAP functional location format | "ISO 14224 compliant structure — exactly how SAP PM organizes it. AI builds this from a simple equipment list in 10 minutes, not 3 days." |
| 15–20 | **P2 Criticality Assessment** | 5×5 matrix, risk class A/B/C colors, weighted score; show SAG Mill as Class A | "The AI calculates the criticality score, the engineer reviews the assumptions and approves. Every gate requires human sign-off. AI-suggested, human-validated." |
| 20–25 | **P6 SAP Review** | SAP upload package: functional locations, task lists, component lists; download `.xlsx` | "The final output is a SAP PM upload package. No re-typing, no translation layer. The reliability engineer reviews and clicks approve — then uploads to SAP." |
| 25–30 | **P23 Troubleshooting** | Search "vibration" on SAG Mill; show symptom match + decision tree steps | "Field technician enters a symptom — even in Arabic or French. The system walks them through a structured diagnosis: tests to run, cost ordered from cheapest first." |

**Closing message (30 seconds):**
> "What would take your team 8–12 weeks — hierarchy, criticality, FMECA, task definition, SAP export — AMS completes in 1–2 weeks with the same quality. Your engineers spend their time on what AI can't do: judging context, building consensus, and approving decisions."

---

### 2B. 60-Minute Full Technical Demo

**Target audience:** Reliability Engineers, Maintenance Planners, Consultants, IT/Digital team

**Narrative:** Walk through the complete M1→M4 workflow using pre-seeded OCP-JFC1 data.

| Minute | Page(s) | What to show | Depth |
|--------|---------|--------------|-------|
| 0–5 | **P18 Wizard** | All 5 steps: project setup → starting point assessment → scope refinement → execution plan → launch + seed deliverables | Show the wizard logic: "Has existing hierarchy? Skip M1-HIER stage. PM optimization? Start at M3." Emphasize effort estimate and stage breakdown. |
| 5–15 | **P1 + P2** | P1: 6-level hierarchy nodes, functional location codes (OCP-JFC1-PHOS-GRIND-SAGM-001), component list. P2: criticality matrix, risk class assignment, mandatory vs. optional PM | "Hierarchy decomposition respects ISO 14224 level 1–6 taxonomy. Functional locations are pre-formatted for SAP IE01. AI validates: no equipment node without a parent." |
| 15–25 | **P3 + P16** | P3: FMECA table with failure modes, mechanisms, causes (72-combo validated), RPN = S×O×D. P16: FMECA worksheet view (matches OCP template) | "Every failure mode is drawn from a validated MASTER table of 72 Mechanism+Cause combinations. AI cannot hallucinate failure modes — it selects from the approved taxonomy." |
| 25–35 | **P4 + P10** | P4: RCM decision tree paths (CBM/TBM/RTF/FFI), maintenance strategy cards. P10: Planner Assistant — show 72-char SAP short text validation, task type, frequency | "The RCM decision tree is encoded as a skill. The AI follows the logic: safety-critical? → always PM. Hidden failure? → FFI task. Does PM prevent it? → if not, RTF." |
| 35–42 | **P12** | Scheduling: calendar view. Crew Assignment tab: competency matrix, optimize button, match scores (color coded), re-optimize with absence | "5-dimension competency scoring: specialty 30%, competency level 25%, equipment expertise 20%, certification 15%, availability 10%. Greedy optimizer assigns the best match." |
| 42–50 | **P22 + P6** | P22: Execution checklist — step-by-step, predecessor locks (can't check step 3 without 2), gate questions, condition codes. P6: SAP package review, REQUIRES_REVIEW flags, download `.xlsx` | "Checklists are gate-enforced. When an AI field has confidence < 0.7, it's flagged REQUIRES_REVIEW — the engineer must explicitly confirm it before SAP export." |
| 50–57 | **P13 + P5** | P13: Weibull distribution plot, shutdown management (daily/shift reports, schedule), reliability analysis. P5: Analytics — failure frequency, cost drivers, Pareto | "The Weibull engine fits historical failure data to predict remaining useful life. Shutdown management generates a Gantt-style critical path — same logic as project CPM." |
| 57–60 | **P24** | ROI calculator (NPV, payback period, BCR), budget tracking with variance alerts, avoided cost, man-hours saved | "For the CFO: enter investment cost + avoided downtime hours → get NPV, payback period, benefit-cost ratio. For OCP scale: $80M maintenance budget, 10% savings = $8M/year avoided cost." |

**Q&A buffer: last 5 minutes.** See [Section 6 — FAQ](#6-frequently-asked-questions) for prepared answers.

---

## 3. Page-by-Page Talking Points

### M0 — Field Capture

**Page 8 — Field Capture**
- "Technicians submit work requests from the field: text, voice (Whisper transcription), or photo (Claude Vision). No paper forms."
- "Multilingual input — they can speak in Darija or French. AI structures the anomaly into a standard format."
- "GPS-aware: the system suggests the nearest equipment TAG based on location."

**Page 9 — Work Requests**
- "The planner queue. All field-captured anomalies land here, sorted by AI-assessed priority."
- "Planner reviews, adjusts priority, assigns to a work order, or rejects with a reason."
- "Full audit trail: who submitted, when, what AI assigned as failure mode and severity."

---

### M1 — Hierarchy + Criticality

**Page 1 — Equipment Hierarchy**
- "6-level hierarchy: Plant → Functional Area → System → Subsystem → Equipment → Component. This is the ISO 14224 taxonomy."
- "Functional Location codes (e.g., `OCP-JFC1-PHOS-GRIND-SAGM-001`) are pre-formatted for SAP transaction IE01. No manual reformatting."
- "AI builds the hierarchy from a simple equipment list (TAG + description + area). What takes a consultant 3 days, the AI does in 10 minutes with human review."
- "Every node requires a parent. AI validates referential integrity before allowing the milestone gate to pass."

**Page 2 — Criticality Assessment**
- "Criticality = Safety Impact × Environmental Impact × Production Impact × Frequency. Weighted on a 1–5 scale each."
- "Risk class A (score ≥ 18): full RCM analysis mandatory. Class B (10–17): targeted PM. Class C (< 10): run-to-failure acceptable."
- "The AI computes the score, the reliability engineer validates the weights and approves. Every gate is human-gated."
- "Criticality results feed directly into the RCM decision tree — the FMECA depth is calibrated to the risk class."

---

### M2 — FMECA + RCM

**Page 3 — FMEA Analysis**
- "FMECA table: Function → Functional Failure → Failure Mode → Mechanism → Cause → Effects → RPN (Severity × Occurrence × Detectability)."
- "72-combo validation: AI can only assign Mechanism+Cause combinations from the MASTER table. Zero hallucination of failure modes."
- "If a failure mode combination doesn't exist in the MASTER table, AI flags it for human review rather than inventing one."
- "Each failure mode generates one or more maintenance tasks — this is the core of the RCM output."

**Page 4 — Strategy Development**
- "RCM decision tree: Is it safety or environmental critical? → always PM. Is it a hidden failure? → Functional Failure Inspection (FFI). Does PM prevent or predict failure? → CBM or TBM. Otherwise → RTF."
- "The AI follows the decision tree as a skill — step by step, logging its reasoning at each node."
- "Strategy output: one maintenance strategy per equipment, with task type (PM/CBM/FFI/RTF) and intervals."

**Page 16 — FMECA Worksheets**
- "Printable FMECA worksheet in the format OCP reliability team already uses — no reformatting for internal review."
- "Export to Excel for review sessions with client. Each worksheet row maps to one failure mode with full RPN calculation."

---

### M3 — Work Planning

**Page 10 — Planner Assistant**
- "AI drafts maintenance task descriptions constrained to 72 characters (SAP PM short text limit). Automatically validated."
- "Task types map to SAP PM scheduling: Fixed Date (TBM), Counter-Based (usage-based), Condition-Based (CBM), Unscheduled (RTF)."
- "Planner reviews, edits, and approves each task. AI confidence score shown — fields below 0.7 require explicit planner confirmation."

**Page 11 — Backlog Management**
- "Backlog prioritization: risk score × urgency factor × resource availability. Automatically re-ranked on each refresh."
- "Overdue work orders highlighted. Backlog grouper clusters similar tasks for efficiency (same equipment, same specialty required)."
- "Work packages assembled automatically: tasks grouped by trade, work area, and estimated duration."

**Page 12 — Scheduling + Crew Assignment**
- "Interactive scheduling calendar. Drag-and-drop work order placement (feature in roadmap)."
- "Crew Assignment optimizer: 5-dimension scoring — specialty match (30%), competency level A/B/C (25%), equipment expertise (20%), certification current (15%), availability this period (10%)."
- "Re-optimize with absences: mark a technician absent → system re-assigns all their open work to the next best available."
- "Match score color coding: green (>80%), orange (60–80%), red (<60%) — supervisor sees at a glance who is under-matched."

**Page 22 — Execution Checklists**
- "Ordered step checklists for complex maintenance tasks. Predecessors are gate-locked — technician cannot confirm step 4 without completing step 3."
- "Each step has a condition code: OK / Deviation / Hold / Safety Stop. Deviations trigger supervisor review."
- "Gate questions embedded: 'Was oil sample taken before starting?' → mandatory yes before proceeding."
- "Supervisor closure: final sign-off includes any open deviations, a pass/fail decision, and optional comments."

---

### M4 — SAP Export

**Page 6 — SAP Review**
- "SAP PM upload package: Maintenance Items (IA05), Task Lists (IA01), Component Lists (IE07), Maintenance Plans (IP41)."
- "Each record shows SAP field mapping — the reliability engineer verifies before approving."
- "Fields with AI confidence < 0.7 are flagged REQUIRES_REVIEW in yellow. The engineer cannot approve without explicitly confirming each."
- "One-click export: downloads `.xlsx` file pre-formatted for SAP batch upload. No re-typing."
- "SAP short text validated: 72 characters max, no special characters that break SAP import."

---

### Cross-Cutting Tools

**Page 5 — Analytics**
- "Cross-equipment analytics: failure frequency by equipment class, cost driver Pareto, MTBF trends."
- "Drill-down from plant level to individual equipment failure mode."
- "Export charts for management reporting in PDF or PNG."

**Page 7 — Overview Dashboard**
- "Bird's-eye view of all open work: by milestone, by status (PENDING/IN_PROGRESS/APPROVED/REJECTED)."
- "Gate status summary: how many milestones are waiting for human approval right now."

**Page 13 — Reliability Analysis**
- "Weibull distribution fitting from failure history. Predicts next failure date and remaining useful life."
- "Shutdown management: daily reports, shift focus suggestions (critical path priority), Gantt-style schedule generation using topological sort + critical path analysis."
- "Jackknife analysis: identify outlier equipment with unusual failure patterns vs. fleet average."

**Page 14 — Executive Dashboard**
- "Role-filtered KPIs: Manager sees total budget, avoided cost, OEE; Reliability Engineer sees MTBF, FMECA coverage %; Planner sees backlog size, schedule adherence."
- "Asset Health Index: single 0–100 score aggregating all reliability indicators. Trend line for management review."
- "Drill-down: click any KPI to see contributing equipment and failure modes."

**Page 15 — Reports & Data Import**
- "Data import: upload Excel or CSV files using AMS templates. 14 import types supported (equipment hierarchy, criticality, FMECA, work orders, spare parts, workforce, etc.)."
- "Auto-detects column mapping with confidence indicators. Shows validation errors with row/column reference and fix suggestions."
- "Export: download any entity set (tasks, work packages, SAP packages) as Excel or PDF."

**Page 17 — Defect Elimination**
- "Root Cause Analysis (RCA) workflow: event capture → causal chain → corrective actions → CAPA tracking."
- "5-Why and Fault Tree templates built in. AI suggests probable causes based on failure mode history."

**Page 18 — Project Wizard** *(see [Section 2A](#2a-30-minute-executive-overview) above for demo script)*
- "5-step guided setup: project configuration → starting point assessment → scope refinement → execution plan generation → launch."
- "Smart logic: if client already has a hierarchy, wizard skips M1-HIER stage. If they have SAP PM plans, starts at M3."
- "Generates a YAML execution plan with stage dependencies. Each stage becomes a trackable deliverable."

**Page 19 — Progress Dashboard**
- "Session-level progress: which milestones are complete, in-progress, or blocked."
- "Clickable checkboxes per stage. Auto-saves to execution plan file."
- "Per-milestone completion bars. Gates clearly marked with approval status."

**Page 20 — Equipment Manual Chat**
- "Upload equipment manuals (PDF, TXT, MD) → ask questions in natural language."
- "Quadrilingual: 'Quels sont les points de graissage du SAG Mill?' → answers in French with reference to manual section."
- "Claude reads the entire manual in one context window (up to 200K tokens). No vector database needed."
- "Prompt caching: subsequent questions on the same manual are 90% cheaper (cached context)."

**Page 21 — Deliverables Tracking**
- "Consultant-facing: track all project deliverables (DRAFT → IN_PROGRESS → SUBMITTED → UNDER_REVIEW → APPROVED)."
- "Time tracking per deliverable. Budget vs. actual hours with variance alerts."
- "Client review tab: client approves or rejects each deliverable with comments."
- "Wizard auto-seeds deliverables from the execution plan — no manual entry needed."

**Page 23 — Troubleshooting**
- "214-symptom diagnostic catalog extracted from the 72 FM MASTER cards."
- "5 equipment-specific decision trees: SAG Mill, Ball Mill, Slurry Pump, Belt Conveyor, Cone Crusher."
- "Jaccard keyword matching: technician describes symptom in natural language → AI finds most similar documented symptoms."
- "Minimum-cost-first test ordering: AI sequences diagnostic tests from cheapest/easiest to most expensive."

**Page 24 — Financial Dashboard**
- "ROI Calculator: input investment cost + annual avoided downtime hours + labor savings → NPV, payback period, benefit-cost ratio, IRR."
- "Budget Tracking: planned vs. actual by category (LABOR, MATERIALS, CONTRACTORS, etc.). Variance alerts at 10%/20% thresholds."
- "Cost Drivers: Pareto analysis of equipment by total annual impact (failure cost + PM cost + downtime cost)."
- "Man-Hours Savings: compare traditional consulting hours vs. AI-assisted hours by activity type."

---

## 4. Key Concepts Reference

### R8 Maintenance Strategy Methodology

R8 is the VSC-branded maintenance strategy development methodology. It structures the work into 4 milestones (M1–M4) with human-approval gates between each. The methodology draws on IEC 60300-3-11 (RCM), ISO 14224 (equipment taxonomy), and SAP PM best practices. AMS digitizes and AI-accelerates each step while keeping the engineer in control of every output.

### 4-Milestone Gate Workflow (M1→M4)

```
M1: Hierarchy + Criticality → [Human Gate] →
M2: FMECA + RCM Strategy   → [Human Gate] →
M3: Tasks + Work Packages   → [Human Gate] →
M4: SAP Upload Package      → [Human Gate] → SAP PM
```

Each gate has 4 outcomes: APPROVED (proceed), MODIFIED (adjust + resubmit), REJECTED (redo), or PENDING (waiting for review). AI agents only advance with explicit human approval. The gate review captures who approved, when, and any modification comments — full audit trail.

### 72-Combo MASTER Table

The FMECA Failure Mode MASTER table defines 72 valid combinations of Failure Mechanism + Failure Cause for industrial equipment. The AI must select from this validated list — it cannot invent failure modes. This prevents hallucination and ensures every FMECA output is auditable. The table is maintained in `skills/00-knowledge-base/data-models/failure-modes/MASTER.md`.

Example combinations:
- Mechanical Wear + Normal Degradation
- Corrosion + Chemical Attack
- Fatigue + Cyclic Loading
- Overload + Excessive Process Demand

### SAP PM Functional Location Structure

SAP PM organizes equipment as a tree of Functional Locations (FL). AMS generates FLs in the format:
```
OCP-JFC1-PHOS-GRIND-SAGM-001
└── Plant (OCP-JFC1)
    └── Area (PHOS — Phosphate Processing)
        └── System (GRIND — Grinding)
            └── Subsystem (SAGM — SAG Mill)
                └── Equipment (001 — Unit 1)
```
This 6-level structure maps directly to SAP levels 1–6. AMS validates the format and ensures no orphaned nodes before generating the upload package.

### SWMR — Single Writer, Multiple Reader

Each entity type (hierarchy, criticality, FMECA, tasks, etc.) is "owned" by exactly one agent. The owner agent writes; all others read. This prevents concurrent write conflicts in the multi-agent system. For example: the Reliability agent owns FMECA data, the Planning agent owns work packages, the Orchestrator owns session state.

### Confidence Scoring

Every AI-generated field carries a confidence score between 0.0 and 1.0. Fields with confidence < 0.7 are automatically flagged `REQUIRES_REVIEW`. The UI highlights these fields in yellow and blocks the milestone gate until the engineer explicitly confirms or corrects each one. This ensures no low-confidence data slips into SAP without human review.

---

## 5. Known Limitations & Honest Answers

These are the current boundaries of the prototype. Answer these proactively in demos — it builds trust.

| Limitation | Current State | Roadmap |
|------------|--------------|---------|
| **Pre-seeded data only** | Demo uses synthetic OCP-JFC1 data. Real OCP equipment data requires file import or API connection. | G-02 (data import) is Phase B priority. File upload with 14 template types now works. |
| **Agent workflow is CLI-only** | `python -m agents.run` works from terminal. The Streamlit UI cannot trigger M1→M4 directly — it shows the results. | G-17 (workflow API endpoint) is planned for Phase A. Will add `POST /workflow/run` with SSE progress. |
| **SAP connection is mock** | The SAP export produces a structured `.xlsx` — no live RFC/BAPI connection. Manual upload to SAP required. | G-11 (real SAP connection) is Phase E — after production hardening. |
| **Voice/image capture is future** | Page 8 has the UI scaffold. Whisper/Deepgram transcription and Claude Vision are not wired up yet. | G-08 (field capture integration) is Phase D. |
| **SQLite database (prototype)** | SQLite works for single-user demo. Not suitable for concurrent multi-user production use. | G-06 (PostgreSQL migration) is Phase C. Alembic migration scripts planned. |
| **Single-user, no authentication** | No JWT tokens or login system. All API endpoints are publicly accessible (except 2 admin endpoints). | G-07 (JWT auth) is Phase C. |
| **Offline mode not available** | Streamlit requires server connection. No PWA/local cache. | GAP-W03 is Phase E — likely requires a different frontend (React Native or PWA). |

---

## 6. Frequently Asked Questions

**Q: Can the AI replace the reliability engineer?**
A: No — and this is by design. The AI generates analysis for the engineer to validate. Every milestone gate requires explicit human approval. The AI accelerates the analysis (3× productivity); the engineer provides the judgment, context knowledge, and approval authority. "Cognitive prosthesis, not replacement."

**Q: How long does the M1→M4 workflow take for one equipment?**
A: With AI assistance: 2–4 hours for a complex piece of equipment (SAG Mill). Traditionally: 2–3 days. For a plant of 500 equipment items, AMS reduces the project from 18 months to 5–6 months.

**Q: Is OCP's data secure?**
A: The system runs on-premise in OCP's infrastructure. Data never leaves OCP's network. When the AI analyzes data, only the structured context (equipment function, failure modes) is sent to the Claude API — not raw proprietary data. OCP owns the outputs.

**Q: What about SAP integration?**
A: Phase 1 (current demo) produces a validated `.xlsx` for manual SAP upload. Phase 2 (planned) adds live read/write via SAP RFC/BAPI — same approach used by major SAP integrators. The functional location and task list structure already matches SAP PM exactly.

**Q: Does it work in Arabic?**
A: Yes — the UI is fully quadrilingual: French, English, Arabic, and Spanish. Field technicians can input in any language, including dialectal Arabic (Darija). The AI understands multilingual input and responds in the same language.

**Q: Can multiple teams work simultaneously?**
A: The current prototype is single-session. Multi-user support requires the PostgreSQL migration (Phase C) and JWT authentication. Architecture already supports it — the SWMR (Single Writer, Multiple Reader) pattern prevents conflicts between concurrent agents.

**Q: What AI models power the system?**
A: Three Claude models for different tasks:
- **Claude Opus** (most capable): Reliability agent — FMECA and RCM analysis
- **Claude Sonnet**: Orchestrator + Planning agent — workflow coordination, task definition, SAP export
- **Claude Haiku** (fastest, cheapest): Spare Parts agent — material assignment, BOM lookup

**Q: How does it handle equipment not in the library?**
A: The equipment resolver uses fuzzy matching + Levenshtein distance to find the closest match in the 15-type equipment library. If confidence < 0.7, it presents the top 3 candidates to the operator for selection. New equipment types can be added to `data/libraries/equipment_library.json`.

**Q: What if a failure mode doesn't fit the 72-combo rule?**
A: The engineer flags it for MASTER table extension. The process for adding a new combination is defined in `gemini.md` — it requires validation against IEC 60300 and approval from the VSC methodology lead before adding to the MASTER table. The AI cannot bypass this rule.

**Q: How much does it cost to run?**
A: Rough estimate for Claude API usage:
- One equipment M1→M4: ~$0.50–$2.00 in Claude tokens
- Full plant (500 equipment): ~$500–$1,000 total for the strategy development project
- Ongoing monthly usage (troubleshooting + planning assistant): ~$50–$200/month
- Compared to: 1 VSC consultant = $15,000–$20,000/month. AMS pays for itself in the first week.

**Q: How do you handle the 72-character SAP short text limit?**
A: The Planner Assistant validates every task description against the 72-character limit in real time. The AI is prompted with this constraint and generates descriptions that fit. If it exceeds the limit, it auto-truncates with a warning for the planner to review the truncation.

**Q: Can it import existing SAP data?**
A: Yes — Page 15 supports import of SAP historical work orders (WO type, dates, costs, functional location). This feeds the Weibull analysis and Pareto analysis. PI System / sensor data integration is planned for Phase D.

---

## 7. Appendix: CLI Agent Execution (Advanced)

This section is for technical demos where you want to show live AI agent execution.

> **Prerequisite:** `ANTHROPIC_API_KEY` must be set in `.env`. This is **not** required for the standard UI demo (Sections 2A and 2B use pre-seeded data).

### Run Full M1→M4 Workflow

```bash
# Activate your Python environment
source venv/bin/activate  # or: venv\Scripts\activate on Windows

# Run full workflow for SAG Mill at JFC plant
python -m agents.run "SAG Mill 001" --plant OCP-JFC

# Other examples
python -m agents.run "Slurry Pump P-101" --plant OCP-JFC
python -m agents.run "Belt Conveyor BC-03" --plant OCP-JFC --start-milestone 2
```

### What to Expect

```
[Orchestrator] Starting M1: Hierarchy + Criticality for SAG Mill 001
[Reliability]  Building equipment hierarchy... (6 nodes)
[Reliability]  Running criticality assessment... (Risk Class: A)
[Gate M1]      PRESENTED — awaiting human review
>>> Human input: APPROVE / MODIFY / REJECT?
```

- **4 human gates** — one per milestone. Press Enter to approve or type a modification comment.
- **Expected time:** 10–30 minutes per equipment (varies with AI response time and number of failure modes).
- **Logs saved to:** `2-state/session-YYYYMMDD-HHMMSS.json`
- **Checkpoint recovery:** if interrupted, resume with `--resume 2-state/session-XXX.json`

### Monitor in Real-Time

While the CLI runs, you can watch the results appear in the Streamlit UI — refresh any page to see the latest data as the agents write to the database.

### Known CLI Issues (G-01 — Not Yet Fully Tested)

The agent workflow has never been run end-to-end with a live API key. Expect integration bugs, particularly:
- Agent tool call format mismatches
- Database write conflicts between agents
- Memory loading errors if client memory files don't exist

These are tracked in **G-01** (Phase A priority). The CLI demo is for technical audiences willing to see real AI output and debug issues in real-time. For executive demos, use Sections 2A and 2B with pre-seeded data.

---

*Document maintained by VSC. Update after each demo with lessons learned, new talking points, and FAQ additions.*
*Last updated: 2026-03-11 (AMS v1.2)*
