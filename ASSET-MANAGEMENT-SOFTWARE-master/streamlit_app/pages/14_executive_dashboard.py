"""Page 14: Executive Dashboard — Consolidated KPI view with traffic lights.

Role-aware: Filters KPIs and tabs based on the user's selected role (GAP-W05).
"""

import streamlit as st
from streamlit_app import api_client
from streamlit_app.components.charts import (
    traffic_light_grid, kpi_trend_chart, notification_summary_chart,
    correlation_scatter, bad_actor_overlap_chart,
)
from streamlit_app.i18n import page_init, t
from streamlit_app.style import apply_style
from streamlit_app.components.feedback import feedback_widget
from streamlit_app.components.role_banner import role_context_banner
from streamlit_app.role_config import (
    UserRole, get_role_kpis, ROLE_DISPLAY_NAMES, ROLE_ICONS, DEFAULT_ROLE,
)

st.set_page_config(page_title="Executive Dashboard", layout="wide")
page_init()
apply_style()
role_context_banner(14)

role = st.session_state.get("user_role", DEFAULT_ROLE)
role_name = t(ROLE_DISPLAY_NAMES[role])
role_icon = ROLE_ICONS.get(role, "")

st.title(f"{t('dashboard.title')} — {role_icon} {role_name}")

plant_id = st.text_input(t("common.plant_id"), value="OCP-JFC")

# --- Role-specific KPI summary at top ---
role_kpis = get_role_kpis(role)
if role_kpis:
    kpi_cols = st.columns(min(len(role_kpis), 5))
    for i, kpi in enumerate(role_kpis):
        with kpi_cols[i % min(len(role_kpis), 5)]:
            kpi_label = t(kpi["i18n_key"])
            target = kpi["target"]
            target_str = f"Target: {target}{kpi['unit']}" if target is not None else ""
            st.metric(kpi_label, "—", help=target_str)

st.divider()

# --- Tabs: show all but highlight role-relevant content ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    t("dashboard.tab_kpi"), t("dashboard.tab_health"), t("dashboard.tab_trends"),
    t("dashboard.tab_notifications"), t("dashboard.tab_cross_module"),
    t("dashboard.tab_financial"),
])

with tab1:
    st.subheader(t("dashboard.kpi_traffic_light"))
    st.info(t("dashboard.generate_report_first"))
    try:
        summary = api_client.get_kpi_summary(plant_id)
        if summary.get("has_data") and summary.get("report"):
            report = summary["report"]
            lights = report.get("traffic_lights", {})
            if lights:
                # Filter to role-relevant KPIs if available
                role_kpi_keys = {k["key"] for k in role_kpis}
                filtered_lights = {
                    name: color for name, color in lights.items()
                    if name in role_kpi_keys
                } if role_kpi_keys else lights
                # Fall back to all lights if no role-specific match
                display_lights = filtered_lights if filtered_lights else lights
                kpi_data = [
                    {"name": name, "traffic_light": color, "value": 0}
                    for name, color in display_lights.items()
                ]
                st.plotly_chart(traffic_light_grid(kpi_data), width="stretch")
            else:
                st.info(t("dashboard.no_traffic_light"))
        else:
            st.info(t("dashboard.no_monthly_reports"))
    except Exception:
        st.warning(t("common.could_not_connect"))

with tab2:
    st.subheader(t("dashboard.health_risk"))
    try:
        dashboard = api_client.get_executive_dashboard(plant_id)
        col1, col2, col3 = st.columns(3)
        col1.metric(t("dashboard.total_reports"), dashboard.get("total_reports", 0))
        col2.metric(t("dashboard.total_notifications"), dashboard.get("total_notifications", 0))
        col3.metric(t("dashboard.critical_alerts"), dashboard.get("critical_alerts", 0))
    except Exception:
        st.warning(t("common.could_not_connect"))

with tab3:
    st.subheader(t("dashboard.kpi_trends"))
    st.info(t("dashboard.select_kpi"))
    # Role-filtered KPI options for trend selection
    role_kpi_keys = [k["key"] for k in role_kpis] if role_kpis else [
        "wo_completion", "schedule_adherence", "pm_compliance",
        "reactive_pct", "backlog_weeks",
    ]
    kpi_name = st.selectbox(t("dashboard.kpi"), role_kpi_keys)
    # Placeholder — trends require historical data
    periods = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    values = [85, 87, 90, 88, 92, 91]
    targets = [90] * 6
    st.plotly_chart(kpi_trend_chart(periods, values, targets, f"{kpi_name} Trend"),
                    width="stretch")

with tab4:
    st.subheader(t("dashboard.active_notifications"))
    try:
        alerts = api_client.get_dashboard_alerts(plant_id)
        st.metric(t("dashboard.active_alerts"), alerts.get("total_active", 0))
        notifications = alerts.get("alerts", [])
        if notifications:
            st.plotly_chart(notification_summary_chart(notifications), width="stretch")
            for n in notifications[:10]:
                level_icon = {"CRITICAL": "🔴", "WARNING": "🟡"}.get(n.get("level"), "🔵")
                st.write(f"{level_icon} **{n.get('title')}** — {n.get('message', '')}")
        else:
            st.success(t("dashboard.no_alerts"))
    except Exception:
        st.warning(t("common.could_not_connect"))

with tab5:
    st.subheader(t("dashboard.cross_module"))
    st.info(t("dashboard.cross_module_info"))
    if st.button(t("dashboard.run_demo")):
        try:
            result = api_client.run_cross_module_analysis(plant_id, {
                "equipment_criticality": [
                    {"equipment_id": "EQ-1", "criticality": "AA"},
                    {"equipment_id": "EQ-2", "criticality": "B"},
                ],
                "failure_records": [
                    {"equipment_id": "EQ-1"}, {"equipment_id": "EQ-1"},
                    {"equipment_id": "EQ-2"},
                ],
            })
            st.json(result)
        except Exception as e:
            st.error(f"Analysis failed: {e}")

with tab6:
    st.subheader(t("dashboard.financial_overview"))
    try:
        fin = api_client.get_financial_summary(plant_id)
        c1, c2, c3 = st.columns(3)
        c1.metric(t("financial.total_budget"), f"${fin.get('total_maintenance_budget', 0):,.0f}")
        c2.metric(t("financial.avoided_cost"), f"${fin.get('total_avoided_cost', 0):,.0f}")
        c3.metric(t("financial.man_hours_metric"), f"{fin.get('total_man_hours_saved', 0):,.0f}")
        recs = fin.get("recommendations", [])
        if recs:
            for r in recs[:3]:
                st.write(f"- {r}")
    except Exception:
        st.info(t("dashboard.financial_no_data"))

feedback_widget("executive_dashboard")
