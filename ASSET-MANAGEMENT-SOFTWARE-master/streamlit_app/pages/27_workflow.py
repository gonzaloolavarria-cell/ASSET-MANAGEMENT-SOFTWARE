"""Page 27: Workflow Launcher — G-17: trigger and supervise the M1→M4 agent pipeline via UI.

Three-section UI:
  A) Launch form (equipment + plant code)
  B) Status monitor (polling, progress bar)
  C) Gate approval panel (shown when status=AWAITING_APPROVAL)
"""

import time

import streamlit as st
from streamlit_app import api_client
from streamlit_app.i18n import page_init, t
from streamlit_app.style import apply_style
from streamlit_app.components.role_banner import role_context_banner

st.set_page_config(page_title="Workflow Launcher", layout="wide")
page_init()
apply_style()
role_context_banner(27)

st.title(t("workflow.title"))
st.markdown(t("workflow.description"))

# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------

if "wf_session_id" not in st.session_state:
    st.session_state.wf_session_id = None
if "wf_status" not in st.session_state:
    st.session_state.wf_status = None

# ---------------------------------------------------------------------------
# Helper: milestone label
# ---------------------------------------------------------------------------

_MILESTONE_LABELS = {
    1: "M1: Hierarchy + Criticality",
    2: "M2: FMECA + RCM",
    3: "M3: Strategy + Work Packages",
    4: "M4: SAP Export",
}

_STATUS_ICONS = {
    "STARTING": "⏳",
    "RUNNING": "🔄",
    "AWAITING_APPROVAL": "🔔",
    "COMPLETED": "✅",
    "FAILED": "❌",
    "REJECTED": "🚫",
}


def _status_label(status: str) -> str:
    icon = _STATUS_ICONS.get(status, "❓")
    return f"{icon} {status}"


# ---------------------------------------------------------------------------
# Section A: Launch form (shown when no active session)
# ---------------------------------------------------------------------------

if st.session_state.wf_session_id is None:
    st.subheader(t("workflow.launch_title"))

    col1, col2 = st.columns([3, 1])
    with col1:
        equipment = st.text_input(
            t("workflow.equipment_label"),
            value="SAG Mill 001",
            placeholder="e.g. SAG Mill 001, Ball Mill BM-201",
        )
    with col2:
        plant_code = st.text_input(t("workflow.plant_label"), value="OCP-JFC")

    if st.button(t("workflow.launch_btn"), type="primary", use_container_width=True):
        if not equipment.strip():
            st.error(t("workflow.error_equipment_required"))
        else:
            with st.spinner(t("workflow.launching")):
                try:
                    result = api_client.run_workflow(equipment.strip(), plant_code.strip() or "OCP")
                    st.session_state.wf_session_id = result["session_id"]
                    st.session_state.wf_status = result.get("status", "STARTING")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Failed to start workflow: {exc}")

    # Show past sessions in expander
    with st.expander(t("workflow.past_sessions"), expanded=False):
        try:
            sessions = api_client.list_workflow_sessions()
            if sessions:
                for s in reversed(sessions):
                    icon = _STATUS_ICONS.get(s.get("status", ""), "❓")
                    st.markdown(
                        f"{icon} **{s.get('equipment', '?')}** ({s.get('plant_code', '?')}) — "
                        f"`{s.get('status')}` — {s.get('started_at', '')[:19]}"
                    )
                    if st.button(f"Resume {s['session_id'][:8]}", key=f"resume_{s['session_id']}"):
                        st.session_state.wf_session_id = s["session_id"]
                        st.rerun()
            else:
                st.info(t("workflow.no_past_sessions"))
        except Exception:
            st.warning(t("workflow.api_unavailable"))

else:
    # ---------------------------------------------------------------------------
    # Section B: Status monitor
    # ---------------------------------------------------------------------------

    session_id = st.session_state.wf_session_id

    # Poll status
    status_data = None
    try:
        status_data = api_client.get_workflow_session(session_id)
        st.session_state.wf_status = status_data.get("status", "UNKNOWN")
    except Exception as exc:
        st.error(f"Failed to fetch session status: {exc}")

    # Header row
    col_title, col_reset = st.columns([5, 1])
    with col_title:
        st.subheader(t("workflow.monitor_title"))
    with col_reset:
        if st.button(t("workflow.new_session_btn")):
            st.session_state.wf_session_id = None
            st.session_state.wf_status = None
            st.rerun()

    if status_data:
        status = status_data.get("status", "UNKNOWN")
        current_m = status_data.get("current_milestone") or 0
        milestones_approved = status_data.get("milestones_approved", 0)
        equipment_name = status_data.get("equipment", "?")

        st.caption(f"Session: `{session_id}`")
        st.metric(t("workflow.status_label"), _status_label(status))
        st.metric(t("workflow.equipment_label"), equipment_name)

        # Progress bar
        progress_value = milestones_approved / 4
        if status == "AWAITING_APPROVAL" and current_m:
            progress_value = (current_m - 0.5) / 4
        st.progress(progress_value, text=t("workflow.milestone_progress").format(milestones_approved, 4))

        # Milestone steps visual
        cols = st.columns(4)
        for i, (col, label) in enumerate(zip(cols, _MILESTONE_LABELS.values()), start=1):
            with col:
                if i <= milestones_approved:
                    col.success(f"✅ {label}")
                elif i == current_m and status in ("RUNNING", "AWAITING_APPROVAL"):
                    col.warning(f"🔄 {label}")
                else:
                    col.info(f"⬜ {label}")

        # Error display
        if status == "FAILED":
            st.error(f"**{t('workflow.status_failed')}**\n\n{status_data.get('error', '')}")

        # Completed
        if status == "COMPLETED":
            st.success(t("workflow.status_completed"))
            counts = status_data.get("entity_counts") or {}
            if counts:
                st.subheader(t("workflow.results_title"))
                for entity, count in counts.items():
                    if isinstance(count, bool):
                        st.write(f"- **{entity}**: {'Yes' if count else 'No'}")
                    elif count:
                        st.write(f"- **{entity}**: {count}")
            sap_path = status_data.get("sap_xlsx_path", "")
            if sap_path:
                st.info(f"SAP Export: `{sap_path}`")

        # ---------------------------------------------------------------------------
        # Section C: Gate approval (only when AWAITING_APPROVAL)
        # ---------------------------------------------------------------------------

        if status == "AWAITING_APPROVAL":
            st.divider()
            milestone_num = status_data.get("current_milestone", "?")
            st.subheader(
                f"🔔 {t('workflow.gate_title').format(milestone_num)} — "
                f"{_MILESTONE_LABELS.get(milestone_num, '')}"
            )

            gate_summary = status_data.get("gate_summary", "")
            if gate_summary:
                with st.container(border=True):
                    st.text(gate_summary)

            feedback = st.text_area(
                t("workflow.feedback_label"),
                placeholder=t("workflow.feedback_placeholder"),
                key=f"feedback_{milestone_num}",
            )

            col_approve, col_modify, col_reject = st.columns(3)

            with col_approve:
                if st.button(t("workflow.approve_btn"), type="primary", use_container_width=True):
                    _submit_gate(session_id, "approve", "")

            with col_modify:
                if st.button(t("workflow.modify_btn"), use_container_width=True):
                    if feedback.strip():
                        _submit_gate(session_id, "modify", feedback.strip())
                    else:
                        st.warning(t("workflow.modify_requires_feedback"))

            with col_reject:
                if st.button(t("workflow.reject_btn"), type="secondary", use_container_width=True):
                    _submit_gate(session_id, "reject", feedback.strip())

        # Auto-refresh when running or starting
        if status in ("STARTING", "RUNNING", "AWAITING_APPROVAL"):
            if status in ("STARTING", "RUNNING"):
                time.sleep(3)
                st.rerun()
            else:
                # Waiting for user — just show a refresh hint
                st.caption(t("workflow.polling_hint"))


def _submit_gate(session_id: str, action: str, feedback: str) -> None:
    """Submit gate decision and trigger rerun."""
    try:
        api_client.approve_workflow_gate(session_id, action, feedback)
        st.success(f"Gate decision '{action}' submitted.")
        time.sleep(1)
        st.rerun()
    except Exception as exc:
        st.error(f"Failed to submit gate: {exc}")
