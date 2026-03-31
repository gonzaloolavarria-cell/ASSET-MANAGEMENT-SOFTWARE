"""Page 18: Consultant Wizard — Interactive 5-step project setup.

Guides the consultant through:
  1. Project Setup (read project.yaml, validate docs)
  2. Starting Point Assessment (determine milestone entry)
  3. Scope Refinement (equipment selection, batching)
  4. Execution Plan Generation
  5. Launch Confirmation
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import streamlit as st

st.set_page_config(page_title="Consultant Wizard", page_icon="\u2728", layout="wide")

# ---------------------------------------------------------------------------
# Safe imports — allow page to render an error if backend modules are absent
# ---------------------------------------------------------------------------

try:
    from streamlit_app.i18n import page_init, t as _t
    page_init()

    def t(key: str, **kw: Any) -> str:
        try:
            return _t(key, **kw)
        except Exception:
            return key
except Exception:
    def t(key: str, **kw: Any) -> str:  # type: ignore[misc]
        return key

try:
    from streamlit_app.style import apply_style
    apply_style()
except Exception:
    pass

try:
    from streamlit_app.components.role_banner import role_context_banner
    role_context_banner(18)
except Exception:
    pass

try:
    from agents._shared.paths import (
        get_project_root,
        get_input_dir,
        get_state_dir,
        load_project_config,
        INPUT_SUBDIRS,
        validate_input_structure,
    )
    from agents.orchestration.execution_plan import (
        ExecutionPlan,
        ExecutionPlanStage,
        ExecutionPlanItem,
        PlanStatus,
        StrategyApproach,
    )
    from tools.engines.deliverable_tracking_engine import (
        DEFAULT_HOURS,
        STAGE_TO_CATEGORY,
        DeliverableTrackingEngine,
    )
    from tools.models.schemas import DeliverableCategory
    _BACKEND_OK = True
except ImportError as exc:
    _BACKEND_OK = False
    _IMPORT_ERROR = str(exc)


# ---------------------------------------------------------------------------
# Input sanitization helpers
# ---------------------------------------------------------------------------

_SAFE_TEXT = re.compile(r"^[\w\s\-.,;:()/#&'+\u00C0-\u024F\u0600-\u06FF]*$")
_YAML_INJECTION = re.compile(r"[{}\[\]!%*&|>]")


def _sanitize(value: str, max_len: int = 200) -> str:
    """Strip dangerous chars that could cause YAML injection or XSS."""
    value = value[:max_len].strip()
    if _YAML_INJECTION.search(value):
        value = _YAML_INJECTION.sub("", value)
    return value


# ═══════════════════════════════════════════════════════════════════════════
# Page header
# ═══════════════════════════════════════════════════════════════════════════

st.title(t("wizard.title"))
st.caption(t("wizard.caption"))

if not _BACKEND_OK:
    st.error(f"Backend modules unavailable: {_IMPORT_ERROR}")
    st.stop()


# ═══════════════════════════════════════════════════════════════════════════
# Session state initialisation
# ═══════════════════════════════════════════════════════════════════════════

if "wiz_step" not in st.session_state:
    st.session_state.wiz_step = 1
if "wiz_project" not in st.session_state:
    st.session_state.wiz_project = None
if "wiz_assessment" not in st.session_state:
    st.session_state.wiz_assessment = {}
if "wiz_scope" not in st.session_state:
    st.session_state.wiz_scope = {}
if "wiz_plan" not in st.session_state:
    st.session_state.wiz_plan = None


def _go(step: int) -> None:
    st.session_state.wiz_step = step


# ═══════════════════════════════════════════════════════════════════════════
# Progress indicator
# ═══════════════════════════════════════════════════════════════════════════

STEPS = [
    t("wizard.steps.setup"),
    t("wizard.steps.starting_point"),
    t("wizard.steps.scope"),
    t("wizard.steps.plan"),
    t("wizard.steps.launch"),
]
cols = st.columns(len(STEPS))
for i, (col, label) in enumerate(zip(cols, STEPS), 1):
    if i < st.session_state.wiz_step:
        col.success(f"**{i}. {label}**")
    elif i == st.session_state.wiz_step:
        col.info(f"**{i}. {label}**")
    else:
        col.markdown(f"**{i}. {label}**")

st.divider()


# ═══════════════════════════════════════════════════════════════════════════
# STEP 1 — Project Setup
# ═══════════════════════════════════════════════════════════════════════════

def _step_1() -> None:
    st.header(t("wizard.step_1.heading"))

    # -- Demo Mode quick-fill ---------------------------------------------
    if st.button(t("wizard.demo_mode_btn"), type="secondary"):
        st.session_state._demo_client = "ocp"
        st.session_state._demo_project = "jfc-maintenance-strategy"
        st.info(t("wizard.demo_mode_info"))

    # -- Client / project input -------------------------------------------
    c1, c2 = st.columns(2)
    client_slug = _sanitize(
        c1.text_input("Client slug", value=st.session_state.get("_demo_client", "ocp")).lower()
    )
    project_slug = _sanitize(
        c2.text_input("Project slug", value=st.session_state.get("_demo_project", "jfc-maintenance-strategy")).lower()
    )

    if not client_slug or not project_slug:
        st.warning("Enter both client and project slugs to continue.")
        return

    # -- Load project.yaml ------------------------------------------------
    config = load_project_config(client_slug, project_slug)

    if config:
        st.success("project.yaml loaded")
        project = config.get("project", {})
        client = config.get("client", {})
        scope = config.get("scope", {})
        maint = config.get("maintenance_context", {})
        org = config.get("organization", {})

        with st.expander("Project Summary", expanded=True):
            r1 = st.columns(3)
            r1[0].metric("Client", client.get("name", client_slug))
            r1[1].metric("Plant", scope.get("plant", {}).get("name", "—"))
            r1[2].metric("Scope", scope.get("type", "—"))

            r2 = st.columns(3)
            r2[0].metric("Industry", client.get("industry", "—"))
            r2[1].metric("Maturity", maint.get("strategy_maturity", "—"))
            r2[2].metric("CMMS", maint.get("cmms", "—"))

        st.session_state.wiz_project = {
            "client_slug": client_slug,
            "project_slug": project_slug,
            "config": config,
        }
    else:
        st.warning("project.yaml not found — proceeding in manual mode")
        st.session_state.wiz_project = {
            "client_slug": client_slug,
            "project_slug": project_slug,
            "config": None,
        }

    # -- Validate 0-input/ documents -------------------------------------
    st.subheader("Document Validation")
    try:
        input_dir = get_input_dir(client_slug, project_slug)
        missing = validate_input_structure(client_slug, project_slug)
        found = [d for d in INPUT_SUBDIRS if d not in missing]

        if found:
            for d in found:
                subdir_path = input_dir / d
                file_count = sum(1 for _ in subdir_path.iterdir()) if subdir_path.is_dir() else 0
                icon = "\u2705" if file_count > 0 else "\u26A0\uFE0F"
                st.markdown(f"{icon} **{d}/** — {file_count} file(s)")
        if missing:
            st.warning(f"Missing input folders: {', '.join(missing)}")
    except Exception:
        st.info("Client project folder not found — will be created at launch.")

    # -- Navigation --------------------------------------------------------
    if st.button(t("wizard.nav.next"), type="primary"):
        _go(2)
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# STEP 2 — Starting Point Assessment
# ═══════════════════════════════════════════════════════════════════════════

def _step_2() -> None:
    st.header(t("wizard.step_2.heading"))
    proj = st.session_state.wiz_project or {}
    config = proj.get("config") or {}
    maint = config.get("maintenance_context", {})
    existing = maint.get("existing_data", {})

    # -- Questions --------------------------------------------------------
    has_hierarchy = st.radio(
        "Does the client have an existing equipment hierarchy?",
        ["Yes", "No"],
        index=0 if existing.get("equipment_list") else 1,
        horizontal=True,
    )

    has_criticality = st.radio(
        "Has a criticality assessment been done before?",
        ["Yes", "No"],
        index=0 if maint.get("prior_criticality_assessment")
               or existing.get("criticality_assessment") else 1,
        horizontal=True,
    )

    has_wo_history = st.radio(
        "Is work order / failure history available?",
        ["Yes", "No"],
        index=0 if existing.get("failure_history") else 1,
        horizontal=True,
    )

    has_pm_plans = st.radio(
        "Are there existing PM plans in SAP?",
        ["Yes", "No"],
        index=0 if existing.get("existing_pm_plans") else 1,
        horizontal=True,
    )

    objective = st.selectbox(
        "Project objective",
        [a.value for a in StrategyApproach],
        format_func=lambda v: {
            "full-rcm": "Full RCM (comprehensive)",
            "fmeca-simplified": "Simplified FMECA",
            "pm-optimization": "PM Optimization (brownfield)",
        }.get(v, v),
    )

    # -- Logic: determine starting milestone ------------------------------
    starting_milestone = 1
    skip_hierarchy = False
    skip_criticality = False

    if has_hierarchy == "Yes":
        skip_hierarchy = True
        if has_criticality == "Yes":
            skip_criticality = True
            starting_milestone = 2  # skip M1 entirely

    if objective == StrategyApproach.PM_OPTIMIZATION.value:
        if has_pm_plans == "Yes":
            starting_milestone = max(starting_milestone, 3)

    approach = StrategyApproach(objective)
    mandatory_skills: list[str] = []
    optional_skills: list[str] = []

    if approach == StrategyApproach.FULL_RCM:
        mandatory_skills = ["hierarchy", "criticality", "fmeca", "rcm-decision", "task-definition", "work-packages"]
        optional_skills = ["spare-parts-analysis", "sap-upload"]
    elif approach == StrategyApproach.FMECA_SIMPLIFIED:
        mandatory_skills = ["hierarchy", "criticality", "fmeca-simplified", "task-definition"]
        optional_skills = ["work-packages", "sap-upload"]
    elif approach == StrategyApproach.PM_OPTIMIZATION:
        mandatory_skills = ["pm-review", "task-optimization", "work-packages"]
        optional_skills = ["criticality", "sap-upload"]

    # -- Summary ----------------------------------------------------------
    st.divider()
    st.subheader("Assessment Result")
    c1, c2, c3 = st.columns(3)
    c1.metric("Starting Milestone", f"M{starting_milestone}")
    c2.metric("Approach", approach.value)
    c3.metric("Reliability Analysis", "Yes" if has_wo_history == "Yes" else "Limited")

    if skip_hierarchy:
        st.info("Equipment hierarchy will be imported from 0-input/01-equipment-list/")
    if skip_criticality:
        st.info("Criticality scores will be imported (skip criticality stage)")

    st.session_state.wiz_assessment = {
        "has_hierarchy": has_hierarchy == "Yes",
        "has_criticality": has_criticality == "Yes",
        "has_wo_history": has_wo_history == "Yes",
        "has_pm_plans": has_pm_plans == "Yes",
        "objective": approach.value,
        "starting_milestone": starting_milestone,
        "skip_hierarchy": skip_hierarchy,
        "skip_criticality": skip_criticality,
        "mandatory_skills": mandatory_skills,
        "optional_skills": optional_skills,
    }

    # -- Navigation -------------------------------------------------------
    bc, nc = st.columns(2)
    if bc.button(t("wizard.nav.back")):
        _go(1)
        st.rerun()
    if nc.button(t("wizard.nav.next"), type="primary"):
        _go(3)
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# STEP 3 — Scope Refinement
# ═══════════════════════════════════════════════════════════════════════════

def _step_3() -> None:
    st.header(t("wizard.step_3.heading"))
    proj = st.session_state.wiz_project or {}
    assessment = st.session_state.wiz_assessment
    config = proj.get("config") or {}
    scope_cfg = config.get("scope", {})

    # -- Equipment selection (if hierarchy available) ---------------------
    equipment_list: list[str] = []

    if assessment.get("has_hierarchy"):
        st.subheader("Equipment Selection")
        # Try to read equipment list from input dir
        try:
            client_slug = proj["client_slug"]
            project_slug = proj["project_slug"]
            eq_dir = get_input_dir(client_slug, project_slug) / "01-equipment-list"
            if eq_dir.is_dir():
                for f in eq_dir.iterdir():
                    if f.suffix in (".csv", ".xlsx", ".xls"):
                        st.info(f"Found equipment file: {f.name}")
                        break
        except Exception:
            pass

        # Manual equipment tags input
        eq_input = st.text_area(
            "Equipment tags in scope (one per line, or paste from spreadsheet)",
            value="\n".join(scope_cfg.get("priority_equipment", [])),
            height=150,
        )
        equipment_list = [
            _sanitize(line.strip())
            for line in eq_input.strip().splitlines()
            if line.strip()
        ]

        if equipment_list:
            st.success(f"{len(equipment_list)} equipment tags in scope")

        # Priority selection
        priority_tags = st.multiselect(
            "Priority equipment (first batch)",
            equipment_list,
            default=equipment_list[:5] if equipment_list else [],
        )
    else:
        st.info("No existing hierarchy — full plant scope will be used.")
        priority_tags = []

    # -- Batching strategy -----------------------------------------------
    st.subheader("Batching Strategy")
    batch_size = st.slider(
        "Equipment per batch",
        min_value=1,
        max_value=50,
        value=min(10, max(1, len(equipment_list))),
    )

    total_equipment = len(equipment_list) if equipment_list else st.number_input(
        "Estimated total equipment count",
        min_value=1,
        max_value=5000,
        value=scope_cfg.get("estimated_equipment_count", 50),
    )

    num_batches = max(1, -(-total_equipment // batch_size))  # ceiling division
    st.metric("Estimated batches", num_batches)

    # -- Areas in scope ---------------------------------------------------
    st.subheader("Areas in Scope")
    areas_input = st.text_area(
        "Plant areas (one per line)",
        value="\n".join(scope_cfg.get("areas_in_scope", [])),
        height=100,
    )
    areas = [_sanitize(a.strip()) for a in areas_input.strip().splitlines() if a.strip()]

    st.session_state.wiz_scope = {
        "equipment_list": equipment_list,
        "priority_tags": priority_tags,
        "batch_size": batch_size,
        "total_equipment": total_equipment,
        "num_batches": num_batches,
        "areas": areas,
    }

    # -- Navigation -------------------------------------------------------
    bc, nc = st.columns(2)
    if bc.button(t("wizard.nav.back")):
        _go(2)
        st.rerun()
    if nc.button(t("wizard.nav.next"), type="primary"):
        _go(4)
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# STEP 4 — Execution Plan Generation
# ═══════════════════════════════════════════════════════════════════════════

def _generate_plan() -> ExecutionPlan:
    """Build an ExecutionPlan from wizard state."""
    proj = st.session_state.wiz_project or {}
    assessment = st.session_state.wiz_assessment
    scope = st.session_state.wiz_scope

    starting = assessment.get("starting_milestone", 1)
    approach = StrategyApproach(assessment.get("objective", "full-rcm"))
    equipment = scope.get("equipment_list", [])
    batch_size = scope.get("batch_size", 10)

    plan = ExecutionPlan(
        starting_milestone=starting,
        approach=approach,
        client_slug=proj.get("client_slug", ""),
        project_slug=proj.get("project_slug", ""),
    )

    item_counter = 0

    def _next_id(prefix: str) -> str:
        nonlocal item_counter
        item_counter += 1
        return f"{prefix}-{item_counter:04d}"

    # ── M1: Hierarchy & Criticality ──────────────────────────────────────

    if starting <= 1:
        # Stage: Hierarchy
        if not assessment.get("skip_hierarchy"):
            hier_stage = ExecutionPlanStage(
                id="M1-HIER", name="Hierarchy Decomposition", milestone=1,
                skill="hierarchy",
            )
            if equipment:
                for tag in equipment:
                    hier_stage.items.append(ExecutionPlanItem(
                        id=_next_id("hier"),
                        description=f"Decompose {tag} into 6-level hierarchy",
                        equipment_tag=tag,
                    ))
            else:
                hier_stage.items.append(ExecutionPlanItem(
                    id=_next_id("hier"),
                    description="Build full plant hierarchy (6 levels)",
                ))
            plan.stages.append(hier_stage)

        # Stage: Criticality
        if not assessment.get("skip_criticality"):
            crit_stage = ExecutionPlanStage(
                id="M1-CRIT", name="Criticality Assessment", milestone=1,
                skill="criticality",
            )
            dep_prefix = "M1-HIER" if not assessment.get("skip_hierarchy") else ""
            if equipment:
                for tag in equipment:
                    depends = []
                    if dep_prefix:
                        # Find the matching hierarchy item
                        for s in plan.stages:
                            for it in s.items:
                                if it.equipment_tag == tag and s.id == "M1-HIER":
                                    depends = [it.id]
                    crit_stage.items.append(ExecutionPlanItem(
                        id=_next_id("crit"),
                        description=f"Assess criticality for {tag}",
                        equipment_tag=tag,
                        depends_on=depends,
                    ))
            else:
                crit_stage.items.append(ExecutionPlanItem(
                    id=_next_id("crit"),
                    description="Assess criticality for all maintainable items",
                ))
            plan.stages.append(crit_stage)

    # ── M2: FMECA ────────────────────────────────────────────────────────

    if starting <= 2:
        fmeca_stage = ExecutionPlanStage(
            id="M2-FMECA", name="FMECA / Failure Analysis", milestone=2,
            skill="fmeca" if approach != StrategyApproach.FMECA_SIMPLIFIED else "fmeca-simplified",
        )

        # Group by criticality class if available
        if equipment:
            for tag in equipment:
                # Determine treatment based on approach
                crit_class = ""  # Will be filled during execution
                desc = f"FMECA for {tag}"
                if approach == StrategyApproach.FULL_RCM:
                    desc = f"Full RCM analysis for {tag}"
                fmeca_stage.items.append(ExecutionPlanItem(
                    id=_next_id("fmeca"),
                    description=desc,
                    equipment_tag=tag,
                    criticality_class=crit_class,
                ))
        else:
            fmeca_stage.items.append(ExecutionPlanItem(
                id=_next_id("fmeca"),
                description="Complete FMECA for all critical equipment",
            ))

        plan.stages.append(fmeca_stage)

    # ── M3: Strategy + Tasks + Resources ─────────────────────────────────

    if starting <= 3:
        # Task definition stage
        task_stage = ExecutionPlanStage(
            id="M3-TASKS", name="Task Definition & Work Packages", milestone=3,
            skill="task-definition",
        )
        if equipment:
            for tag in equipment:
                task_stage.items.append(ExecutionPlanItem(
                    id=_next_id("task"),
                    description=f"Define maintenance tasks for {tag}",
                    equipment_tag=tag,
                ))
        else:
            task_stage.items.append(ExecutionPlanItem(
                id=_next_id("task"),
                description="Define maintenance tasks for all failure modes",
            ))
        plan.stages.append(task_stage)

        # Work packages stage
        wp_stage = ExecutionPlanStage(
            id="M3-WP", name="Work Package Assembly", milestone=3,
            skill="work-packages",
        )
        wp_stage.items.append(ExecutionPlanItem(
            id=_next_id("wp"),
            description="Group tasks into work packages",
        ))
        wp_stage.items.append(ExecutionPlanItem(
            id=_next_id("wp"),
            description="Assign materials to REPLACE tasks",
        ))
        wp_stage.items.append(ExecutionPlanItem(
            id=_next_id("wp"),
            description="Generate work instructions",
        ))
        plan.stages.append(wp_stage)

    # ── M4: SAP Upload ───────────────────────────────────────────────────

    sap_stage = ExecutionPlanStage(
        id="M4-SAP", name="SAP Upload Package", milestone=4,
        skill="sap-upload",
    )
    sap_stage.items.append(ExecutionPlanItem(
        id=_next_id("sap"),
        description="Generate SAP Maintenance Item + Task List",
    ))
    sap_stage.items.append(ExecutionPlanItem(
        id=_next_id("sap"),
        description="Validate SAP cross-references",
    ))
    sap_stage.items.append(ExecutionPlanItem(
        id=_next_id("sap"),
        description="Human review of DRAFT SAP package",
    ))
    plan.stages.append(sap_stage)

    return plan


def _step_4() -> None:
    st.header(t("wizard.step_4.heading"))

    if st.session_state.wiz_plan is None:
        with st.spinner("Generating execution plan..."):
            plan = _generate_plan()
            # Validate dependencies
            errors = plan.validate_dependencies()
            if errors:
                st.error("Dependency errors detected:")
                for e in errors:
                    st.markdown(f"- {e}")
                return
            st.session_state.wiz_plan = plan

    plan: ExecutionPlan = st.session_state.wiz_plan
    progress = plan.calculate_progress()

    # -- Summary ----------------------------------------------------------
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Items", progress["total_items"])
    c2.metric("Starting Milestone", f"M{plan.starting_milestone}")
    c3.metric("Approach", plan.approach.value)
    c4.metric("Stages", len(plan.stages))

    # -- Stage details ----------------------------------------------------
    for sp in progress["stages"]:
        stage_obj = next(s for s in plan.stages if s.id == sp["stage_id"])
        with st.expander(
            f"{sp['name']} — M{stage_obj.milestone} ({sp['total']} items)",
            expanded=True,
        ):
            st.progress(sp["progress"] / 100)
            for item in stage_obj.items:
                tag = f" [{item.equipment_tag}]" if item.equipment_tag else ""
                st.markdown(f"- [ ] {item.description}{tag}")

    # -- Navigation -------------------------------------------------------
    bc, rc, nc = st.columns(3)
    if bc.button(t("wizard.nav.back")):
        _go(3)
        st.session_state.wiz_plan = None
        st.rerun()
    if rc.button(t("wizard.step_4.regen")):
        st.session_state.wiz_plan = None
        st.rerun()
    if nc.button(t("wizard.nav.next"), type="primary"):
        _go(5)
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# STEP 5 — Launch Confirmation
# ═══════════════════════════════════════════════════════════════════════════

def _step_5() -> None:
    st.header(t("wizard.step_5.heading"))
    plan: ExecutionPlan | None = st.session_state.wiz_plan
    if plan is None:
        st.error("No execution plan generated. Go back to Step 4.")
        return

    progress = plan.calculate_progress()
    proj = st.session_state.wiz_project or {}

    # -- Summary ----------------------------------------------------------
    st.subheader("Execution Plan Summary")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total checklist items", progress["total_items"])
    c2.metric("Stages", len(plan.stages))
    c3.metric("Starting at", f"Milestone {plan.starting_milestone}")

    st.divider()

    # -- Effort estimation ------------------------------------------------
    st.subheader("Effort Estimation")

    # Calculate effort from DEFAULT_HOURS per stage category
    est_hours = 0.0
    stage_estimates: list[tuple[str, str, float]] = []
    for stage in plan.stages:
        skill_name = stage.skill or stage.name.lower()
        cat = STAGE_TO_CATEGORY.get(skill_name)
        if cat is None:
            # Try prefix match
            for key, val in STAGE_TO_CATEGORY.items():
                if key in skill_name:
                    cat = val
                    break
        if cat is None:
            cat = DeliverableCategory.CUSTOM
        hours = DEFAULT_HOURS[cat]
        est_hours += hours
        stage_estimates.append((stage.name, cat.value, hours))

    est_hours = round(est_hours, 1)
    est_days = round(est_hours / 8, 1)

    e1, e2, e3 = st.columns(3)
    e1.metric("Estimated Consulting Hours", est_hours)
    e2.metric("Estimated Working Days", est_days)
    e3.metric("Requires Human Review", f"{len(plan.stages)} gates")

    with st.expander("Effort Breakdown by Stage"):
        for name, cat, hours in stage_estimates:
            st.markdown(f"- **{name}** ({cat}): {hours}h")

    st.divider()

    # -- Launch -----------------------------------------------------------
    st.subheader("Activate Plan")
    st.warning(
        "This will create the execution plan file at "
        f"`2-state/execution-plan.yaml` for project "
        f"**{proj.get('client_slug', '?')}/{proj.get('project_slug', '?')}**."
    )

    bc, lc = st.columns(2)
    if bc.button(t("wizard.nav.back")):
        _go(4)
        st.rerun()

    if lc.button(t("wizard.nav.launch_btn"), type="primary"):
        try:
            saved_path = plan.to_file()
            st.success(f"Execution plan saved to: `{saved_path}`")
            st.balloons()
            st.session_state.wiz_launched = True
        except Exception as exc:
            st.error(f"Failed to save plan: {exc}")
            # Offer download as fallback
            st.download_button(
                "Download execution-plan.yaml",
                data=plan.to_yaml(),
                file_name="execution-plan.yaml",
                mime="text/yaml",
            )

    # -- Seed deliverables ------------------------------------------------
    if st.session_state.get("wiz_launched"):
        st.divider()
        st.subheader("Seed Deliverables to Database")
        st.info(
            "Create trackable deliverables from this execution plan. "
            "Each stage becomes a deliverable with estimated hours."
        )

        if st.button(t("wizard.nav.seed_btn"), type="secondary"):
            try:
                from streamlit_app.api_client import seed_deliverables
                plan_dict = {"stages": [
                    {"id": s.id, "name": s.skill or s.name.lower(), "milestone": s.milestone}
                    for s in plan.stages
                ]}
                result = seed_deliverables(
                    plan_dict,
                    proj.get("client_slug", ""),
                    proj.get("project_slug", ""),
                )
                created = result.get("created", 0)
                st.success(f"Created {created} deliverables. Track them on Page 21.")
            except Exception as exc:
                st.error(f"Failed to seed deliverables: {exc}")


# ═══════════════════════════════════════════════════════════════════════════
# Router
# ═══════════════════════════════════════════════════════════════════════════

_STEP_FNS = {1: _step_1, 2: _step_2, 3: _step_3, 4: _step_4, 5: _step_5}
_STEP_FNS[st.session_state.wiz_step]()

try:
    from streamlit_app.components.feedback import feedback_widget
    feedback_widget("wizard")
except Exception:
    pass
