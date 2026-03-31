"""Page 19: Execution Progress Dashboard.

Displays execution plan progress with:
- Overall progress bar
- Per-milestone/stage bars
- Expandable checklist with clickable checkboxes
- Color-coded status indicators
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

st.set_page_config(page_title="Execution Progress", page_icon="\u2705", layout="wide")

try:
    from streamlit_app.i18n import page_init, t as _t
    page_init()
except Exception:
    pass

try:
    from streamlit_app.components.role_banner import role_context_banner
    role_context_banner(19)
except Exception:
    pass

try:
    from agents._shared.paths import get_state_dir, load_project_config
    from agents.orchestration.execution_plan import (
        ExecutionPlan,
        PlanStatus,
    )
    _BACKEND_OK = True
except ImportError as exc:
    _BACKEND_OK = False
    _IMPORT_ERROR = str(exc)


# ---------------------------------------------------------------------------
# Status colours
# ---------------------------------------------------------------------------

STATUS_COLORS = {
    PlanStatus.PENDING: "#9E9E9E",      # grey
    PlanStatus.IN_PROGRESS: "#2196F3",  # blue
    PlanStatus.COMPLETED: "#4CAF50",    # green
    PlanStatus.SKIPPED: "#FF9800",      # orange
} if _BACKEND_OK else {}

STATUS_ICONS = {
    PlanStatus.PENDING: "\u23F3",       # hourglass
    PlanStatus.IN_PROGRESS: "\u25B6\uFE0F",  # play
    PlanStatus.COMPLETED: "\u2705",     # check
    PlanStatus.SKIPPED: "\u23E9",       # fast-forward
} if _BACKEND_OK else {}


def _status_badge(status: PlanStatus) -> str:
    color = STATUS_COLORS.get(status, "#9E9E9E")
    icon = STATUS_ICONS.get(status, "")
    return (
        f'<span style="background-color:{color};color:white;'
        f'padding:2px 8px;border-radius:4px;font-size:0.8em;">'
        f'{icon} {status.value}</span>'
    )


# ═══════════════════════════════════════════════════════════════════════════
# Page header
# ═══════════════════════════════════════════════════════════════════════════

st.title("Execution Progress")

if not _BACKEND_OK:
    st.error(f"Backend modules unavailable: {_IMPORT_ERROR}")
    st.stop()


# ═══════════════════════════════════════════════════════════════════════════
# Load execution plan
# ═══════════════════════════════════════════════════════════════════════════

c1, c2 = st.columns(2)
client_slug = c1.text_input("Client slug", value="ocp").strip().lower()
project_slug = c2.text_input("Project slug", value="jfc-maintenance-strategy").strip().lower()

plan: ExecutionPlan | None = None

if client_slug and project_slug:
    try:
        plan_path = get_state_dir(client_slug, project_slug) / "execution-plan.yaml"
        if plan_path.is_file():
            plan = ExecutionPlan.from_file(plan_path)
            st.success(f"Loaded: `{plan_path}`")
        else:
            st.warning(f"No execution plan found at `{plan_path}`")
    except Exception as exc:
        st.error(f"Error loading plan: {exc}")

# Allow file upload as fallback
uploaded = st.file_uploader("Or upload execution-plan.yaml", type=["yaml", "yml"])
if uploaded is not None:
    try:
        plan = ExecutionPlan.from_yaml(uploaded.getvalue().decode("utf-8"))
        st.success("Loaded from upload")
    except Exception as exc:
        st.error(f"Invalid YAML: {exc}")

if plan is None:
    st.info("Load or upload an execution plan to view progress.")
    st.stop()


# ═══════════════════════════════════════════════════════════════════════════
# Overall progress
# ═══════════════════════════════════════════════════════════════════════════

progress = plan.calculate_progress()

st.divider()
st.subheader("Overall Progress")
st.progress(progress["overall_progress"] / 100)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Progress", f"{progress['overall_progress']}%")
c2.metric("Completed", f"{progress['total_completed']} / {progress['total_items']}")
c3.metric("Stages", len(plan.stages))
c4.metric("Approach", plan.approach.value)


# ═══════════════════════════════════════════════════════════════════════════
# Per-milestone bar chart
# ═══════════════════════════════════════════════════════════════════════════

st.divider()
st.subheader("Progress by Milestone")

# Group stages by milestone
milestones: dict[int, list[dict[str, Any]]] = {}
for sp in progress["stages"]:
    stage_obj = next(s for s in plan.stages if s.id == sp["stage_id"])
    m = stage_obj.milestone
    milestones.setdefault(m, []).append(sp)

for m_num in sorted(milestones.keys()):
    stage_infos = milestones[m_num]
    total = sum(s["total"] for s in stage_infos)
    done = sum(s["completed"] for s in stage_infos)
    pct = round(done / total * 100, 1) if total else 100.0

    st.markdown(f"**Milestone {m_num}** — {pct}% ({done}/{total})")
    st.progress(pct / 100)


# ═══════════════════════════════════════════════════════════════════════════
# Checklist by stage (expandable, with checkboxes)
# ═══════════════════════════════════════════════════════════════════════════

st.divider()
st.subheader("Detailed Checklist")

# Track whether the user made any changes
plan_changed = False

for stage in plan.stages:
    sp = next(s for s in progress["stages"] if s["stage_id"] == stage.id)
    badge = _status_badge(stage.status)

    with st.expander(
        f"M{stage.milestone} — {stage.name} ({sp['completed']}/{sp['total']})",
        expanded=(stage.status == PlanStatus.IN_PROGRESS),
    ):
        st.markdown(badge, unsafe_allow_html=True)
        st.progress(sp["progress"] / 100)

        for item in stage.items:
            col1, col2 = st.columns([0.05, 0.95])
            is_done = item.status in (PlanStatus.COMPLETED, PlanStatus.SKIPPED)
            checked = col1.checkbox(
                "done",
                value=is_done,
                key=f"cb_{item.id}",
                label_visibility="collapsed",
            )
            # Detect user toggle
            if checked and not is_done:
                item.mark_completed()
                stage.recalculate_status()
                plan_changed = True
            elif not checked and is_done and item.status == PlanStatus.COMPLETED:
                item.status = PlanStatus.PENDING
                item.completed_at = None
                stage.recalculate_status()
                plan_changed = True

            tag = f" `[{item.equipment_tag}]`" if item.equipment_tag else ""
            crit = f" `{item.criticality_class}`" if item.criticality_class else ""
            status_icon = STATUS_ICONS.get(item.status, "")
            col2.markdown(f"{status_icon} {item.description}{tag}{crit}")

            if item.started_at:
                col2.caption(f"Started: {item.started_at}")
            if item.completed_at:
                col2.caption(f"Completed: {item.completed_at}")

# ═══════════════════════════════════════════════════════════════════════════
# Persist changes
# ═══════════════════════════════════════════════════════════════════════════

if plan_changed:
    try:
        plan.to_file()
        st.toast("Progress saved", icon="\u2705")
    except Exception:
        pass
    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# Timestamps & metadata
# ═══════════════════════════════════════════════════════════════════════════

st.divider()
with st.expander("Plan Metadata"):
    st.json({
        "created_at": plan.created_at,
        "starting_milestone": plan.starting_milestone,
        "approach": plan.approach.value,
        "client_slug": plan.client_slug,
        "project_slug": plan.project_slug,
    })


# ═══════════════════════════════════════════════════════════════════════════
# Sidebar: Deliverable Summary
# ═══════════════════════════════════════════════════════════════════════════

try:
    from streamlit_app import api_client as _api

    if client_slug and project_slug:
        summary = _api.get_deliverable_summary(client_slug, project_slug)
        if summary and summary.get("total_deliverables", 0) > 0:
            with st.sidebar:
                st.markdown("---")
                st.subheader("Deliverables")
                total = summary["total_deliverables"]
                pct = summary.get("overall_completion_pct", 0)
                st.progress(pct / 100)
                st.metric("Completion", f"{pct:.0f}%")
                est = summary.get("total_estimated_hours", 0)
                act = summary.get("total_actual_hours", 0)
                st.metric("Hours", f"{act:.1f} / {est:.1f}h")
                by_status = summary.get("by_status", {})
                if by_status:
                    parts = [f"{k}: {v}" for k, v in by_status.items()]
                    st.caption(" | ".join(parts))
                st.page_link("pages/21_deliverables.py", label="Open Deliverables Page")
except Exception:
    pass
