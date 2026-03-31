"""Page 2: Criticality Assessment."""

import streamlit as st
from streamlit_app import api_client
from streamlit_app.i18n import page_init, t
from streamlit_app.style import apply_style
from streamlit_app.components.feedback import feedback_widget
from streamlit_app.components.forms import criticality_matrix_form
from streamlit_app.components.role_banner import role_context_banner

st.set_page_config(page_title="Criticality", layout="wide")
page_init()
apply_style()
role_context_banner(2)

st.title(t("criticality.title"))

try:
    nodes = api_client.list_nodes(node_type="EQUIPMENT")
except Exception:
    st.warning(t("common.cannot_connect_start"))
    st.stop()

if not nodes:
    st.info(t("criticality.no_equipment"))
    st.stop()

# Equipment selector
eq_names = {n["node_id"]: f"{n['name']} ({n['code']})" for n in nodes}
selected_eq = st.selectbox(t("common.select_equipment"), list(eq_names.keys()), format_func=lambda x: eq_names[x])

# Existing assessment
col1, col2 = st.columns(2)
with col1:
    st.subheader(t("criticality.current_assessment"))
    try:
        assessment = api_client.get_criticality(selected_eq)
        st.metric(t("criticality.risk_class"), assessment["risk_class"])
        st.metric(t("criticality.overall_score"), f"{assessment['overall_score']:.1f}")
        st.write(f"**Status:** {assessment['status']}")
        if assessment["status"] == "DRAFT":
            if st.button(t("criticality.approve_assessment")):
                result = api_client.approve_criticality(assessment["assessment_id"])
                st.success(t("criticality.approved", result=result))
                st.rerun()
    except Exception:
        st.info(t("criticality.no_assessment"))

# New assessment form
with col2:
    st.subheader(t("criticality.new_assessment"))
    scores, probability = criticality_matrix_form()
    if st.button(t("criticality.run_assessment")):
        result = api_client.assess_criticality({
            "node_id": selected_eq,
            "criteria_scores": scores,
            "probability": probability,
        })
        st.success(t("criticality.risk_result", risk_class=result['risk_class'], score=f"{result['overall_score']:.1f}"))
        if result.get("warnings"):
            for w in result["warnings"]:
                st.warning(w)

feedback_widget("criticality")
