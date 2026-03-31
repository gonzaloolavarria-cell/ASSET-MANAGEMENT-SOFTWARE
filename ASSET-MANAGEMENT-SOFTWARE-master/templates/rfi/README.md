# RFI (Request for Information) Templates

## Purpose

The RFI questionnaire collects client information before a maintenance strategy engagement. It feeds into `project.yaml` and seeds the project memory.

## Workflow

1. **Generate template**: `python scripts/generate_rfi_template.py`
2. **Send to client**: Share `00_rfi_questionnaire.xlsx` for the client to complete
3. **Receive completed file**: Client fills in 8 sheets with their facility data
4. **Process**: `python scripts/process_ams_rfi.py filled-rfi.xlsx --client <slug> --project <slug>`
5. **Review outputs**: Check generated `project.yaml`, availability report, and follow-up items

## Generated Outputs

| File | Location | Description |
|------|----------|-------------|
| `project.yaml` | Project root | Project configuration from RFI data |
| `data-availability-report.md` | `1-output/rfi/` | Data availability matrix |
| `scope-assessment.md` | `1-output/rfi/` | Effort estimation and starting milestone |
| `global-requirements.md` | `3-memory/` | Naming, language, and standards seed |
| `rfi-followup.md` | `1-output/rfi/` | Missing data items (if any) |

## Questionnaire Sheets

1. Company & Site Profile (12 fields)
2. Equipment & Hierarchy Data (11 fields)
3. Maintenance Current State (14 fields)
4. Organization & Resources (8 fields)
5. Standards & Compliance (8 fields)
6. KPI Baseline & Targets (10 fields)
7. Scope & Timeline (7 fields)
8. Data Availability Checklist (14 templates)
