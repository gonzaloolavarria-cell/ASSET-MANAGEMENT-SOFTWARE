"""AMS Consultant Wizard — CLI version for Claude Code console.

Run: python scripts/wizard_cli.py [--client CLIENT] [--project PROJECT]

Guides the consultant through the same 5-step flow as the Streamlit wizard,
but via interactive prompts on the console. Produces the same
``2-state/execution-plan.yaml`` output.

This module can also be imported and called programmatically:
    from scripts.wizard_cli import run_wizard
    plan = run_wizard(client_slug="ocp", project_slug="jfc-maintenance-strategy")
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents._shared.paths import (
    get_input_dir,
    get_state_dir,
    load_project_config,
    INPUT_SUBDIRS,
    validate_input_structure,
    scaffold_project,
)
from agents.orchestration.execution_plan import (
    ExecutionPlan,
    ExecutionPlanItem,
    ExecutionPlanStage,
    PlanStatus,
    StrategyApproach,
)
from tools.engines.deliverable_tracking_engine import (
    DEFAULT_HOURS,
    STAGE_TO_CATEGORY,
    DeliverableTrackingEngine,
)
from tools.models.schemas import DeliverableCategory

# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------

_YAML_INJECTION = re.compile(r"[{}\[\]!%*&|>]")


def _sanitize(value: str, max_len: int = 200) -> str:
    value = value[:max_len].strip()
    return _YAML_INJECTION.sub("", value)


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    return _sanitize(raw) if raw else default


def _ask_yn(prompt: str, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    raw = input(f"{prompt} ({hint}): ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes", "si", "oui")


def _ask_choice(prompt: str, options: list[str], default: int = 0) -> str:
    print(f"\n{prompt}")
    for i, opt in enumerate(options):
        marker = " *" if i == default else ""
        print(f"  {i + 1}) {opt}{marker}")
    raw = input(f"Choice [1-{len(options)}, default={default + 1}]: ").strip()
    if not raw:
        return options[default]
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(options):
            return options[idx]
    except ValueError:
        pass
    return options[default]


def _heading(text: str) -> None:
    width = max(60, len(text) + 4)
    print()
    print("=" * width)
    print(f"  {text}")
    print("=" * width)
    print()


# ═══════════════════════════════════════════════════════════════════════════
# STEP 1 — Project Setup
# ═══════════════════════════════════════════════════════════════════════════

def step_1_project_setup(
    client_slug: str = "",
    project_slug: str = "",
) -> dict[str, Any]:
    _heading("STEP 1: Project Setup")

    if not client_slug:
        client_slug = _ask("Client slug (lowercase)", "ocp").lower()
    if not project_slug:
        project_slug = _ask("Project slug (lowercase)", "jfc-maintenance-strategy").lower()

    config = load_project_config(client_slug, project_slug)

    if config:
        print("\n[OK] project.yaml loaded successfully")
        client = config.get("client", {})
        scope = config.get("scope", {})
        maint = config.get("maintenance_context", {})
        print(f"  Client:   {client.get('name', client_slug)}")
        print(f"  Plant:    {scope.get('plant', {}).get('name', '—')}")
        print(f"  Scope:    {scope.get('type', '—')}")
        print(f"  Industry: {client.get('industry', '—')}")
        print(f"  Maturity: {maint.get('strategy_maturity', '—')}")
        print(f"  CMMS:     {maint.get('cmms', '—')}")
    else:
        print("\n[WARN] project.yaml not found — continuing in manual mode")

    # Validate documents
    print("\n--- Document Validation ---")
    try:
        input_dir = get_input_dir(client_slug, project_slug)
        missing = validate_input_structure(client_slug, project_slug)
        found = [d for d in INPUT_SUBDIRS if d not in missing]
        for d in found:
            subdir = input_dir / d
            count = sum(1 for _ in subdir.iterdir()) if subdir.is_dir() else 0
            icon = "[OK]" if count > 0 else "[!!]"
            print(f"  {icon} {d}/ — {count} file(s)")
        if missing:
            print(f"\n  Missing folders: {', '.join(missing)}")
    except Exception:
        print("  Client project folder not found (will be created at launch)")

    return {
        "client_slug": client_slug,
        "project_slug": project_slug,
        "config": config,
    }


# ═══════════════════════════════════════════════════════════════════════════
# STEP 2 — Starting Point Assessment
# ═══════════════════════════════════════════════════════════════════════════

def step_2_assessment(project: dict[str, Any]) -> dict[str, Any]:
    _heading("STEP 2: Starting Point Assessment")

    config = project.get("config") or {}
    maint = config.get("maintenance_context", {})
    existing = maint.get("existing_data", {})

    has_hierarchy = _ask_yn(
        "Does the client have an existing equipment hierarchy?",
        default=bool(existing.get("equipment_list")),
    )

    has_criticality = _ask_yn(
        "Has a criticality assessment been done before?",
        default=bool(maint.get("prior_criticality_assessment")),
    )

    has_wo_history = _ask_yn(
        "Is work order / failure history available?",
        default=bool(existing.get("failure_history")),
    )

    has_pm_plans = _ask_yn(
        "Are there existing PM plans in SAP?",
        default=bool(existing.get("existing_pm_plans")),
    )

    approach_options = [
        "full-rcm — Full RCM (comprehensive)",
        "fmeca-simplified — Simplified FMECA",
        "pm-optimization — PM Optimization (brownfield)",
    ]
    approach_raw = _ask_choice("Project objective", approach_options, default=0)
    approach_value = approach_raw.split(" — ")[0]
    approach = StrategyApproach(approach_value)

    # Determine starting milestone
    starting_milestone = 1
    skip_hierarchy = False
    skip_criticality = False

    if has_hierarchy:
        skip_hierarchy = True
        if has_criticality:
            skip_criticality = True
            starting_milestone = 2

    if approach == StrategyApproach.PM_OPTIMIZATION and has_pm_plans:
        starting_milestone = max(starting_milestone, 3)

    # Skills
    if approach == StrategyApproach.FULL_RCM:
        mandatory = ["hierarchy", "criticality", "fmeca", "rcm-decision", "task-definition", "work-packages"]
        optional = ["spare-parts-analysis", "sap-upload"]
    elif approach == StrategyApproach.FMECA_SIMPLIFIED:
        mandatory = ["hierarchy", "criticality", "fmeca-simplified", "task-definition"]
        optional = ["work-packages", "sap-upload"]
    else:
        mandatory = ["pm-review", "task-optimization", "work-packages"]
        optional = ["criticality", "sap-upload"]

    print(f"\n--- Assessment Result ---")
    print(f"  Starting Milestone: M{starting_milestone}")
    print(f"  Approach:           {approach.value}")
    print(f"  Reliability Data:   {'Yes' if has_wo_history else 'Limited'}")
    if skip_hierarchy:
        print("  [INFO] Hierarchy will be imported from 0-input/01-equipment-list/")
    if skip_criticality:
        print("  [INFO] Criticality scores will be imported")

    return {
        "has_hierarchy": has_hierarchy,
        "has_criticality": has_criticality,
        "has_wo_history": has_wo_history,
        "has_pm_plans": has_pm_plans,
        "objective": approach.value,
        "starting_milestone": starting_milestone,
        "skip_hierarchy": skip_hierarchy,
        "skip_criticality": skip_criticality,
        "mandatory_skills": mandatory,
        "optional_skills": optional,
    }


# ═══════════════════════════════════════════════════════════════════════════
# STEP 3 — Scope Refinement
# ═══════════════════════════════════════════════════════════════════════════

def step_3_scope(project: dict[str, Any], assessment: dict[str, Any]) -> dict[str, Any]:
    _heading("STEP 3: Scope Refinement")

    config = project.get("config") or {}
    scope_cfg = config.get("scope", {})

    # Equipment list
    equipment_list: list[str] = []
    if assessment.get("has_hierarchy"):
        print("Enter equipment tags in scope (one per line, empty line to finish):")
        defaults = scope_cfg.get("priority_equipment", [])
        if defaults:
            print(f"  (defaults from project.yaml: {', '.join(defaults[:5])}...)")
        while True:
            line = input("  > ").strip()
            if not line:
                break
            equipment_list.append(_sanitize(line))
        if not equipment_list and defaults:
            equipment_list = [_sanitize(d) for d in defaults]
        print(f"\n  {len(equipment_list)} equipment tags in scope")
    else:
        print("No existing hierarchy — full plant scope.")

    # Batching
    default_batch = min(10, max(1, len(equipment_list)))
    batch_str = _ask(f"Equipment per batch", str(default_batch))
    try:
        batch_size = max(1, int(batch_str))
    except ValueError:
        batch_size = default_batch

    total = len(equipment_list) if equipment_list else int(
        _ask("Estimated total equipment count", str(scope_cfg.get("estimated_equipment_count", 50)))
    )
    num_batches = max(1, -(-total // batch_size))
    print(f"  Estimated batches: {num_batches}")

    # Areas
    print("\nPlant areas in scope (one per line, empty to finish):")
    areas: list[str] = []
    while True:
        line = input("  > ").strip()
        if not line:
            break
        areas.append(_sanitize(line))

    # Priority tags (first batch)
    priority_tags: list[str] = []
    if equipment_list:
        print(f"\nSelect priority equipment for the first batch (indices 1-{len(equipment_list)}, comma-separated):")
        for i, tag in enumerate(equipment_list[:20], 1):
            print(f"  {i}) {tag}")
        raw = input("Priority indices [default: first 5]: ").strip()
        if raw:
            for idx_str in raw.split(","):
                try:
                    idx = int(idx_str.strip()) - 1
                    if 0 <= idx < len(equipment_list):
                        priority_tags.append(equipment_list[idx])
                except ValueError:
                    pass
        if not priority_tags:
            priority_tags = equipment_list[:5]

    return {
        "equipment_list": equipment_list,
        "priority_tags": priority_tags,
        "batch_size": batch_size,
        "total_equipment": total,
        "num_batches": num_batches,
        "areas": areas,
    }


# ═══════════════════════════════════════════════════════════════════════════
# STEP 4 — Plan Generation (reuses Streamlit logic)
# ═══════════════════════════════════════════════════════════════════════════

def step_4_generate_plan(
    project: dict[str, Any],
    assessment: dict[str, Any],
    scope: dict[str, Any],
) -> ExecutionPlan:
    _heading("STEP 4: Execution Plan Generation")

    starting = assessment.get("starting_milestone", 1)
    approach = StrategyApproach(assessment.get("objective", "full-rcm"))
    equipment = scope.get("equipment_list", [])

    plan = ExecutionPlan(
        starting_milestone=starting,
        approach=approach,
        client_slug=project.get("client_slug", ""),
        project_slug=project.get("project_slug", ""),
    )

    counter = 0

    def _nid(prefix: str) -> str:
        nonlocal counter
        counter += 1
        return f"{prefix}-{counter:04d}"

    # M1
    if starting <= 1:
        if not assessment.get("skip_hierarchy"):
            s = ExecutionPlanStage(id="M1-HIER", name="Hierarchy Decomposition", milestone=1, skill="hierarchy")
            if equipment:
                for tag in equipment:
                    s.items.append(ExecutionPlanItem(id=_nid("hier"), description=f"Decompose {tag} into 6-level hierarchy", equipment_tag=tag))
            else:
                s.items.append(ExecutionPlanItem(id=_nid("hier"), description="Build full plant hierarchy (6 levels)"))
            plan.stages.append(s)

        if not assessment.get("skip_criticality"):
            s = ExecutionPlanStage(id="M1-CRIT", name="Criticality Assessment", milestone=1, skill="criticality")
            if equipment:
                for tag in equipment:
                    deps = []
                    if not assessment.get("skip_hierarchy"):
                        for st_ in plan.stages:
                            for it in st_.items:
                                if it.equipment_tag == tag and st_.id == "M1-HIER":
                                    deps = [it.id]
                    s.items.append(ExecutionPlanItem(id=_nid("crit"), description=f"Assess criticality for {tag}", equipment_tag=tag, depends_on=deps))
            else:
                s.items.append(ExecutionPlanItem(id=_nid("crit"), description="Assess criticality for all items"))
            plan.stages.append(s)

    # M2
    if starting <= 2:
        skill = "fmeca" if approach != StrategyApproach.FMECA_SIMPLIFIED else "fmeca-simplified"
        s = ExecutionPlanStage(id="M2-FMECA", name="FMECA / Failure Analysis", milestone=2, skill=skill)
        if equipment:
            for tag in equipment:
                desc = f"Full RCM analysis for {tag}" if approach == StrategyApproach.FULL_RCM else f"FMECA for {tag}"
                s.items.append(ExecutionPlanItem(id=_nid("fmeca"), description=desc, equipment_tag=tag))
        else:
            s.items.append(ExecutionPlanItem(id=_nid("fmeca"), description="Complete FMECA for all critical equipment"))
        plan.stages.append(s)

    # M3
    if starting <= 3:
        s = ExecutionPlanStage(id="M3-TASKS", name="Task Definition & Work Packages", milestone=3, skill="task-definition")
        if equipment:
            for tag in equipment:
                s.items.append(ExecutionPlanItem(id=_nid("task"), description=f"Define maintenance tasks for {tag}", equipment_tag=tag))
        else:
            s.items.append(ExecutionPlanItem(id=_nid("task"), description="Define maintenance tasks for all failure modes"))
        plan.stages.append(s)

        wp = ExecutionPlanStage(id="M3-WP", name="Work Package Assembly", milestone=3, skill="work-packages")
        wp.items.append(ExecutionPlanItem(id=_nid("wp"), description="Group tasks into work packages"))
        wp.items.append(ExecutionPlanItem(id=_nid("wp"), description="Assign materials to REPLACE tasks"))
        wp.items.append(ExecutionPlanItem(id=_nid("wp"), description="Generate work instructions"))
        plan.stages.append(wp)

    # M4
    s = ExecutionPlanStage(id="M4-SAP", name="SAP Upload Package", milestone=4, skill="sap-upload")
    s.items.append(ExecutionPlanItem(id=_nid("sap"), description="Generate SAP Maintenance Item + Task List"))
    s.items.append(ExecutionPlanItem(id=_nid("sap"), description="Validate SAP cross-references"))
    s.items.append(ExecutionPlanItem(id=_nid("sap"), description="Human review of DRAFT SAP package"))
    plan.stages.append(s)

    # Validate
    errors = plan.validate_dependencies()
    if errors:
        print("[ERROR] Dependency errors:")
        for e in errors:
            print(f"  - {e}")
        raise ValueError("Invalid execution plan")

    # Display summary
    progress = plan.calculate_progress()
    print(f"  Total items:        {progress['total_items']}")
    print(f"  Stages:             {len(plan.stages)}")
    print(f"  Starting milestone: M{plan.starting_milestone}")
    print(f"  Approach:           {plan.approach.value}")
    print()
    for sp in progress["stages"]:
        print(f"  [{sp['status']:12s}] {sp['name']} — {sp['total']} items")

    return plan


# ═══════════════════════════════════════════════════════════════════════════
# STEP 5 — Launch Confirmation
# ═══════════════════════════════════════════════════════════════════════════

def step_5_launch(plan: ExecutionPlan, seed_deliverables: bool = False) -> Path | None:
    _heading("STEP 5: Launch Confirmation")

    progress = plan.calculate_progress()
    total = progress["total_items"]

    # Calculate effort from DEFAULT_HOURS per stage category
    est_hours = 0.0
    for stage in plan.stages:
        skill_name = stage.skill or stage.name.lower()
        cat = STAGE_TO_CATEGORY.get(skill_name)
        if cat is None:
            for key, val in STAGE_TO_CATEGORY.items():
                if key in skill_name:
                    cat = val
                    break
        if cat is None:
            cat = DeliverableCategory.CUSTOM
        est_hours += DEFAULT_HOURS[cat]

    est_hours = round(est_hours, 1)
    est_days = round(est_hours / 8, 1)

    print(f"  Checklist items:         {total}")
    print(f"  Stages:                  {len(plan.stages)}")
    print(f"  Estimated consulting hrs: {est_hours}")
    print(f"  Estimated work days:     {est_days}")
    print(f"  Human review gates:      {len(plan.stages)}")
    print()

    if not _ask_yn("Activate this execution plan?", default=True):
        print("Aborted. Plan not saved.")
        return None

    try:
        saved = plan.to_file()
        print(f"\n[OK] Execution plan saved to: {saved}")
    except Exception as exc:
        print(f"[ERROR] Failed to save: {exc}")
        # Fallback: save to current directory
        fallback = Path("execution-plan.yaml")
        fallback.write_text(plan.to_yaml(), encoding="utf-8")
        print(f"[FALLBACK] Saved to {fallback.resolve()}")
        saved = fallback

    # Seed deliverables to database if requested
    if seed_deliverables:
        _seed_deliverables_from_plan(plan)

    return saved


def _seed_deliverables_from_plan(plan: ExecutionPlan) -> None:
    """Seed deliverables to the database from the execution plan."""
    plan_dict = {"stages": [
        {"id": s.id, "name": s.skill or s.name.lower(), "milestone": s.milestone}
        for s in plan.stages
    ]}
    deliverables = DeliverableTrackingEngine.seed_from_execution_plan(
        plan_dict, plan.client_slug, plan.project_slug,
    )
    print(f"\n  [OK] Generated {len(deliverables)} deliverables from plan:")
    for d in deliverables:
        print(f"    - {d['name']} ({d['category']}) — {d['estimated_hours']}h")


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def run_wizard(
    client_slug: str = "",
    project_slug: str = "",
    seed: bool = False,
) -> ExecutionPlan | None:
    """Run the full 5-step wizard and return the plan (or None if aborted)."""
    project = step_1_project_setup(client_slug, project_slug)
    assessment = step_2_assessment(project)
    scope = step_3_scope(project, assessment)
    plan = step_4_generate_plan(project, assessment, scope)
    path = step_5_launch(plan, seed_deliverables=seed)
    return plan if path else None


def main() -> None:
    parser = argparse.ArgumentParser(description="AMS Consultant Wizard (CLI)")
    parser.add_argument("--client", default="", help="Client slug")
    parser.add_argument("--project", default="", help="Project slug")
    parser.add_argument("--seed-deliverables", action="store_true",
                        help="Seed deliverables to database after plan creation")
    args = parser.parse_args()

    try:
        run_wizard(client_slug=args.client, project_slug=args.project,
                    seed=args.seed_deliverables)
    except KeyboardInterrupt:
        print("\n\nWizard cancelled.")
        sys.exit(1)


if __name__ == "__main__":
    main()
