"""Page 24: Financial Dashboard — Budget tracking, ROI, cost drivers, man-hours (GAP-W04).

5 tabs: Budget Tracking, ROI Calculator, Cost Drivers, Man-Hours Savings, Financial Summary.
"""

import streamlit as st
from streamlit_app import api_client
from streamlit_app.components.charts import (
    budget_variance_chart, roi_cumulative_chart,
    cost_driver_pareto_chart, man_hours_comparison_chart,
)
from streamlit_app.i18n import page_init, t
from streamlit_app.style import apply_style
from streamlit_app.components.feedback import feedback_widget
from streamlit_app.components.role_banner import role_context_banner

st.set_page_config(page_title="Financial Dashboard", layout="wide")
page_init()
apply_style()
role_context_banner(24)

st.title(t("financial.title"))

plant_id = st.text_input(t("common.plant_id"), value="OCP-JFC")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    t("financial.tab_budget"), t("financial.tab_roi"),
    t("financial.tab_cost_drivers"), t("financial.tab_man_hours"),
    t("financial.tab_summary"),
])

# ── Tab 1: Budget Tracking ─────────────────────────────────────────
with tab1:
    st.subheader(t("financial.budget_tracking"))

    with st.expander(t("financial.add_budget_items"), expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            category = st.selectbox(t("financial.category"), [
                "LABOR", "MATERIALS", "CONTRACTORS", "EQUIPMENT_RENTAL",
                "DOWNTIME_COST", "PRODUCTION_LOSS", "SAFETY_PENALTY", "OVERHEAD",
            ])
            planned = st.number_input(t("financial.planned_amount"), min_value=0.0, value=100000.0)
        with col2:
            description = st.text_input(t("financial.description"), value="")
            actual = st.number_input(t("financial.actual_amount"), min_value=0.0, value=95000.0)

    # Demo budget data
    if st.button(t("financial.run_demo_budget")):
        demo_items = [
            {"item_id": "B1", "plant_id": plant_id, "category": "LABOR",
             "description": "Maintenance labor", "planned_amount": 2000000, "actual_amount": 2200000},
            {"item_id": "B2", "plant_id": plant_id, "category": "MATERIALS",
             "description": "Spare parts", "planned_amount": 1500000, "actual_amount": 1400000},
            {"item_id": "B3", "plant_id": plant_id, "category": "CONTRACTORS",
             "description": "External services", "planned_amount": 800000, "actual_amount": 950000},
            {"item_id": "B4", "plant_id": plant_id, "category": "EQUIPMENT_RENTAL",
             "description": "Crane rental", "planned_amount": 300000, "actual_amount": 280000},
            {"item_id": "B5", "plant_id": plant_id, "category": "OVERHEAD",
             "description": "Admin & logistics", "planned_amount": 400000, "actual_amount": 420000},
        ]
        try:
            result = api_client.track_budget(plant_id, demo_items)
            c1, c2, c3 = st.columns(3)
            c1.metric(t("financial.total_planned"), f"${result.get('total_planned', 0):,.0f}")
            c2.metric(t("financial.total_actual"), f"${result.get('total_actual', 0):,.0f}")
            variance_pct = result.get("variance_pct", 0)
            color = "normal" if abs(variance_pct) < 5 else "inverse" if variance_pct > 15 else "off"
            c3.metric(t("financial.variance"), f"{variance_pct:.1f}%", delta=f"${result.get('total_variance', 0):,.0f}", delta_color=color)

            by_cat = result.get("by_category", {})
            if by_cat:
                st.plotly_chart(budget_variance_chart(by_cat), use_container_width=True)

            recs = result.get("recommendations", [])
            if recs:
                st.subheader(t("financial.recommendations"))
                for r in recs:
                    st.write(f"- {r}")

            # Alerts
            alerts = api_client.get_budget_alerts(plant_id, demo_items)
            if alerts:
                st.subheader(t("financial.alerts"))
                for a in alerts:
                    icon = "🔴" if a.get("severity") == "CRITICAL" else "🟡"
                    st.write(f"{icon} {a.get('message', '')}")
        except Exception as e:
            st.warning(f"{t('common.could_not_connect')}: {e}")

# ── Tab 2: ROI Calculator ──────────────────────────────────────────
with tab2:
    st.subheader(t("financial.roi_calculator"))

    with st.form("roi_form"):
        col1, col2 = st.columns(2)
        with col1:
            project_id = st.text_input(t("financial.project_id"), value="PROJ-001")
            investment = st.number_input(t("financial.investment_cost"), min_value=0.0, value=500000.0)
            downtime_hours = st.number_input(t("financial.avoided_downtime_hours"), min_value=0.0, value=200.0)
            prod_value = st.number_input(t("financial.hourly_production_value"), min_value=0.0, value=5000.0)
        with col2:
            labor_hours = st.number_input(t("financial.labor_savings_hours"), min_value=0.0, value=1000.0)
            labor_rate = st.number_input(t("financial.labor_cost_per_hour"), min_value=0.0, value=50.0)
            material_savings = st.number_input(t("financial.material_savings"), min_value=0.0, value=100000.0)
            horizon = st.slider(t("financial.analysis_horizon"), 1, 15, 5)

        submitted = st.form_submit_button(t("financial.calculate_roi"))

    if submitted:
        try:
            result = api_client.calculate_roi({
                "project_id": project_id,
                "plant_id": plant_id,
                "investment_cost": investment,
                "annual_avoided_downtime_hours": downtime_hours,
                "hourly_production_value": prod_value,
                "annual_labor_savings_hours": labor_hours,
                "labor_cost_per_hour": labor_rate,
                "annual_material_savings": material_savings,
                "analysis_horizon_years": horizon,
            })
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("NPV", f"${result.get('npv', 0):,.0f}")
            payback = result.get("payback_period_years")
            c2.metric(t("financial.payback"), f"{payback:.1f} yr" if payback else "N/A")
            c3.metric("BCR", f"{result.get('bcr', 0):.2f}")
            c4.metric("ROI", f"{result.get('roi_pct', 0):.1f}%")

            st.info(f"**{t('financial.recommendation')}:** {result.get('recommendation', '')}")

            cum = result.get("cumulative_savings_by_year", [])
            if cum:
                st.plotly_chart(roi_cumulative_chart(cum, investment), use_container_width=True)
        except Exception as e:
            st.warning(f"{t('common.could_not_connect')}: {e}")

# ── Tab 3: Cost Drivers ────────────────────────────────────────────
with tab3:
    st.subheader(t("financial.cost_drivers"))
    st.info(t("financial.cost_drivers_info"))

    if st.button(t("financial.run_demo_impact")):
        demo_impacts = [
            {"equipment_id": "SAG-MILL-01", "failure_rate": 3.0, "cost_per_failure": 50000,
             "cost_per_pm": 5000, "annual_pm_count": 12, "production_value_per_hour": 8000,
             "avg_downtime_hours": 24},
            {"equipment_id": "CONV-01", "failure_rate": 5.0, "cost_per_failure": 15000,
             "cost_per_pm": 2000, "annual_pm_count": 24, "production_value_per_hour": 8000,
             "avg_downtime_hours": 8},
            {"equipment_id": "PUMP-03", "failure_rate": 8.0, "cost_per_failure": 8000,
             "cost_per_pm": 1500, "annual_pm_count": 6, "production_value_per_hour": 5000,
             "avg_downtime_hours": 4},
        ]
        try:
            impacts = []
            for imp in demo_impacts:
                result = api_client.calculate_financial_impact(imp)
                impacts.append(result)

            if impacts:
                st.plotly_chart(cost_driver_pareto_chart(impacts), use_container_width=True)

                for i in impacts:
                    st.write(f"**{i.get('equipment_id')}** — Total: ${i.get('total_annual_impact', 0):,.0f} "
                             f"(Failures: ${i.get('annual_failure_cost', 0):,.0f}, "
                             f"PM: ${i.get('annual_pm_cost', 0):,.0f}, "
                             f"Downtime: ${i.get('annual_production_loss', 0):,.0f})")
        except Exception as e:
            st.warning(f"{t('common.could_not_connect')}: {e}")

# ── Tab 4: Man-Hours Savings ───────────────────────────────────────
with tab4:
    st.subheader(t("financial.man_hours_saved"))

    if st.button(t("financial.run_demo_man_hours")):
        try:
            result = api_client.calculate_man_hours_saved({
                "traditional_hours": {
                    "hierarchy_build": 120, "criticality_assessment": 80,
                    "fmeca": 200, "task_development": 160,
                    "work_package_assembly": 100, "sap_upload_prep": 60,
                },
                "ai_hours": {
                    "hierarchy_build": 40, "criticality_assessment": 25,
                    "fmeca": 60, "task_development": 50,
                    "work_package_assembly": 30, "sap_upload_prep": 15,
                },
                "labor_rate": 50.0,
                "plant_id": plant_id,
            })
            c1, c2, c3 = st.columns(3)
            c1.metric(t("financial.hours_saved"), f"{result.get('hours_saved', 0):,.0f} hrs")
            c2.metric(t("financial.savings_pct"), f"{result.get('savings_pct', 0):.0f}%")
            c3.metric(t("financial.cost_equivalent"), f"${result.get('cost_equivalent', 0):,.0f}")

            trad = result.get("traditional_man_hours", 0)
            ai = result.get("ai_assisted_man_hours", 0)
            by_act = result.get("by_activity", {})
            if by_act:
                st.plotly_chart(man_hours_comparison_chart(by_act,
                    result.get("traditional_man_hours", 0),
                    result.get("ai_assisted_man_hours", 0)), use_container_width=True)
        except Exception as e:
            st.warning(f"{t('common.could_not_connect')}: {e}")

# ── Tab 5: Financial Summary ───────────────────────────────────────
with tab5:
    st.subheader(t("financial.summary"))

    if st.button(t("financial.load_summary")):
        try:
            result = api_client.get_financial_summary(plant_id)
            c1, c2, c3 = st.columns(3)
            c1.metric(t("financial.total_budget"), f"${result.get('total_maintenance_budget', 0):,.0f}")
            c2.metric(t("financial.avoided_cost"), f"${result.get('total_avoided_cost', 0):,.0f}")
            c3.metric(t("financial.man_hours_metric"), f"{result.get('total_man_hours_saved', 0):,.0f}")

            prod = result.get("resource_productivity_multiplier", 1.0)
            st.metric(t("financial.productivity_multiplier"), f"{prod:.1f}x")

            recs = result.get("recommendations", [])
            if recs:
                st.subheader(t("financial.recommendations"))
                for r in recs:
                    st.write(f"- {r}")
        except Exception as e:
            st.warning(f"{t('common.could_not_connect')}: {e}")

feedback_widget("financial_dashboard")
