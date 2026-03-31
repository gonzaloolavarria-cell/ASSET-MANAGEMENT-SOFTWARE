# Shared Documents Manifest

> **Version**: 1.0 | **Date**: 2026-03-05
> **Purpose**: Single source of truth for all documents shared between AMS, OR SYSTEM, and Archive
> **Update process**: Update this manifest whenever documents are added, removed, or synced

---

## 1. Failure Mode Table (CRITICAL)

| Attribute                  | Value                                                                                                                                                                         |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Canonical Source** | `OR SYSTEM/methodology/Failure Modes (Mechanism + Cause).xlsx`                                                                                                              |
| **AMS Copy**         | `skills/00-knowledge-base/data-models/failure-modes/MASTER.md` (markdown synthesis)                                                                                         |
| **Archive Copy**     | `ARCHIVE-methodology/Failure Modes (Mechanism + Cause).xlsx` (binary identical to OR)                                                                                       |
| **Format**           | Canonical: Excel (.xlsx) / AMS: Markdown (.md)                                                                                                                                |
| **Content**          | 18 mechanisms, 46 causes (OR) / 44 causes (AMS normalized), 72 valid combinations                                                                                             |
| **Last Sync**        | 2026-03-05                                                                                                                                                                    |
| **Sync Note**        | OR Excel uses descriptive cause names (e.g., "Excessive temperature (hot/cold)"); AMS normalizes to enum values (e.g., EXCESSIVE_TEMPERATURE). 72 combinations are identical. |

## 2. Documents Transferred: AMS → OR SYSTEM

| AMS Source                                                   | OR Destination                                                                             | Category          | Last Sync  |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------ | ----------------- | ---------- |
| `standards/iso-55002-2018-standard.md`                     | `asset-management-iso-55000/iso-55002-2018-analysis-ams.md`                              | Standards         | 2026-03-05 |
| `standards/pas-55-2008-standard.md`                        | `asset-management-iso-55000/pas-55-2008-analysis-ams.md`                                 | Standards         | 2026-03-05 |
| `standards/iso-14224-plant-equipment-taxonomy.md`          | `asset-management-iso-55000/iso-14224-plant-equipment-taxonomy-ams.md`                   | Standards         | 2026-03-05 |
| `strategic/ref-09-iso-55002-compliance-mapping.md`         | `asset-management-iso-55000/iso-55002-compliance-mapping-ams.md`                         | Standards         | 2026-03-05 |
| `methodologies/ref-01-maintenance-strategy-methodology.md` | `maintenance-procedures/rcm/maintenance-strategy-methodology-ams.md`                     | RCM               | 2026-03-05 |
| `methodologies/rcm-methodology-full.md`                    | `maintenance-procedures/rcm/rcm-methodology-full-ams.md`                                 | RCM               | 2026-03-05 |
| `methodologies/rcm2-moubray-methodology.md`                | `maintenance-procedures/rcm/rcm2-moubray-methodology-ams.md`                             | RCM               | 2026-03-05 |
| `methodologies/maintenance-tactics-guideline.md`           | `maintenance-procedures/r8-methodology/maintenance-tactics-guideline-ams.md`             | R8 Tactics        | 2026-03-05 |
| `methodologies/maintenance-tactics-process-map.md`         | `maintenance-procedures/r8-methodology/maintenance-tactics-process-map-ams.md`           | R8 Tactics        | 2026-03-05 |
| `methodologies/r8-deployment-flowcharts.md`                | `maintenance-procedures/r8-methodology/r8-deployment-flowcharts-ams.md`                  | R8 Tactics        | 2026-03-05 |
| `methodologies/r8-deployment-implementation.md`            | `maintenance-procedures/r8-methodology/r8-deployment-implementation-ams.md`              | R8 Tactics        | 2026-03-05 |
| `methodologies/r8-maintenance-optimization.md`             | `maintenance-procedures/r8-methodology/r8-maintenance-optimization-ams.md`               | R8 Tactics        | 2026-03-05 |
| `methodologies/r8-tactics-development-process.md`          | `maintenance-procedures/r8-methodology/r8-tactics-development-process-ams.md`            | R8 Tactics        | 2026-03-05 |
| `methodologies/ref-07-work-instruction-templates.md`       | `maintenance-procedures/work-instructions/work-instruction-templates-ams.md`             | Work Instructions | 2026-03-05 |
| `methodologies/work-instruction-examples-consolidated.md`  | `maintenance-procedures/work-instructions/work-instruction-examples-consolidated-ams.md` | Work Instructions | 2026-03-05 |
| `integration/ref-03-sap-pm-integration.md`                 | `maintenance-readiness/sap-integration/sap-pm-integration-ams.md`                        | SAP Integration   | 2026-03-05 |
| `integration/r8-integration-master-plan.md`                | `maintenance-readiness/sap-integration/r8-integration-master-plan-ams.md`                | SAP Integration   | 2026-03-05 |
| `integration/sap-r8-setup-guide.md`                        | `maintenance-readiness/sap-integration/sap-r8-setup-guide-ams.md`                        | SAP Integration   | 2026-03-05 |
| `integration/sap-upload-templates-reference.md`            | `maintenance-readiness/sap-integration/sap-upload-templates-reference-ams.md`            | SAP Integration   | 2026-03-05 |
| `data-models/component-library.md`                         | `standards/component-library-ams.md`                                                     | Libraries         | 2026-03-05 |
| `data-models/equipment-library.md`                         | `standards/equipment-library-ams.md`                                                     | Libraries         | 2026-03-05 |
| `quality/ref-04-quality-validation-rules.md`               | `references-md/quality-validation-rules-ams.md`                                          | Quality           | 2026-03-05 |
| `quality/mso-checklist.md`                                 | `references-md/mso-checklist-ams.md`                                                     | Quality           | 2026-03-05 |
| `quality/quality-management-flowchart.md`                  | `references-md/quality-management-flowchart-ams.md`                                      | Quality           | 2026-03-05 |
| `quality/r8-quality-analysis-guideline.md`                 | `references-md/r8-quality-analysis-guideline-ams.md`                                     | Quality           | 2026-03-05 |
| `competitive/gecamin/*.md` (58 files)                      | `or-papers-and-bibliography/gecamin/*.md`                                                | GECAMIN           | 2026-03-05 |
| `competitive/ref-10-gecamin-cross-reference.md`            | `or-papers-and-bibliography/gecamin/gecamin-cross-reference-ams.md`                      | GECAMIN           | 2026-03-05 |
| `templates/01-14_*.xlsx` (14 files)                        | `templates/asset-management/*.xlsx`                                                      | Templates         | 2026-03-05 |

## 3. Documents Transferred: OR SYSTEM → AMS

| OR Source                                                           | AMS Destination                                            | Category       | Last Sync  |
| ------------------------------------------------------------------- | ---------------------------------------------------------- | -------------- | ---------- |
| `or-playbook-and-procedures/client-intent-interview-guide.md`     | `client/client-intent-interview-guide-or.md`             | Client         | 2026-03-05 |
| `references-md/or-assessment-tools.md`                            | `strategic/or-assessment-tools-or.md`                    | Strategic      | 2026-03-05 |
| `maintenance-readiness/RAM-Failure-Model--AWB_FM_LoadSheet*.xlsx` | `gfsn/ram-failure-model-loadsheet-or.xlsx`               | GFSN           | 2026-03-05 |
| `maintenance-readiness/Spare-Part-Criticality-Analysis--*.xlsx`   | `gfsn/spare-parts-criticality-template-or.xlsx`          | GFSN           | 2026-03-05 |
| `references-md/process-safety-design-integration.md`              | `process-safety/process-safety-design-integration-or.md` | Process Safety | 2026-03-05 |
| `references-md/hse-critical-risks-standards.md`                   | `hse-risks/hse-critical-risks-standards-or.md`           | HSE            | 2026-03-05 |
| `or-playbook-and-procedures/conflict-resolution-protocol.md`      | `architecture/conflict-resolution-protocol-or.md`        | Architecture   | 2026-03-05 |

## 4. Documents from Archive → Both Systems

| Archive Source                                                  | AMS Destination                                       | OR Destination                                         | Last Sync  |
| --------------------------------------------------------------- | ----------------------------------------------------- | ------------------------------------------------------ | ---------- |
| `maintenance-strategy-structure-examples/*.xlsx` (4 files)    | `data-models/strategy-examples/`                    | `deliverable-examples/maintenance-strategy/`         | 2026-03-05 |
| `sap-upload-sheets-template-*/*.xlsx` (3 files)               | —                                                    | `templates/sap-upload/`                              | 2026-03-05 |
| `maintenance-work-instruction-template-examples/*` (16 files) | —                                                    | `maintenance-procedures/work-instructions/examples/` | 2026-03-05 |
| `Video-tutorial-uso-R8/` (11 videos + 9 diagrams)             | Indexed at `methodologies/video-tutorials-index.md` | —                                                     | 2026-03-05 |

## 5. Naming Convention

Files copied between systems are suffixed to indicate origin:

- `-ams.md` = Originated in AMS
- `-or.md` = Originated in OR SYSTEM
- No suffix = Canonical/original location

## 6. Update Process

1. **Who updates**: The team member who modifies the canonical source
2. **When**: After any change to a shared document
3. **How**:
   - Update the canonical source first
   - Run `scripts/sync_knowledge_base.py` to detect out-of-sync copies
   - Copy updated file to all listed destinations
   - Update `Last Sync` date in this manifest
4. **Verification**: Run sync script to confirm all copies match canonical source

## 7. Phase 5 — Agent & Skills Alignment Artifacts (2026-03-05)

### Skills Transferred: AMS → OR SYSTEM

| AMS Skill                  | OR Destination                                                      | Category    |
| -------------------------- | ------------------------------------------------------------------- | ----------- |
| `validate-failure-modes` | `skills/asset-management-skills/validate-failure-modes/CLAUDE.md` | FMECA       |
| `run-rcm-decision-tree`  | `skills/asset-management-skills/run-rcm-decision-tree/CLAUDE.md`  | RCM (DEPRECATED in AMS — merged into `perform-fmeca` Stage 4) |
| `analyze-jackknife`      | `skills/asset-management-skills/analyze-jackknife/CLAUDE.md`      | Reliability |
| `analyze-pareto`         | `skills/asset-management-skills/analyze-pareto/CLAUDE.md`         | Reliability |
| `calculate-health-score` | `skills/asset-management-skills/calculate-health-score/CLAUDE.md` | KPIs        |

### Skills Transferred: OR SYSTEM → AMS

| OR Skill                       | AMS Destination                                                                             | Category    |
| ------------------------------ | ------------------------------------------------------------------------------------------- | ----------- |
| `assess-am-maturity`         | `skills/02-maintenance-strategy-development/assess-am-maturity/CLAUDE.md`                 | Strategy    |
| `model-ram-simulation`       | `skills/03-reliability-engineering-and-defect-elimination/model-ram-simulation/CLAUDE.md` | Reliability |
| `benchmark-maintenance-kpis` | `skills/06-orchestation/benchmark-maintenance-kpis/CLAUDE.md`                             | KPIs        |
| `develop-samp`               | `skills/02-maintenance-strategy-development/develop-samp/CLAUDE.md`                       | Strategy    |

### Shared Infrastructure Created

| Artifact                      | Location                                                                      | Purpose                                          |
| ----------------------------- | ----------------------------------------------------------------------------- | ------------------------------------------------ |
| `vsc-shared-engines`        | `g:\...\03. PRODUCT\vsc-shared-engines\`                                    | Shared engine package (re-exports 8 AMS engines) |
| `SKILL_ALIGNMENT_MATRIX.md` | `skills/`                                                                   | Maps 39 AMS skills ↔ 28 OR AG-003 skills (+ 2 deprecated) |
| `@json_tool` decorator      | `agents/tool_wrappers/registry.py`                                          | Reduces boilerplate in tool wrappers             |
| 4 OR tool wrappers            | `OR SYSTEM/agents/tool_wrappers/{criticality,fmeca,rcm,hierarchy}_tools.py` | Engine-backed tools for AG-003                   |
