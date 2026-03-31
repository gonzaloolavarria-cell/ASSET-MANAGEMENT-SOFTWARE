"""Page 22: Execution Checklists — GAP-W06.

Interactive digital work execution with gate enforcement,
condition codes, and supervisor closure.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Execution Checklists", page_icon="📋", layout="wide")

try:
    from streamlit_app.i18n import page_init, t as _t
    page_init()
except Exception:
    pass

try:
    from streamlit_app.components.role_banner import role_context_banner
    role_context_banner(22)
except Exception:
    pass

try:
    from streamlit_app import api_client
    _BACKEND_OK = True
except ImportError as exc:
    _BACKEND_OK = False
    _IMPORT_ERROR = str(exc)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STEP_TYPE_COLORS = {
    "SAFETY_CHECK": "#F44336",
    "QUALITY_GATE": "#FF9800",
    "TASK_OPERATION": "#2196F3",
    "INSPECTION": "#9C27B0",
    "COMMISSIONING": "#4CAF50",
    "HANDOVER": "#009688",
}

STATUS_ICONS = {
    "PENDING": "⏳",
    "BLOCKED": "🚫",
    "IN_PROGRESS": "▶️",
    "COMPLETED": "✅",
    "SKIPPED": "⏩",
    "FAILED": "❌",
}

CONDITION_CODES = {
    1: "1 — No Fault Found",
    2: "2 — Fault Found & Fixed",
    3: "3 — Defect Found, Not Fixed",
}


def _type_badge(step_type: str) -> str:
    color = STEP_TYPE_COLORS.get(step_type, "#607D8B")
    label = step_type.replace("_", " ").title()
    return (
        f'<span style="background-color:{color};color:white;'
        f'padding:2px 8px;border-radius:4px;font-size:0.75em;">'
        f'{label}</span>'
    )


def _status_icon(status: str) -> str:
    return STATUS_ICONS.get(status, "")


# ═══════════════════════════════════════════════════════════════════════════
# Page header
# ═══════════════════════════════════════════════════════════════════════════

st.title("Execution Checklists")
st.caption("Digital work execution with gate enforcement — GAP-W06")

if not _BACKEND_OK:
    st.error(f"Backend modules unavailable: {_IMPORT_ERROR}")
    st.stop()


# ═══════════════════════════════════════════════════════════════════════════
# Section 1: Generate or load checklist
# ═══════════════════════════════════════════════════════════════════════════

tab_generate, tab_load = st.tabs(["Generate New", "Load Existing"])

checklist = None

with tab_generate:
    st.subheader("Generate Checklist from Work Package")
    with st.form("generate_form"):
        wp_id = st.text_input("Work Package ID")
        wp_name = st.text_input("Work Package Name")
        wp_code = st.text_input("Work Package Code")
        constraint = st.selectbox("Constraint", ["ONLINE", "OFFLINE"])
        equip_name = st.text_input("Equipment Name")
        equip_tag = st.text_input("Equipment TAG")
        submitted = st.form_submit_button("Generate Checklist")

    if submitted and wp_id:
        try:
            work_package = {
                "work_package_id": wp_id,
                "name": wp_name,
                "code": wp_code,
                "constraint": constraint,
                "allocated_tasks": [],
            }
            result = api_client.generate_execution_checklist(
                work_package=work_package,
                tasks=[],
                equipment_name=equip_name,
                equipment_tag=equip_tag,
            )
            st.session_state["current_checklist"] = result
            st.success(f"Checklist generated: {result['checklist_id']}")
        except Exception as exc:
            st.error(f"Error: {exc}")

with tab_load:
    st.subheader("Load Existing Checklist")
    col1, col2 = st.columns(2)
    filter_wp = col1.text_input("Filter by Work Package ID", key="filter_wp")
    filter_status = col2.selectbox(
        "Filter by Status",
        ["", "DRAFT", "IN_PROGRESS", "COMPLETED", "CLOSED"],
        key="filter_status",
    )
    if st.button("Search"):
        try:
            results = api_client.list_execution_checklists(
                work_package_id=filter_wp or None,
                status=filter_status or None,
            )
            if results:
                for cl in results:
                    col_a, col_b, col_c = st.columns([3, 1, 1])
                    col_a.write(f"**{cl['work_package_name']}** ({cl['equipment_tag']})")
                    col_b.write(cl["status"])
                    if col_c.button("Open", key=f"open_{cl['checklist_id']}"):
                        loaded = api_client.get_execution_checklist(cl["checklist_id"])
                        st.session_state["current_checklist"] = loaded
                        st.rerun()
            else:
                st.info("No checklists found.")
        except Exception as exc:
            st.error(f"Error: {exc}")

    checklist_id_input = st.text_input("Or enter Checklist ID directly")
    if st.button("Load by ID") and checklist_id_input:
        try:
            loaded = api_client.get_execution_checklist(checklist_id_input)
            st.session_state["current_checklist"] = loaded
            st.success("Loaded")
        except Exception as exc:
            st.error(f"Error: {exc}")


# ═══════════════════════════════════════════════════════════════════════════
# Section 2: Checklist display
# ═══════════════════════════════════════════════════════════════════════════

checklist = st.session_state.get("current_checklist")
if not checklist:
    st.info("Generate or load a checklist above to begin execution.")
    st.stop()

st.divider()

# Header
col1, col2, col3 = st.columns([3, 1, 1])
col1.subheader(f"{checklist.get('work_package_name', '')} — {checklist.get('equipment_tag', '')}")
col2.metric("Status", checklist.get("status", ""))

steps = checklist.get("steps", [])
total = len(steps)
completed = sum(1 for s in steps if s.get("status") in ("COMPLETED", "SKIPPED"))
pct = round(completed / total * 100) if total else 0
col3.metric("Progress", f"{completed}/{total}")

st.progress(pct / 100)

# Safety section
safety = checklist.get("safety_section", [])
if safety:
    with st.expander("Safety Requirements", expanded=False):
        for item in safety:
            st.markdown(f"- {item}")

# Pre-task notes
pre_notes = checklist.get("pre_task_notes", "")
if pre_notes:
    with st.expander("Pre-Task Notes", expanded=False):
        st.write(pre_notes)


# ═══════════════════════════════════════════════════════════════════════════
# Section 3: Interactive steps
# ═══════════════════════════════════════════════════════════════════════════

st.divider()
st.subheader("Execution Steps")

# Build predecessor completion map
step_status_map = {s.get("step_id", ""): s.get("status", "PENDING") for s in steps}

for i, step in enumerate(steps):
    step_id = step.get("step_id", "")
    step_num = step.get("step_number", "")
    step_type = step.get("step_type", "TASK_OPERATION")
    description = step.get("description", "")
    status = step.get("status", "PENDING")
    is_gate = step.get("is_gate", False)
    gate_question = step.get("gate_question", "")
    predecessors = step.get("predecessor_step_ids", [])

    # Check if predecessors are done
    preds_done = all(
        step_status_map.get(pid, "PENDING") in ("COMPLETED", "SKIPPED")
        for pid in predecessors
    )
    can_act = status == "PENDING" and preds_done

    icon = _status_icon(status)
    badge = _type_badge(step_type)

    with st.expander(
        f"{icon} {step_num} — {description}",
        expanded=(can_act and status == "PENDING"),
    ):
        st.markdown(badge, unsafe_allow_html=True)

        # Show materials if any
        materials = step.get("materials", [])
        if materials:
            st.caption(f"Materials: {', '.join(materials)}")

        trade = step.get("trade", "")
        if trade:
            st.caption(f"Trade: {trade}")

        limits = step.get("acceptable_limits")
        if limits:
            st.info(f"Acceptable limits: {limits}")

        # Status-specific UI
        if status == "COMPLETED":
            obs = step.get("observation")
            if obs:
                cc = obs.get("condition_code", 1)
                st.success(f"Condition: {CONDITION_CODES.get(cc, cc)}")
                notes = obs.get("notes", "")
                if notes:
                    st.caption(f"Notes: {notes}")
            st.caption(f"Completed by: {step.get('completed_by', '')} at {step.get('completed_at', '')}")

        elif status == "SKIPPED":
            obs = step.get("observation")
            if obs:
                st.warning(f"Skipped: {obs.get('notes', '')}")

        elif can_act:
            # Gate question
            if is_gate and gate_question:
                st.warning(f"**GATE:** {gate_question}")

            # Completion form
            with st.form(f"step_form_{step_id}"):
                cc = st.radio(
                    "Condition Code",
                    options=[1, 2, 3],
                    format_func=lambda x: CONDITION_CODES[x],
                    key=f"cc_{step_id}",
                )
                measured = st.text_input("Measured Value", key=f"meas_{step_id}")
                notes = st.text_area("Notes / Observations", key=f"notes_{step_id}")
                completed_by = st.text_input("Completed By", key=f"by_{step_id}")

                col_complete, col_skip = st.columns(2)
                do_complete = col_complete.form_submit_button("Complete Step")
                do_skip = col_skip.form_submit_button(
                    "Skip Step" if not is_gate else "Skip (N/A for gates)",
                    disabled=is_gate,
                )

            if do_complete:
                try:
                    observation = {
                        "condition_code": cc,
                        "notes": notes,
                    }
                    if measured:
                        observation["measured_value"] = measured
                    result = api_client.complete_checklist_step(
                        checklist["checklist_id"],
                        step_id,
                        observation=observation,
                        completed_by=completed_by,
                    )
                    st.session_state["current_checklist"] = result
                    st.toast("Step completed", icon="✅")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Error: {exc}")

            if do_skip and not is_gate:
                try:
                    result = api_client.skip_checklist_step(
                        checklist["checklist_id"],
                        step_id,
                        reason=notes,
                        authorized_by=completed_by,
                    )
                    st.session_state["current_checklist"] = result
                    st.toast("Step skipped", icon="⏩")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Error: {exc}")

        else:
            if not preds_done:
                st.caption("Waiting for predecessor steps to complete...")


# ═══════════════════════════════════════════════════════════════════════════
# Section 4: Closure
# ═══════════════════════════════════════════════════════════════════════════

if checklist.get("status") == "COMPLETED":
    st.divider()
    st.subheader("Supervisor Closure")

    closure = checklist.get("closure_summary")
    if closure:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Completed", closure.get("completed_steps", 0))
        c2.metric("Skipped", closure.get("skipped_steps", 0))
        c3.metric("Defects", closure.get("defects_raised", 0))
        c4.metric("Completion", f"{closure.get('completion_pct', 0)}%")

        cond = closure.get("condition_distribution", {})
        if cond:
            st.write("**Condition Distribution:**")
            for code, count in cond.items():
                st.write(f"- {code}: {count}")

    with st.form("close_form"):
        supervisor = st.text_input("Supervisor Name")
        supervisor_notes = st.text_area("Supervisor Notes")
        close_btn = st.form_submit_button("Close Checklist")

    if close_btn and supervisor:
        try:
            result = api_client.close_execution_checklist(
                checklist["checklist_id"],
                supervisor=supervisor,
                supervisor_notes=supervisor_notes,
            )
            st.session_state["current_checklist"] = result
            st.toast("Checklist closed", icon="🔒")
            st.rerun()
        except Exception as exc:
            st.error(f"Error: {exc}")

elif checklist.get("status") == "CLOSED":
    st.divider()
    st.success(
        f"Checklist closed by {checklist.get('supervisor', '')} "
        f"at {checklist.get('closed_at', '')}"
    )

# Post-task notes
post_notes = checklist.get("post_task_notes", "")
if post_notes:
    with st.expander("Post-Task Notes", expanded=False):
        st.write(post_notes)
