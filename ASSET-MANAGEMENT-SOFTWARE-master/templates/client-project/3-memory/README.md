# Client Memory — Project-Level Knowledge Store

This directory stores **client-specific requirements, patterns, and learnings** that agents use to personalize their outputs. Memory is injected into agent system prompts before execution.

## Directory Structure

```
3-memory/
  global-requirements.md        # Cross-stage requirements (naming, language, standards)
  maintenance-strategy/
    requirements.md             # Hierarchy, criticality, FMECA, RCM requirements
    patterns.md                 # Confirmed patterns (PAT-XXX)
  work-identification/
    requirements.md             # Capture, WO classification requirements
    patterns.md
  work-planning/
    requirements.md             # SAP conventions, WP grouping, resource constraints
    patterns.md
  reliability-engineering/
    requirements.md             # RCA, Weibull, Pareto requirements
    patterns.md
  cost-analysis/
    requirements.md             # LCC, cost-risk optimization requirements
    patterns.md
  deviations/                   # DEV-XXX files (auto-generated from gate feedback)
  meetings/                     # Meeting notes ({date}_meeting.md)
```

## How Memory Works

1. **Seeding**: `process_ams_rfi.py` populates `global-requirements.md` and stage-specific `requirements.md` from the RFI questionnaire.
2. **Loading**: Before each milestone, agents load `global-requirements.md` + the relevant stage files.
3. **Learning**: After gate reviews, the system extracts patterns (approve) or deviations (modify) and saves them here.
4. **Priority**: Requirements in memory **OVERRIDE** methodology defaults.

## For Consultants

- Edit `global-requirements.md` to add client constraints discovered in interviews.
- Add patterns to `{stage}/patterns.md` when a working approach is confirmed.
- Do NOT edit files in `deviations/` — these are system-managed.
- Meeting notes in `meetings/` are auto-generated from transcripts.

## Milestone-to-Stage Mapping

| Milestone | Stages Loaded |
|-----------|--------------|
| M1 | maintenance-strategy |
| M2 | maintenance-strategy, reliability-engineering |
| M3 | work-planning, cost-analysis |
| M4 | work-planning |
