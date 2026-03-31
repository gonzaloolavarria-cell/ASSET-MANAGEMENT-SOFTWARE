"""Page 9: Work Request Queue — M1-M2 Review and Validation."""

import streamlit as st
from streamlit_app import api_client
from streamlit_app.i18n import page_init, t
from streamlit_app.style import apply_style
from streamlit_app.components.feedback import feedback_widget
from streamlit_app.components.role_banner import role_context_banner

st.set_page_config(page_title="Work Requests", page_icon="📋", layout="wide")
page_init()
apply_style()
role_context_banner(9)

st.title(t("work_requests.title"))
st.markdown(t("work_requests.subtitle"))

# Filters
col_f1, col_f2 = st.columns([1, 3])
with col_f1:
    status_filter = st.selectbox(t("work_requests.filter_by_status"), [None, "DRAFT", "PENDING_VALIDATION", "VALIDATED", "REJECTED"])

try:
    work_requests = api_client.list_work_requests(status=status_filter)
except Exception as e:
    st.error(t("work_requests.could_not_load", error=str(e)))
    work_requests = []

if not work_requests:
    st.info(t("work_requests.no_requests"))
    st.stop()

st.subheader(t("work_requests.count_title", count=len(work_requests)))

for wr in work_requests:
    status = wr.get("status", "UNKNOWN")
    badge_color = {"DRAFT": "blue", "PENDING_VALIDATION": "orange", "VALIDATED": "green", "REJECTED": "red"}.get(status, "gray")

    with st.expander(f"**{wr['request_id'][:12]}...** | {wr.get('equipment_tag', 'N/A')} | :{badge_color}[{status}]"):
        col1, col2, col3 = st.columns(3)
        col1.metric(t("work_requests.equipment"), wr.get("equipment_tag", "N/A"))
        col2.metric(t("work_requests.confidence"), f"{wr.get('equipment_confidence', 0):.0%}")

        ai = wr.get("ai_classification") or {}
        col3.metric(t("work_requests.ai_priority"), ai.get("priority_suggested", "N/A"))

        if ai:
            st.markdown(f"**WO Type:** {ai.get('work_order_type', 'N/A')} | **Duration:** {ai.get('estimated_duration_hours', 'N/A')}h | **Specialties:** {', '.join(ai.get('required_specialties', []))}")

        st.markdown(f"**Created:** {wr.get('created_at', 'N/A')}")

        if status in ("DRAFT", "PENDING_VALIDATION"):
            col_a, col_b, col_c = st.columns(3)
            wr_id = wr["request_id"]
            if col_a.button(t("common.approve"), key=f"approve_{wr_id}"):
                try:
                    result = api_client.validate_work_request(wr_id, "APPROVE")
                    st.success(t("work_requests.approved_msg", id=wr_id[:8]))
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
            if col_b.button(t("common.reject"), key=f"reject_{wr_id}"):
                try:
                    api_client.validate_work_request(wr_id, "REJECT")
                    st.warning(t("work_requests.rejected_msg", id=wr_id[:8]))
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
            if col_c.button(t("work_requests.classify"), key=f"classify_{wr_id}"):
                try:
                    api_client.classify_work_request(wr_id)
                    st.info(t("work_requests.reclassify_triggered"))
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

feedback_widget("work_requests")
