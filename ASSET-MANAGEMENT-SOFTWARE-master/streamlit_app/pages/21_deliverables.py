"""Page 21: Deliverable Tracking — GAP-W10.

4-tab interface for consultant workflow and client review:
- Tab 1: Overview — project summary metrics, milestone progress, status distribution
- Tab 2: Deliverable Detail — table, status transitions, notes
- Tab 3: Time Tracking — log hours, history, variance analysis
- Tab 4: Client Review — approve/reject submitted deliverables
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Deliverable Tracking", page_icon="📦", layout="wide")

try:
    from streamlit_app.i18n import page_init, t as _t
    page_init()
except Exception:
    _t = lambda k, **kw: k  # noqa: E731

try:
    from streamlit_app.components.role_banner import role_context_banner
    role_context_banner(21)
except Exception:
    pass

try:
    from streamlit_app import api_client
    from streamlit_app.role_config import UserRole
    _BACKEND_OK = True
except ImportError as exc:
    _BACKEND_OK = False
    _IMPORT_ERROR = str(exc)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STATUS_COLORS = {
    "DRAFT": "#9E9E9E",
    "IN_PROGRESS": "#2196F3",
    "SUBMITTED": "#FF9800",
    "UNDER_REVIEW": "#9C27B0",
    "APPROVED": "#4CAF50",
    "REJECTED": "#F44336",
}

STATUS_ICONS = {
    "DRAFT": "\u270F\uFE0F",
    "IN_PROGRESS": "\u25B6\uFE0F",
    "SUBMITTED": "\U0001F4E4",
    "UNDER_REVIEW": "\U0001F50D",
    "APPROVED": "\u2705",
    "REJECTED": "\u274C",
}

ACTIVITY_TYPES = ["analysis", "review", "rework", "meeting", "documentation"]

# Map status to the next valid transition + button label i18n key
TRANSITION_ACTIONS = {
    "DRAFT": ("IN_PROGRESS", "deliverables.start_work"),
    "IN_PROGRESS": ("SUBMITTED", "deliverables.submit_for_review"),
    "SUBMITTED": ("UNDER_REVIEW", "deliverables.begin_review"),
}


def _status_badge(status: str) -> str:
    color = STATUS_COLORS.get(status, "#9E9E9E")
    icon = STATUS_ICONS.get(status, "")
    return (
        f'<span style="background-color:{color};color:white;'
        f'padding:2px 10px;border-radius:4px;font-size:0.85em;">'
        f'{icon} {status}</span>'
    )


def _t_status(status: str) -> str:
    key = f"deliverables.status_{status.lower()}"
    val = _t(key)
    return val if val != key else status


def _variance_indicator(est: float, act: float) -> str:
    if est <= 0:
        return ""
    pct = (act - est) / est * 100
    if pct <= 0:
        return f":green[{pct:+.0f}%]"
    elif pct <= 10:
        return f":orange[{pct:+.0f}%]"
    else:
        return f":red[{pct:+.0f}%]"


# ═══════════════════════════════════════════════════════════════════════════
# Page header
# ═══════════════════════════════════════════════════════════════════════════

st.title(_t("deliverables.title"))

if not _BACKEND_OK:
    st.error(f"Backend modules unavailable: {_IMPORT_ERROR}")
    st.stop()


# ═══════════════════════════════════════════════════════════════════════════
# Sidebar — Project context + Seed
# ═══════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.subheader(_t("deliverables.project_summary"))
    client_slug = st.text_input("Client slug", value="ocp").strip().lower()
    project_slug = st.text_input(
        "Project slug", value="jfc-maintenance-strategy"
    ).strip().lower()

    st.divider()
    st.subheader(_t("deliverables.seed_from_plan"))
    uploaded = st.file_uploader(
        "Upload execution-plan.yaml", type=["yaml", "yml"], key="seed_upload"
    )
    if uploaded is not None and st.button(_t("deliverables.seed_from_plan"), key="btn_seed"):
        try:
            import yaml
            plan_dict = yaml.safe_load(uploaded.getvalue().decode("utf-8"))
            result = api_client.seed_deliverables(plan_dict, client_slug, project_slug)
            if result:
                st.success(f"Created {result.get('created', 0)} deliverables")
                st.rerun()
            else:
                st.error("Seed failed")
        except Exception as exc:
            st.error(f"Error: {exc}")


# ═══════════════════════════════════════════════════════════════════════════
# Load data
# ═══════════════════════════════════════════════════════════════════════════

deliverables = api_client.list_deliverables(
    client_slug=client_slug, project_slug=project_slug
) or []

user_role = st.session_state.get("user_role", UserRole.CONSULTANT)

if not deliverables:
    st.info(_t("deliverables.no_deliverables"))
    st.stop()


# ═══════════════════════════════════════════════════════════════════════════
# Tabs
# ═══════════════════════════════════════════════════════════════════════════

tab_overview, tab_detail, tab_time, tab_review = st.tabs([
    _t("deliverables.overview"),
    _t("deliverables.detail"),
    _t("deliverables.time_tracking"),
    _t("deliverables.client_review"),
])


# ───────────────────────────────────────────────────────────────────────────
# Tab 1: Overview
# ───────────────────────────────────────────────────────────────────────────

with tab_overview:
    # Summary metrics
    summary = api_client.get_deliverable_summary(client_slug, project_slug)
    if not summary:
        summary = {
            "total_deliverables": len(deliverables),
            "overall_completion_pct": 0,
            "total_estimated_hours": 0,
            "total_actual_hours": 0,
            "variance_hours": 0,
            "variance_pct": 0,
            "by_status": {},
            "by_milestone": {},
        }

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(_t("deliverables.total_deliverables"), summary["total_deliverables"])
    c2.metric(_t("deliverables.completion"), f"{summary['overall_completion_pct']}%")
    c3.metric(
        _t("deliverables.hours_estimated"),
        f"{summary['total_estimated_hours']:.1f}h",
    )

    var_pct = summary.get("variance_pct", 0)
    var_label = _t("deliverables.on_track") if var_pct <= 10 else _t("deliverables.over_budget")
    c4.metric(
        _t("deliverables.hours_variance"),
        f"{summary['total_actual_hours']:.1f}h",
        delta=f"{summary['variance_hours']:+.1f}h ({var_pct:+.1f}%)",
        delta_color="inverse",
    )

    st.progress(min(summary["overall_completion_pct"] / 100, 1.0))

    # Per-milestone progress
    st.divider()
    st.subheader(_t("deliverables.progress_by_milestone"))

    by_milestone = summary.get("by_milestone", {})
    if by_milestone:
        milestone_cols = st.columns(min(len(by_milestone), 4))
        for idx, (m_num, count) in enumerate(sorted(by_milestone.items(), key=lambda x: str(x[0]))):
            m_deliverables = [d for d in deliverables if d.get("milestone") == int(m_num)]
            approved = sum(1 for d in m_deliverables if d.get("status") == "APPROVED")
            pct = round(approved / count * 100) if count else 0
            col = milestone_cols[idx % len(milestone_cols)]
            col.metric(_t("deliverables.milestone_n", num=m_num), f"{approved}/{count}")
            col.progress(pct / 100)

    # Status distribution
    st.divider()
    st.subheader(_t("deliverables.status"))
    by_status = summary.get("by_status", {})
    if by_status:
        for status_name, count in by_status.items():
            pct = round(count / summary["total_deliverables"] * 100) if summary["total_deliverables"] else 0
            badge = _status_badge(status_name)
            st.markdown(
                f"{badge} &nbsp; **{count}** ({pct}%)",
                unsafe_allow_html=True,
            )


# ───────────────────────────────────────────────────────────────────────────
# Tab 2: Deliverable Detail
# ───────────────────────────────────────────────────────────────────────────

with tab_detail:
    # Filters
    fc1, fc2 = st.columns(2)
    filter_milestone = fc1.selectbox(
        _t("deliverables.milestone"),
        [None, 1, 2, 3, 4],
        format_func=lambda x: "All" if x is None else f"M{x}",
        key="filter_milestone",
    )
    filter_status = fc2.selectbox(
        _t("deliverables.status"),
        [None, "DRAFT", "IN_PROGRESS", "SUBMITTED", "UNDER_REVIEW", "APPROVED", "REJECTED"],
        format_func=lambda x: "All" if x is None else _t_status(x),
        key="filter_status",
    )

    filtered = deliverables
    if filter_milestone:
        filtered = [d for d in filtered if d.get("milestone") == filter_milestone]
    if filter_status:
        filtered = [d for d in filtered if d.get("status") == filter_status]

    if not filtered:
        st.info(_t("deliverables.no_deliverables"))
    else:
        for d in filtered:
            d_id = d["deliverable_id"]
            status = d.get("status", "DRAFT")
            est = d.get("estimated_hours", 0)
            act = d.get("actual_hours", 0)
            badge = _status_badge(status)
            var = _variance_indicator(est, act)

            with st.expander(
                f"M{d.get('milestone', '?')} | {d['name']} — {_t_status(status)}",
                expanded=False,
            ):
                st.markdown(badge, unsafe_allow_html=True)

                mc1, mc2, mc3, mc4 = st.columns(4)
                mc1.metric(_t("deliverables.category"), d.get("category", ""))
                mc2.metric(_t("deliverables.hours_estimated"), f"{est:.1f}h")
                mc3.metric(_t("deliverables.hours_actual"), f"{act:.1f}h")
                mc4.markdown(f"**{_t('deliverables.hours_variance')}:** {var}")

                # Artifacts
                artifacts = d.get("artifact_paths") or []
                if artifacts:
                    st.markdown(f"**{_t('deliverables.artifacts')}:** {', '.join(artifacts)}")

                # Quality score
                qs = d.get("quality_score_id")
                if qs:
                    st.markdown(f"**{_t('deliverables.quality_score')}:** `{qs}`")

                # Notes
                notes = d.get("consultant_notes", "")
                if user_role == UserRole.CONSULTANT:
                    new_notes = st.text_area(
                        _t("deliverables.consultant_notes"),
                        value=notes,
                        key=f"notes_{d_id}",
                    )
                    if new_notes != notes:
                        if st.button("Save Notes", key=f"save_notes_{d_id}"):
                            api_client.update_deliverable(d_id, {"consultant_notes": new_notes})
                            st.toast("Notes saved")
                            st.rerun()
                elif notes:
                    st.markdown(f"**{_t('deliverables.consultant_notes')}:** {notes}")

                # Client feedback
                fb = d.get("client_feedback", "")
                if fb:
                    st.markdown(f"**{_t('deliverables.client_feedback')}:** {fb}")

                # Status transition button (consultant only)
                if user_role == UserRole.CONSULTANT and status in TRANSITION_ACTIONS:
                    target, label_key = TRANSITION_ACTIONS[status]
                    if st.button(_t(label_key), key=f"trans_{d_id}"):
                        result = api_client.transition_deliverable(d_id, target)
                        if result:
                            st.toast(f"Status: {target}")
                            st.rerun()
                        else:
                            st.error("Transition failed")


# ───────────────────────────────────────────────────────────────────────────
# Tab 3: Time Tracking
# ───────────────────────────────────────────────────────────────────────────

with tab_time:
    if user_role not in (UserRole.CONSULTANT, UserRole.MANAGER):
        st.info("Time tracking is available for Consultant and Manager roles.")
    else:
        st.subheader(_t("deliverables.log_time"))

        tc1, tc2 = st.columns(2)
        selected_del = tc1.selectbox(
            _t("deliverables.select_deliverable"),
            deliverables,
            format_func=lambda d: f"M{d.get('milestone', '?')} | {d['name']}",
            key="time_deliverable",
        )
        activity = tc2.selectbox(
            _t("deliverables.activity_type"),
            ACTIVITY_TYPES,
            format_func=lambda a: _t(f"deliverables.activity_{a}"),
            key="time_activity",
        )

        hc1, hc2 = st.columns(2)
        hours = hc1.number_input(
            _t("deliverables.hours"), min_value=0.25, max_value=24.0,
            value=1.0, step=0.25, key="time_hours",
        )
        description = hc2.text_input(
            _t("deliverables.description"), key="time_desc",
        )

        if st.button(_t("deliverables.log_time"), key="btn_log_time"):
            if selected_del:
                result = api_client.log_time(selected_del["deliverable_id"], {
                    "hours": hours,
                    "activity_type": activity,
                    "description": description,
                })
                if result:
                    st.success(f"Logged {hours}h")
                    st.rerun()
                else:
                    st.error("Failed to log time")

        # Time log history
        st.divider()
        st.subheader(_t("deliverables.time_log_history"))

        for d in deliverables:
            est = d.get("estimated_hours", 0)
            act = d.get("actual_hours", 0)
            if act > 0 or est > 0:
                var = _variance_indicator(est, act)
                with st.expander(
                    f"{d['name']} — {act:.1f}h / {est:.1f}h {var}",
                    expanded=False,
                ):
                    logs = api_client.list_time_logs(d["deliverable_id"])
                    if logs:
                        for log in logs:
                            st.markdown(
                                f"- **{log.get('hours', 0):.2f}h** "
                                f"({log.get('activity_type', 'analysis')}) "
                                f"— {log.get('description', '')} "
                                f"*{log.get('logged_by', '')}* "
                                f"{log.get('logged_at', '')}"
                            )
                    else:
                        st.caption("No time logged yet")


# ───────────────────────────────────────────────────────────────────────────
# Tab 4: Client Review
# ───────────────────────────────────────────────────────────────────────────

with tab_review:
    if user_role not in (UserRole.CONSULTANT, UserRole.MANAGER):
        st.info("Client review is available for Consultant and Manager roles.")
    else:
        reviewable = [
            d for d in deliverables
            if d.get("status") in ("SUBMITTED", "UNDER_REVIEW")
        ]

        if not reviewable:
            st.info("No deliverables pending review.")
        else:
            for d in reviewable:
                d_id = d["deliverable_id"]
                status = d.get("status", "")
                badge = _status_badge(status)

                st.markdown(f"### {d['name']}")
                st.markdown(badge, unsafe_allow_html=True)

                rc1, rc2, rc3 = st.columns(3)
                rc1.metric(_t("deliverables.category"), d.get("category", ""))
                rc2.metric(_t("deliverables.milestone"), f"M{d.get('milestone', '?')}")
                rc3.metric(
                    _t("deliverables.hours_actual"),
                    f"{d.get('actual_hours', 0):.1f}h / {d.get('estimated_hours', 0):.1f}h",
                )

                # Artifacts
                artifacts = d.get("artifact_paths") or []
                if artifacts:
                    st.markdown(f"**{_t('deliverables.artifacts')}:** {', '.join(artifacts)}")

                # Quality score
                qs = d.get("quality_score_id")
                if qs:
                    st.markdown(f"**{_t('deliverables.quality_score')}:** `{qs}`")

                # Notes
                notes = d.get("consultant_notes", "")
                if notes:
                    st.markdown(f"**{_t('deliverables.consultant_notes')}:** {notes}")

                # If SUBMITTED, transition to UNDER_REVIEW first
                if status == "SUBMITTED":
                    if st.button(_t("deliverables.begin_review"), key=f"review_{d_id}"):
                        api_client.transition_deliverable(d_id, "UNDER_REVIEW")
                        st.rerun()

                # If UNDER_REVIEW, show approve/reject
                if status == "UNDER_REVIEW":
                    feedback = st.text_area(
                        _t("deliverables.feedback"), key=f"fb_{d_id}",
                    )
                    bc1, bc2 = st.columns(2)
                    if bc1.button(
                        _t("deliverables.approve_deliverable"),
                        key=f"approve_{d_id}",
                        type="primary",
                    ):
                        api_client.transition_deliverable(d_id, "APPROVED", feedback)
                        st.toast("Approved")
                        st.rerun()
                    if bc2.button(
                        _t("deliverables.reject_deliverable"),
                        key=f"reject_{d_id}",
                    ):
                        api_client.transition_deliverable(d_id, "REJECTED", feedback)
                        st.toast("Rejected — sent back for rework")
                        st.rerun()

                st.divider()
