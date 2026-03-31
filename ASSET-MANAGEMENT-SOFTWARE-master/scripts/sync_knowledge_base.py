#!/usr/bin/env python3
"""
Knowledge Base Sync Checker

Compares shared documents between AMS, OR SYSTEM, and Archive to detect
out-of-sync copies. Does NOT automatically overwrite — reports differences
for manual review.

Usage:
    python scripts/sync_knowledge_base.py [--fix]

    --fix   Copy canonical source to all destinations (requires confirmation)
"""

import argparse
import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path

# ── Base paths ──────────────────────────────────────────────────────────────
AMS_ROOT = Path(__file__).resolve().parent.parent
AMS_KB = AMS_ROOT / "skills" / "00-knowledge-base"
AMS_TEMPLATES = AMS_ROOT / "templates"

# OR SYSTEM and Archive paths (adjust if mounted differently)
OR_ROOT = Path("G:/Unidades compartidas/VSC Team/VSC CHILE/03. PRODUCT/OR SYSTEM/methodology")
ARCHIVE_ROOT = Path(
    "G:/Unidades compartidas/VSC Team/VSC CHILE/03. PRODUCT/"
    "ASSET-MANAGEMENT-SOFTWARE-ARCHIVE-methodology"
)


@dataclass
class SharedDoc:
    """A document that exists in multiple locations."""
    name: str
    canonical: Path
    copies: list[Path]
    category: str


# ── Shared document registry ───────────────────────────────────────────────
# Each entry: (name, canonical_path, [copy_paths], category)
SHARED_DOCS: list[SharedDoc] = [
    # ── Failure Mode Table ──
    SharedDoc(
        "Failure Modes Table (Excel)",
        OR_ROOT / "Failure Modes (Mechanism + Cause).xlsx",
        [ARCHIVE_ROOT / "Failure Modes (Mechanism + Cause).xlsx"],
        "FM Table",
    ),
    # ── AMS → OR: Standards ──
    SharedDoc(
        "ISO 55002 Analysis",
        AMS_KB / "standards" / "iso-55002-2018-standard.md",
        [OR_ROOT / "asset-management-iso-55000" / "iso-55002-2018-analysis-ams.md"],
        "Standards",
    ),
    SharedDoc(
        "PAS 55 Analysis",
        AMS_KB / "standards" / "pas-55-2008-standard.md",
        [OR_ROOT / "asset-management-iso-55000" / "pas-55-2008-analysis-ams.md"],
        "Standards",
    ),
    SharedDoc(
        "ISO 14224 Taxonomy",
        AMS_KB / "standards" / "iso-14224-plant-equipment-taxonomy.md",
        [OR_ROOT / "asset-management-iso-55000" / "iso-14224-plant-equipment-taxonomy-ams.md"],
        "Standards",
    ),
    SharedDoc(
        "ISO 55002 Compliance Mapping",
        AMS_KB / "strategic" / "ref-09-iso-55002-compliance-mapping.md",
        [OR_ROOT / "asset-management-iso-55000" / "iso-55002-compliance-mapping-ams.md"],
        "Standards",
    ),
    # ── AMS → OR: RCM ──
    SharedDoc(
        "Maintenance Strategy Methodology",
        AMS_KB / "methodologies" / "ref-01-maintenance-strategy-methodology.md",
        [OR_ROOT / "maintenance-procedures" / "rcm" / "maintenance-strategy-methodology-ams.md"],
        "RCM",
    ),
    SharedDoc(
        "RCM Methodology Full",
        AMS_KB / "methodologies" / "rcm-methodology-full.md",
        [OR_ROOT / "maintenance-procedures" / "rcm" / "rcm-methodology-full-ams.md"],
        "RCM",
    ),
    SharedDoc(
        "RCM2 Moubray",
        AMS_KB / "methodologies" / "rcm2-moubray-methodology.md",
        [OR_ROOT / "maintenance-procedures" / "rcm" / "rcm2-moubray-methodology-ams.md"],
        "RCM",
    ),
    # ── AMS → OR: R8 Tactics ──
    SharedDoc(
        "Maintenance Tactics Guideline",
        AMS_KB / "methodologies" / "maintenance-tactics-guideline.md",
        [OR_ROOT / "maintenance-procedures" / "r8-methodology" / "maintenance-tactics-guideline-ams.md"],
        "R8 Tactics",
    ),
    SharedDoc(
        "Maintenance Tactics Process Map",
        AMS_KB / "methodologies" / "maintenance-tactics-process-map.md",
        [OR_ROOT / "maintenance-procedures" / "r8-methodology" / "maintenance-tactics-process-map-ams.md"],
        "R8 Tactics",
    ),
    # ── AMS → OR: Work Instructions ──
    SharedDoc(
        "Work Instruction Templates",
        AMS_KB / "methodologies" / "ref-07-work-instruction-templates.md",
        [OR_ROOT / "maintenance-procedures" / "work-instructions" / "work-instruction-templates-ams.md"],
        "Work Instructions",
    ),
    SharedDoc(
        "Work Instruction Examples",
        AMS_KB / "methodologies" / "work-instruction-examples-consolidated.md",
        [OR_ROOT / "maintenance-procedures" / "work-instructions" / "work-instruction-examples-consolidated-ams.md"],
        "Work Instructions",
    ),
    # ── AMS → OR: SAP Integration ──
    SharedDoc(
        "SAP PM Integration",
        AMS_KB / "integration" / "ref-03-sap-pm-integration.md",
        [OR_ROOT / "maintenance-readiness" / "sap-integration" / "sap-pm-integration-ams.md"],
        "SAP Integration",
    ),
    SharedDoc(
        "R8 Integration Master Plan",
        AMS_KB / "integration" / "r8-integration-master-plan.md",
        [OR_ROOT / "maintenance-readiness" / "sap-integration" / "r8-integration-master-plan-ams.md"],
        "SAP Integration",
    ),
    # ── AMS → OR: Libraries ──
    SharedDoc(
        "Component Library",
        AMS_KB / "data-models" / "component-library.md",
        [OR_ROOT / "standards" / "component-library-ams.md"],
        "Libraries",
    ),
    SharedDoc(
        "Equipment Library",
        AMS_KB / "data-models" / "equipment-library.md",
        [OR_ROOT / "standards" / "equipment-library-ams.md"],
        "Libraries",
    ),
    # ── AMS → OR: Quality ──
    SharedDoc(
        "Quality Validation Rules",
        AMS_KB / "quality" / "ref-04-quality-validation-rules.md",
        [OR_ROOT / "references-md" / "quality-validation-rules-ams.md"],
        "Quality",
    ),
    # ── OR → AMS ──
    SharedDoc(
        "Client Intent Interview Guide",
        OR_ROOT / "or-playbook-and-procedures" / "client-intent-interview-guide.md",
        [AMS_KB / "client" / "client-intent-interview-guide-or.md"],
        "Client",
    ),
    SharedDoc(
        "OR Assessment Tools",
        OR_ROOT / "references-md" / "or-assessment-tools.md",
        [AMS_KB / "strategic" / "or-assessment-tools-or.md"],
        "Strategic",
    ),
    SharedDoc(
        "Process Safety Integration",
        OR_ROOT / "references-md" / "process-safety-design-integration.md",
        [AMS_KB / "process-safety" / "process-safety-design-integration-or.md"],
        "Process Safety",
    ),
    SharedDoc(
        "HSE Critical Risks Standards",
        OR_ROOT / "references-md" / "hse-critical-risks-standards.md",
        [AMS_KB / "hse-risks" / "hse-critical-risks-standards-or.md"],
        "HSE",
    ),
    SharedDoc(
        "Conflict Resolution Protocol",
        OR_ROOT / "or-playbook-and-procedures" / "conflict-resolution-protocol.md",
        [AMS_KB / "architecture" / "conflict-resolution-protocol-or.md"],
        "Architecture",
    ),
    # ── SHARED_DOCS_MANIFEST.md ──
    SharedDoc(
        "Shared Docs Manifest",
        AMS_ROOT / "SHARED_DOCS_MANIFEST.md",
        [OR_ROOT / "SHARED_DOCS_MANIFEST.md"],
        "Manifest",
    ),
]


def file_hash(path: Path) -> str | None:
    """Return SHA-256 hex digest of file, or None if not found."""
    if not path.exists():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def check_sync() -> list[dict]:
    """Check all shared docs for sync status. Returns list of issues."""
    issues = []
    for doc in SHARED_DOCS:
        canonical_hash = file_hash(doc.canonical)
        if canonical_hash is None:
            issues.append({
                "doc": doc.name,
                "category": doc.category,
                "issue": "MISSING_CANONICAL",
                "path": str(doc.canonical),
            })
            continue

        for copy_path in doc.copies:
            copy_hash = file_hash(copy_path)
            if copy_hash is None:
                issues.append({
                    "doc": doc.name,
                    "category": doc.category,
                    "issue": "MISSING_COPY",
                    "path": str(copy_path),
                })
            elif copy_hash != canonical_hash:
                issues.append({
                    "doc": doc.name,
                    "category": doc.category,
                    "issue": "OUT_OF_SYNC",
                    "canonical": str(doc.canonical),
                    "copy": str(copy_path),
                })
    return issues


def fix_sync(issues: list[dict]) -> None:
    """Copy canonical source to out-of-sync or missing destinations."""
    import shutil

    fixable = [i for i in issues if i["issue"] in ("OUT_OF_SYNC", "MISSING_COPY")]
    if not fixable:
        print("Nothing to fix.")
        return

    print(f"\nWill fix {len(fixable)} issue(s):")
    for i in fixable:
        dest = i.get("copy") or i.get("path")
        print(f"  {i['doc']}: -> {dest}")

    confirm = input("\nProceed? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return

    for i in fixable:
        doc = next(d for d in SHARED_DOCS if d.name == i["doc"])
        dest = Path(i.get("copy") or i.get("path"))
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(doc.canonical, dest)
        print(f"  Synced: {doc.name} -> {dest}")


def main():
    parser = argparse.ArgumentParser(description="Knowledge Base Sync Checker")
    parser.add_argument("--fix", action="store_true", help="Fix out-of-sync copies")
    args = parser.parse_args()

    print("=" * 60)
    print("Knowledge Base Sync Check")
    print("=" * 60)

    # Check paths
    missing_roots = []
    if not OR_ROOT.exists():
        missing_roots.append(f"OR SYSTEM: {OR_ROOT}")
    if not ARCHIVE_ROOT.exists():
        missing_roots.append(f"Archive: {ARCHIVE_ROOT}")
    if missing_roots:
        print(f"\nWARNING: Cannot reach shared drives:")
        for r in missing_roots:
            print(f"  - {r}")
        print("Sync check will skip documents on unreachable paths.\n")

    issues = check_sync()

    if not issues:
        print(f"\nAll {len(SHARED_DOCS)} shared documents are in sync.")
        return 0

    print(f"\nFound {len(issues)} issue(s):\n")
    for i in issues:
        icon = {"MISSING_CANONICAL": "X", "MISSING_COPY": "!", "OUT_OF_SYNC": "~"}[i["issue"]]
        print(f"  [{icon}] {i['doc']} ({i['category']}): {i['issue']}")
        if "path" in i:
            print(f"      Path: {i['path']}")
        if "copy" in i:
            print(f"      Canonical: {i['canonical']}")
            print(f"      Copy:      {i['copy']}")

    if args.fix:
        fix_sync(issues)

    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
