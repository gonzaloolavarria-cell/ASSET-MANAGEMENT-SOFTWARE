# G-03 Execution Plan — Guided Demo Flow

> **Status:** COMPLETE (Session 17, 2026-03-11)
> **Created:** 2026-03-11
> **Last Updated:** 2026-03-11
> **Estimated Sessions:** 1–2 (A + B)
> **Related Gaps:** G-03, G-04, T-17, T-18
> **Save to:** `docs/G-03_EXECUTION.md` (copy there at session start)

---

## Context

**The gap:** AMS has 23 working Streamlit pages, 4 AI agents, and 155 MCP tools — but no orchestrated narrative that ties them together for a client demo. A product manager showing OCP the platform today would have to improvise a story across disconnected pages. There is no "golden path."

**Why it blocks progress:**
- G-03 is classified P2 (Demo Readiness) — it directly unblocks client meetings and pilot conversations.
- Without a demo guide, the team must re-invent the demo narrative every time, risking inconsistency.
- Page 18 (Wizard) — the natural demo entry point — has hardcoded English strings, no `apply_style()` call, and no feedback widget. It doesn't match the visual quality of other pages.

**Deliverables:**
1. `docs/DEMO_GUIDE.md` — step-by-step demo walkthrough (T-17)
2. Polished Page 18 Wizard with i18n, styling, Demo Mode button (T-18)
3. MASTER_PLAN.md updated: G-03 marked closed

**Important note on demo scope:**
- The Streamlit UI pages show pre-seeded OCP-JFC1 data (DB must be seeded via `POST /admin/seed-database`).
- Live agent workflow (M1→M4 via `python -m agents.run`) is *not* part of G-03 — that's G-01. The demo guide uses pre-seeded data for the UI tour and describes CLI execution as an optional "advanced" section.

---

## Prerequisites — G-04 Quick Win (5 minutes)

Before any demo, the database must be populated. This is T-03 from the backlog.

- [ ] **P.1** Start the FastAPI backend (`uvicorn api.main:app --reload`)
- [ ] **P.2** Call `POST /api/v1/admin/seed-database` with the admin key header:
  ```
  curl -X POST http://localhost:8000/api/v1/admin/seed-database \
       -H "X-Admin-Key: <AMS_ADMIN_API_KEY from .env>"
  ```
- [ ] **P.3** Verify response contains OCP-JFC1 plant, 25 workers, 50 inventory items
- [ ] **P.4** Open Page 1 (Equipment Hierarchy) in Streamlit — confirm data is visible

---

## Session A: Demo Guide Creation (T-17)

**Deliverable:** `docs/DEMO_GUIDE.md`
**Goal:** A consultant can pick up this doc, set up in 5 minutes, and run a polished 30- or 60-minute demo with OCP.

### Phase 1: Document Structure

- [ ] **1.1** Create `docs/DEMO_GUIDE.md` with this top-level structure:
  ```
  # AMS Demo Guide — OCP Maintenance AI
  ## 1. Setup (5 min)
  ## 2. Demo Scenarios
     ### 2A. 30-Minute Executive Overview
     ### 2B. 60-Minute Full Technical Demo
  ## 3. Page-by-Page Talking Points
  ## 4. Key Concepts Reference
  ## 5. Known Limitations & Honest Answers
  ## 6. Frequently Asked Questions
  ## 7. Appendix: CLI Agent Execution (Advanced)
  ```

### Phase 2: Setup Section

- [ ] **2.1** Write **Section 1 — Setup (5 min)**:
  - Prerequisites: Python 3.11+, `pip install -r requirements.txt`, `.env` from `.env.example`
  - Start sequence:
    ```bash
    # Terminal 1: FastAPI backend
    uvicorn api.main:app --reload --port 8000

    # Terminal 2: Streamlit UI
    streamlit run streamlit_app/app.py
    ```
  - Seed database: `curl -X POST .../admin/seed-database -H "X-Admin-Key: ..."` (or Postman)
  - Set role to "Consultant" in sidebar selector
  - Verify checklist: 5 checkboxes (backend up, UI loads, sidebar shows OCP-JFC1, data in P1, role selector works)

### Phase 3: Demo Scenarios

- [ ] **3.1** Write **Section 2A — 30-Minute Executive Overview** (target: Plant Manager, VP Operations):

  | Minute | Page | What to show | Talking point |
  |--------|------|--------------|---------------|
  | 0–3 | P18 Wizard | Fill OCP/JFC, run to Step 4 | "We start every engagement with the wizard — it generates a tailored execution plan." |
  | 3–8 | P14 Executive Dashboard | KPIs: MTBF, MTTR, OEE, Health Score | "Management sees one number: the Asset Health Index. Drill-down by system." |
  | 8–15 | P1 Equipment Hierarchy | 6-level tree (Plant→Component) | "ISO 14224 compliant hierarchy — same structure SAP PM uses." |
  | 15–20 | P2 Criticality | 5×5 matrix, risk class A/B/C | "AI assists the criticality workshop — the engineer validates and approves." |
  | 20–25 | P6 SAP Review | Functional location + task list | "Output is a SAP PM upload package — no re-typing, direct upload." |
  | 25–30 | P23 Troubleshooting | Symptom search on SAG Mill | "Field technician enters a symptom, AI walks through the decision tree." |

- [ ] **3.2** Write **Section 2B — 60-Minute Full Technical Demo** (target: Reliability Engineers, Planners, Consultants):

  | Minute | Page | Depth |
  |--------|------|-------|
  | 0–5 | P18 Wizard | All 5 steps, generate plan, seed deliverables |
  | 5–15 | P1 + P2 | Hierarchy decomposition (6 levels), criticality matrix, human gate |
  | 15–25 | P3 + P16 FMECA | Failure modes with 72-combo validation, RPN scores |
  | 25–35 | P4 + P10 | Strategy (RCM decision tree), Planner Assistant (72-char SAP text) |
  | 35–42 | P12 | Scheduling + Crew Assignment (5-dimension competency optimizer) |
  | 42–50 | P22 + P6 | Execution checklists, gate review, SAP export package |
  | 50–57 | P13 + P5 | Reliability analysis (Weibull, shutdown), Analytics |
  | 57–60 | P24 Financial | ROI calculator, budget tracking, avoided cost |

### Phase 4: Talking Points + FAQs

- [ ] **4.1** Write **Section 3 — Page-by-Page Talking Points** for all 23 pages, organized by milestone:

  **M0 — Field Capture (P8, P9):**
  - P8: "Voice or photo input — technician speaks an anomaly, AI transcribes and structures it"
  - P9: "Work requests queue — planner reviews, assigns priority, converts to work order"

  **M1 — Hierarchy + Criticality (P1, P2):**
  - P1: "6-level hierarchy: Plant > Area > System > Subsystem > Equipment > Component (ISO 14224)"
  - P1: "Functional Location format matches SAP PM — no translation layer needed"
  - P2: "Criticality = Severity × Frequency × Detectability × Production Impact"
  - P2: "Risk class A (critical) → full RCM; B (semi-critical) → targeted PM; C (non-critical) → RTF"
  - P2: "AI does the math, engineer reviews the assumptions. Human always approves."

  **M2 — FMECA + RCM (P3, P4, P16):**
  - P3: "72 validated Failure Mode combinations (Mechanism + Cause). AI can't invent arbitrary codes — it picks from the MASTER table."
  - P4: "RCM decision tree: Is it safety-critical? Hidden failure? Does PM prevent it? → selects CBM/TBM/RTF/FFI"
  - P16: "FMECA worksheet export — matches the template the OCP reliability team already knows"

  **M3 — Work Planning (P10, P11, P12, P22):**
  - P10: "SAP short text limit is 72 characters — AI auto-truncates and validates"
  - P11: "Backlog prioritization: risk score × urgency × resource availability"
  - P12: "Crew Assignment: 5-dimension competency score (specialty, certification, equipment expertise, experience, availability)"
  - P22: "Execution checklists: predecessor-locked steps — technician can't skip step 3 without completing step 2"

  **M4 — SAP Export (P6):**
  - P6: "SAP PM upload package: Maintenance Items + Task Lists + Component Lists"
  - P6: "Human reviews the DRAFT — 4 fields flagged REQUIRES_REVIEW if AI confidence < 0.7"
  - P6: "One-click export to `.xlsx` → upload directly to SAP transaction IE01/IA05"

  **Cross-Cutting (P14, P23, P24, P20):**
  - P14: "Executive dashboard: role-filtered KPIs. Manager sees cost + OEE. Engineer sees MTBF + FMECA coverage."
  - P23: "Troubleshooting: 214 symptom catalog from 72 FM MASTER cards. Jaccard keyword matching + min-cost test ordering."
  - P24: "Financial: NPV, payback period, BCR, avoided downtime cost — numbers for the CFO conversation."
  - P20: "Equipment manual chat: ask questions about SAG Mill in French, English, or Arabic. Claude reads the manual."

- [ ] **4.2** Write **Section 4 — Key Concepts Reference** (1-paragraph each):
  - R8 Maintenance Strategy Methodology
  - 4-Milestone Gate Workflow (M1→M4)
  - 72-Combo MASTER Table
  - SAP PM functional location structure
  - SWMR (Single Writer Multiple Reader) principle
  - Confidence scoring (< 0.7 = REQUIRES_REVIEW)

- [ ] **4.3** Write **Section 5 — Known Limitations & Honest Answers**:
  - "The demo uses pre-seeded synthetic data (OCP-JFC1). Real OCP data import is production scope."
  - "Live agent execution (M1→M4 via API) is CLI-only today. The workflow API endpoint is on the roadmap (G-17)."
  - "SAP connection is mock — no live RFC/BAPI. Export produces `.xlsx` for manual upload."
  - "Voice capture (G-08) and offline mode (GAP-W03) are future phases."
  - "Database is SQLite (prototype). PostgreSQL migration is Phase C."

- [ ] **4.4** Write **Section 6 — FAQ** (minimum 10 Q&As):
  - Q: Can AI replace the reliability engineer? → A: No. The engineer defines the context and approves every gate.
  - Q: How long does M1→M4 take for one equipment? → A: With AI assistance, 2–4 hours vs. 2–3 days manually.
  - Q: Is OCP data secure? → A: All data stays in the client's infrastructure (on-prem). No data sent to Anthropic except the prompts (no raw equipment data in prompts by default).
  - Q: What about SAP integration? → A: Phase 2 adds RFC/BAPI read/write. Today: structured `.xlsx` export.
  - Q: Does it work in Arabic? → A: Yes — quadrilingual (French, English, Arabic, Spanish). All UI strings are translated.
  - Q: Can multiple teams work simultaneously? → A: Current prototype is single-user. Multi-tenant is Phase C.
  - Q: What AI model powers it? → A: Claude 3.5 Sonnet (orchestrator, planner) + Claude 3 Opus (reliability analysis) + Claude 3 Haiku (spare parts — fast, cheap).
  - Q: How does it handle equipment I don't have in the library? → A: Resolver uses fuzzy matching + operator confirmation.
  - Q: What if the 72-combo rule doesn't fit? → A: Reliability engineer can flag for MASTER table extension. Process defined in gemini.md.
  - Q: How much does it cost to run? → A: Estimate: ~$0.50–$2.00 per equipment M1→M4 (Claude API tokens). Full plant (500 items): ~$500–$1000.

- [ ] **4.5** Write **Section 7 — Appendix: CLI Agent Execution**:
  ```bash
  # Set environment
  export ANTHROPIC_API_KEY=sk-ant-...

  # Run full M1→M4 for SAG Mill at JFC plant
  python -m agents.run "SAG Mill 001" --plant OCP-JFC

  # Expected output: 4 milestone gates, each requiring human approval
  # Expected time: 10–30 min depending on equipment complexity
  # Logs saved to: 2-state/session-*.json
  ```
  - Note: This is for advanced technical demos only. G-01 tracks live API testing.

---

## Session B: Wizard Polish (T-18)

**Deliverable:** Updated `streamlit_app/pages/18_wizard.py` + i18n files
**Goal:** Page 18 matches the visual quality of Pages 14, 22, 23 — professional, consistent, client-ready.

**Current state analysis:**
- Missing `apply_style()` call (all other pages have it)
- Missing `feedback_widget()` at bottom
- All labels are hardcoded English strings (no `t()` calls on steps, headers, or buttons)
- Progress bar uses `col.success/info/markdown` — inconsistent styling
- No "Demo Mode" quick-fill button
- Title "Consultant Wizard" could be more client-facing

### Phase 5: i18n Keys

- [ ] **5.1** Add wizard section to `streamlit_app/i18n/en.json`:
  ```json
  "wizard": {
    "title": "Project Wizard",
    "caption": "Interactive project setup and execution plan generator",
    "demo_mode_btn": "Load OCP Demo Data",
    "demo_mode_info": "Pre-filled with OCP Jerada phosphate plant configuration.",
    "steps": {
      "setup": "Project Setup",
      "starting_point": "Starting Point",
      "scope": "Scope Refinement",
      "plan": "Plan Generation",
      "launch": "Launch"
    },
    "step_1": { "heading": "Step 1 — Project Setup", "doc_validation": "Document Validation" },
    "step_2": { "heading": "Step 2 — Starting Point Assessment", "result": "Assessment Result" },
    "step_3": { "heading": "Step 3 — Scope Refinement", "batching": "Batching Strategy", "areas": "Areas in Scope" },
    "step_4": { "heading": "Step 4 — Execution Plan", "regen": "Regenerate Plan" },
    "step_5": { "heading": "Step 5 — Launch Confirmation", "effort": "Effort Estimation", "activate": "Activate Plan", "seed_deliverables": "Seed Deliverables" },
    "nav": { "back": "Back", "next": "Next", "launch_btn": "Launch Execution Plan", "seed_btn": "Seed Deliverables" }
  }
  ```
- [ ] **5.2** Add same keys (translated) to `streamlit_app/i18n/es.json`
- [ ] **5.3** Add same keys (translated) to `streamlit_app/i18n/fr.json`
- [ ] **5.4** Add same keys (translated) to `streamlit_app/i18n/ar.json`

### Phase 6: Page 18 Code Changes

- [ ] **6.1** Add `apply_style()` import and call after `page_init()`:
  ```python
  from streamlit_app.components.styles import apply_style
  apply_style()
  ```
  (wrap in `try/except` like other safe imports at top of file)

- [ ] **6.2** Replace hardcoded title + caption:
  ```python
  # Before:
  st.title("Consultant Wizard")
  st.caption("Interactive project setup and execution plan generator")
  # After:
  st.title(t("wizard.title"))
  st.caption(t("wizard.caption"))
  ```

- [ ] **6.3** Replace hardcoded `STEPS` list:
  ```python
  # Before:
  STEPS = ["Project Setup", "Starting Point", "Scope Refinement", "Plan Generation", "Launch"]
  # After:
  STEPS = [
      t("wizard.steps.setup"),
      t("wizard.steps.starting_point"),
      t("wizard.steps.scope"),
      t("wizard.steps.plan"),
      t("wizard.steps.launch"),
  ]
  ```

- [ ] **6.4** Replace hardcoded `st.header()` calls in each step function (5 replacements):
  - `_step_1`: `st.header(t("wizard.step_1.heading"))`
  - `_step_2`: `st.header(t("wizard.step_2.heading"))`
  - `_step_3`: `st.header(t("wizard.step_3.heading"))`
  - `_step_4`: `st.header(t("wizard.step_4.heading"))`
  - `_step_5`: `st.header(t("wizard.step_5.heading"))`

- [ ] **6.5** Add "Demo Mode" quick-fill button in `_step_1()`, just before the client/project inputs:
  ```python
  if st.button(t("wizard.demo_mode_btn"), type="secondary"):
      st.session_state._demo_client = "ocp"
      st.session_state._demo_project = "jfc-maintenance-strategy"
      st.info(t("wizard.demo_mode_info"))
  client_slug = _sanitize(
      c1.text_input("Client slug",
                    value=st.session_state.get("_demo_client", "ocp")).lower()
  )
  project_slug = _sanitize(
      c2.text_input("Project slug",
                    value=st.session_state.get("_demo_project", "jfc-maintenance-strategy")).lower()
  )
  ```

- [ ] **6.6** Replace hardcoded nav button labels with `t()` calls:
  - All `st.button("Back")` → `st.button(t("wizard.nav.back"))`
  - All `st.button("Next: ...")` → use appropriate `t("wizard.nav.next")` + step hint
  - `st.button("Launch Execution Plan", ...)` → `st.button(t("wizard.nav.launch_btn"), ...)`
  - `st.button("Seed Deliverables", ...)` → `st.button(t("wizard.nav.seed_btn"), ...)`

- [ ] **6.7** Add `feedback_widget` at the very end (after the step router):
  ```python
  # At module level, after _STEP_FNS[st.session_state.wiz_step]()
  try:
      from streamlit_app.components.feedback import feedback_widget
      feedback_widget("wizard")
  except Exception:
      pass
  ```

- [ ] **6.8** Replace `"Regenerate Plan"` button in `_step_4()`:
  ```python
  if rc.button(t("wizard.step_4.regen")):
  ```

### Phase 7: MASTER_PLAN.md Update

- [ ] **7.1** In `MASTER_PLAN.md` Part 3.1, mark G-03 as closed:
  ```
  - [x] **G-03** ~~No guided demo flow~~ — CLOSED (Session XX). `docs/DEMO_GUIDE.md` created (30-min + 60-min demo tracks, 23-page talking points, 10 FAQs, CLI appendix). Page 18 wizard polished: `apply_style()`, i18n keys (4 languages, ~20 new keys), Demo Mode quick-fill button, `feedback_widget`. `(1 session)`
  ```

- [ ] **7.2** In Part 4 Phase B, mark B-5 and B-6 as done:
  ```
  - [x] **B-5** Create guided demo script `(G-03)` → DONE: `docs/DEMO_GUIDE.md`
  - [x] **B-6** Polish wizard page for client-facing use `(G-03)` → DONE: Page 18 i18n + style
  ```

- [ ] **7.3** In Part 5 Task Backlog, mark T-17 and T-18 as done (strikethrough format matching other completed tasks)

- [ ] **7.4** Update the build history table with a new row for this session

- [ ] **7.5** Add changelog entry

---

## Critical Files Reference

| File | Role | Change |
|------|------|--------|
| `docs/DEMO_GUIDE.md` | NEW — demo walkthrough document | Create |
| `docs/G-03_EXECUTION.md` | NEW — this execution tracker | Create (copy plan) |
| `streamlit_app/pages/18_wizard.py` | Existing wizard — polish | Edit |
| `streamlit_app/i18n/en.json` | English i18n | Add ~20 keys under "wizard" |
| `streamlit_app/i18n/es.json` | Spanish i18n | Add ~20 keys under "wizard" |
| `streamlit_app/i18n/fr.json` | French i18n | Add ~20 keys under "wizard" |
| `streamlit_app/i18n/ar.json` | Arabic i18n | Add ~20 keys under "wizard" |
| `MASTER_PLAN.md` | Living plan | Mark G-03 closed, T-17/T-18 done |

**Files to READ for context (do not modify):**
- `streamlit_app/components/styles.py` — check exact import name for `apply_style()`
- `streamlit_app/components/feedback.py` — check exact import name for `feedback_widget()`
- `streamlit_app/pages/22_execution_checklists.py` — reference for style + i18n pattern
- `streamlit_app/i18n/__init__.py` — understand `t()` key resolution (dot-separated)

---

## Verification Checklist

### Demo Guide Verification
- [ ] `docs/DEMO_GUIDE.md` exists and has all 7 sections
- [ ] 30-minute scenario table covers: Wizard, Exec Dashboard, Hierarchy, Criticality, SAP Review, Troubleshooting
- [ ] 60-minute scenario table covers all 23 pages or calls them out explicitly
- [ ] 23 page talking points are written (one entry per page)
- [ ] FAQ section has ≥ 10 Q&As
- [ ] Known limitations section is honest about G-01, G-17, G-08

### Wizard Polish Verification
- [ ] Open Page 18 — title shows "Project Wizard" (not "Consultant Wizard")
- [ ] Progress bar steps show translated labels (switch language in sidebar — verify French labels appear)
- [ ] "Load OCP Demo Data" button appears at top of Step 1
- [ ] Clicking demo button pre-fills client slug = "ocp", project slug = "jfc-maintenance-strategy"
- [ ] Navigate through all 5 steps — no hardcoded English strings remain in headings
- [ ] Feedback widget appears at bottom of page
- [ ] All navigation buttons ("Back", "Next") work correctly
- [ ] `pytest tests/test_navigation.py -v` — all pass (page 18 still in registry)
- [ ] Run full test suite: `pytest --tb=short -q` — no regressions

### MASTER_PLAN.md Verification
- [ ] G-03 has `[x]` checkbox
- [ ] T-17 and T-18 are struck through in the task backlog
- [ ] Changelog has new entry for this session

---

## Execution Order (within a single session)

```
Phase 1 (20 min)  → Document structure + setup section
Phase 2 (20 min)  → 30-min + 60-min demo scenarios
Phase 3 (30 min)  → 23-page talking points + key concepts
Phase 4 (20 min)  → FAQ + known limitations + CLI appendix
Phase 5 (15 min)  → i18n keys (4 languages)
Phase 6 (25 min)  → Page 18 code changes (7 edits)
Phase 7 (10 min)  → MASTER_PLAN.md update
Verification      (10 min) → Run tests, spot-check UI
─────────────────────────────────────────────────────
Total:            ~2.5 hours (1 focused session)
```
