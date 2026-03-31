"""Page 7: Overview — Executive summary, stats, audit log."""

import streamlit as st
from streamlit_app import api_client
from streamlit_app.i18n import page_init, t
from streamlit_app.style import apply_style
from streamlit_app.components.feedback import feedback_widget
from streamlit_app.components.tables import render_data_table, metric_row
from streamlit_app.components.charts import node_distribution_pie
from streamlit_app.components.role_banner import role_context_banner

st.set_page_config(page_title="Overview", layout="wide")
page_init()
apply_style()
role_context_banner(7)

st.title(t("overview.title"))

# Stats
try:
    stats = api_client.get_stats()
    col1, col2, col3 = st.columns(3)
    col1.metric(t("overview.plants"), stats.get("plants", 0))
    col2.metric(t("overview.total_nodes"), stats.get("total_nodes", 0))
    node_counts = stats.get("hierarchy_nodes", {})
    col3.metric(t("overview.equipment_items"), node_counts.get("EQUIPMENT", 0))

    if node_counts:
        st.plotly_chart(node_distribution_pie(node_counts, "Hierarchy Distribution"), width="stretch")
except Exception:
    st.warning(t("common.cannot_connect_start"))

# Agent status
st.subheader(t("overview.agent_status"))
try:
    agent_status = api_client.get_agent_status()
    if agent_status.get("api_key_configured"):
        st.success(t("overview.api_key_configured"))
        st.write(t("overview.agents_available"), ", ".join(agent_status.get("agents_available", [])))
    else:
        st.info(t("overview.no_api_key"))
except Exception:
    pass

# Database management
st.subheader(t("overview.db_management"))
col1, col2 = st.columns(2)
with col1:
    if st.button(t("overview.seed_database")):
        with st.spinner(t("overview.seeding")):
            try:
                result = api_client.seed_database()
                st.success(f"Database seeded: {result}")
            except Exception as e:
                st.error(f"Seed failed: {e}")

# Audit log
st.subheader(t("overview.audit_log"))
try:
    entity_filter = st.selectbox(t("overview.filter_entity"), ["ALL", "plant", "hierarchy_node", "criticality_assessment", "failure_mode", "maintenance_task", "work_package", "sap_upload", "system"])
    ef = None if entity_filter == "ALL" else entity_filter
    log = api_client.get_audit_log(entity_type=ef, limit=20)
    render_data_table(log, key_columns=["id", "entity_type", "entity_id", "action", "user", "timestamp"])
except Exception:
    pass

feedback_widget("overview")
