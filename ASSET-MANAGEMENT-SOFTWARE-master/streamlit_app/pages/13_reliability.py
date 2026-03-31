"""Page 13: Advanced Reliability Engineering — Phase 5."""

import streamlit as st
from streamlit_app import api_client
from streamlit_app.components.charts import jackknife_chart, pareto_chart, rbi_risk_matrix
from streamlit_app.i18n import page_init, t
from streamlit_app.style import apply_style
from streamlit_app.components.feedback import feedback_widget
from streamlit_app.components.role_banner import role_context_banner

st.set_page_config(page_title="Reliability Engineering", page_icon="🔧", layout="wide")
page_init()
apply_style()
role_context_banner(13)

st.title(t("reliability.title"))
st.markdown(t("reliability.subtitle"))

tab_sp, tab_sd, tab_moc, tab_ocr, tab_ba, tab_rbi = st.tabs([
    t("reliability.tab_spare"), t("reliability.tab_shutdown"), t("reliability.tab_moc"),
    t("reliability.tab_ocr"), t("reliability.tab_bad_actors"), t("reliability.tab_rbi"),
])

with tab_sp:
    st.subheader(t("reliability.spare_parts_title"))
    st.markdown(t("reliability.spare_parts_desc"))

    col1, col2 = st.columns(2)
    with col1:
        plant_id = st.text_input(t("common.plant_id"), value="OCP-JFC1", key="sp_plant")
    with col2:
        num_parts = st.number_input(t("reliability.sample_parts"), min_value=1, max_value=20, value=3)

    if st.button(t("reliability.run_analysis"), key="sp_analyze", type="primary"):
        parts = []
        for i in range(num_parts):
            parts.append({
                "part_id": f"SP-{i+1:03d}",
                "equipment_id": f"EQ-{i+1}",
                "description": f"Spare part {i+1}",
                "equipment_criticality": ["HIGH", "MEDIUM", "LOW"][i % 3],
                "failure_impact": ["PRODUCTION_STOP", "PRODUCTION_REDUCED", "NONE"][i % 3],
                "movements_per_year": [15, 6, 0][i % 3],
                "annual_cost": [50000, 15000, 2000][i % 3],
                "unit_cost": [500, 150, 20][i % 3],
                "daily_consumption": [0.5, 0.1, 0.01][i % 3],
                "lead_time_days": [30, 60, 90][i % 3],
                "current_stock": 10,
            })
        try:
            result = api_client.analyze_spare_parts(plant_id, parts)
            st.success(f"Analyzed {result.get('total_parts', 0)} parts")
            st.metric(t("reliability.total_inventory"), f"${result.get('total_inventory_value', 0):,.0f}")
            st.metric(t("reliability.recommended_reduction"), f"{result.get('recommended_reduction_pct', 0):.1f}%")
            if result.get("results"):
                st.dataframe([{
                    "Part": r["part_id"], "VED": r["ved_class"], "FSN": r["fsn_class"],
                    "ABC": r["abc_class"], "Score": r["criticality_score"],
                    "Min": r["recommended_min_stock"], "Max": r["recommended_max_stock"],
                    "ROP": r["reorder_point"],
                } for r in result["results"]])
        except Exception as e:
            st.error(str(e))

with tab_sd:
    st.subheader(t("reliability.shutdown_title"))
    st.markdown(t("reliability.shutdown_desc"))

    col1, col2 = st.columns(2)
    with col1:
        sd_name = st.text_input(t("reliability.shutdown_name"), value="Major Turnaround 2025")
        sd_plant = st.text_input(t("reliability.plant"), value="OCP-JFC1", key="sd_plant")
    with col2:
        sd_start = st.text_input(t("reliability.planned_start"), value="2025-06-01T06:00:00")
        sd_end = st.text_input(t("reliability.planned_end"), value="2025-06-08T18:00:00")

    if st.button(t("reliability.create_shutdown"), key="sd_create", type="primary"):
        try:
            result = api_client.create_shutdown(
                sd_plant, sd_name, sd_start, sd_end, ["WO-001", "WO-002", "WO-003"],
            )
            st.session_state["last_shutdown"] = result
            st.success(f"Shutdown created: {result.get('shutdown_id', '')[:12]}...")
        except Exception as e:
            st.error(str(e))

    # ── GAP-W14: Enhanced Shutdown Management ────────────────────────
    if "last_shutdown" in st.session_state:
        sd_data = st.session_state["last_shutdown"]
        sd_id = sd_data.get("shutdown_id", "")

        st.divider()
        st.markdown(f"**{t('reliability.sd_active')}:** `{sd_id[:12]}...` — {sd_data.get('status', 'N/A')}")

        with st.expander(t("reliability.sd_daily_report")):
            dr_date = st.date_input(t("reliability.sd_report_date"), key="sd_dr_date")
            dr_completed = st.text_input(
                t("reliability.sd_completed_today"),
                value="WO-001",
                help="Comma-separated WO IDs",
                key="sd_dr_completed",
            )
            dr_blockers = st.text_area(
                t("reliability.sd_blockers"), value="", key="sd_dr_blockers",
                help="One blocker per line: WO_ID:reason",
            )
            dr_delay = st.number_input(t("reliability.sd_delay_hours"), min_value=0.0, value=0.0, key="sd_dr_delay")

            if st.button(t("reliability.sd_generate_daily"), key="sd_gen_daily", type="primary"):
                completed_list = [w.strip() for w in dr_completed.split(",") if w.strip()]
                blocked_list = []
                for line in dr_blockers.strip().split("\n"):
                    if ":" in line:
                        wo_id, reason = line.split(":", 1)
                        blocked_list.append({"work_order_id": wo_id.strip(), "status": "BLOCKED", "blocker": reason.strip()})
                try:
                    from tools.engines.shutdown_engine import ShutdownEngine
                    from tools.models.schemas import ShutdownEvent, ShutdownWorkOrderStatus
                    event = ShutdownEvent(**sd_data)
                    blocked_wos = [ShutdownWorkOrderStatus(**b) for b in blocked_list] or None
                    report = ShutdownEngine.generate_daily_report(
                        event, dr_date, completed_list, blocked_wos, dr_delay,
                    )
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric(t("reliability.sd_completion"), f"{report.completion_pct}%")
                    col_b.metric(t("reliability.sd_pending"), str(len(report.pending_work_orders)))
                    col_c.metric(t("reliability.sd_delays_cum"), f"{report.delay_hours_cumulative}h")
                    for section in report.sections:
                        st.markdown(f"**{section.title}**")
                        st.write(section.content)
                except Exception as e:
                    st.error(str(e))

        with st.expander(t("reliability.sd_shift_suggestion")):
            ss_date = st.date_input(t("reliability.sd_target_date"), key="sd_ss_date")
            ss_shift = st.selectbox(t("reliability.sd_target_shift"), ["MORNING", "AFTERNOON", "NIGHT"], key="sd_ss_shift")

            if st.button(t("reliability.sd_get_suggestion"), key="sd_gen_suggest", type="primary"):
                try:
                    from tools.engines.shutdown_engine import ShutdownEngine
                    from tools.models.schemas import ShutdownEvent, ShiftType
                    event = ShutdownEvent(**sd_data)
                    suggestion = ShutdownEngine.suggest_next_shift_focus(
                        event, ss_date, ShiftType(ss_shift),
                    )
                    st.markdown(f"**{t('reliability.sd_priority_wos')}**")
                    for wo, reason in zip(suggestion.priority_work_orders[:5], suggestion.priority_reasons[:5]):
                        st.write(f"- {reason}")
                    if suggestion.focus_areas:
                        st.markdown(f"**{t('reliability.sd_focus_areas')}:** {', '.join(suggestion.focus_areas)}")
                    st.info(f"{t('reliability.sd_projected')}: {suggestion.estimated_completion_if_on_track}%")
                    st.markdown(f"**{t('reliability.sd_safety')}**")
                    for reminder in suggestion.safety_reminders:
                        st.write(f"- {reminder}")
                except Exception as e:
                    st.error(str(e))

        with st.expander(t("reliability.sd_schedule")):
            st.markdown(t("reliability.sd_schedule_desc"))
            sch_json = st.text_area(
                t("reliability.sd_wo_details"),
                value='[{"work_order_id": "WO-001", "name": "Replace bearing", "duration_hours": 4, "dependencies": [], "specialties": ["mech"], "area": "SAG"}]',
                height=120,
                key="sd_sch_json",
            )
            if st.button(t("reliability.sd_generate_schedule"), key="sd_gen_schedule", type="primary"):
                try:
                    import json as _json
                    from tools.engines.shutdown_engine import ShutdownEngine
                    from tools.models.schemas import ShutdownEvent
                    event = ShutdownEvent(**sd_data)
                    wo_details = _json.loads(sch_json)
                    schedule = ShutdownEngine.generate_shutdown_schedule(event, wo_details)
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric(t("reliability.sd_total_hours"), f"{schedule.total_duration_hours}h")
                    col_b.metric(t("reliability.sd_critical_path"), f"{schedule.critical_path_hours}h")
                    col_c.metric(t("reliability.sd_shifts_needed"), str(schedule.shifts_required))
                    if schedule.items:
                        import pandas as pd
                        df = pd.DataFrame([{
                            "WO": i.work_order_id, "Name": i.name,
                            "Start (h)": i.start_offset_hours, "Duration (h)": i.duration_hours,
                            "End (h)": i.end_offset_hours, "Shift": i.shift.value,
                            "Critical": "Yes" if i.is_critical_path else "",
                        } for i in schedule.items])
                        st.dataframe(df, use_container_width=True)
                except Exception as e:
                    st.error(str(e))

        with st.expander(t("reliability.sd_final_summary")):
            if st.button(t("reliability.sd_generate_final"), key="sd_gen_final", type="primary"):
                try:
                    from tools.engines.shutdown_engine import ShutdownEngine
                    from tools.models.schemas import ShutdownEvent
                    event = ShutdownEvent(**sd_data)
                    report = ShutdownEngine.generate_final_summary(event)
                    col_a, col_b = st.columns(2)
                    col_a.metric(t("reliability.sd_compliance"), f"{report.schedule_compliance_pct}%")
                    col_b.metric(t("reliability.sd_completion"), f"{report.completion_pct}%")
                    for section in report.sections:
                        st.markdown(f"**{section.title}**")
                        st.write(section.content)
                        if section.metrics:
                            st.json(section.metrics)
                except Exception as e:
                    st.error(str(e))

with tab_moc:
    st.subheader(t("reliability.moc_title"))
    st.markdown(t("reliability.moc_workflow"))

    col1, col2 = st.columns(2)
    with col1:
        moc_title = st.text_input(t("reliability.moc_name"), value="Replace bearing type on SAG mill")
        moc_category = st.selectbox(t("reliability.category"), [
            "EQUIPMENT_MODIFICATION", "PROCESS_CHANGE", "STRATEGY_CHANGE",
            "MATERIAL_SUBSTITUTION", "PROCEDURE_UPDATE",
        ])
    with col2:
        moc_plant = st.text_input(t("reliability.plant"), value="OCP-JFC1", key="moc_plant")
        moc_risk = st.selectbox(t("reliability.risk_level"), ["LOW", "MEDIUM", "HIGH", "CRITICAL"])

    if st.button(t("reliability.create_moc"), key="moc_create", type="primary"):
        try:
            result = api_client.create_moc(
                moc_plant, moc_title, "Change request for improved reliability",
                moc_category, "REQ-001", risk_level=moc_risk,
            )
            st.success(f"MoC created: {result.get('moc_id', '')[:12]}...")
        except Exception as e:
            st.error(str(e))

    st.divider()
    st.subheader(t("reliability.existing_mocs"))
    try:
        mocs = api_client.list_mocs(plant_id=moc_plant)
    except Exception:
        mocs = []

    if mocs:
        for m in mocs:
            st.write(f"**{m.get('title', '')}** — {m.get('status', '')} ({m.get('category', '')})")
    else:
        st.info(t("reliability.no_mocs"))

with tab_ocr:
    st.subheader(t("reliability.ocr_title"))
    st.markdown(t("reliability.ocr_desc"))

    col1, col2, col3 = st.columns(3)
    with col1:
        ocr_eq = st.text_input(t("common.equipment_id"), value="EQ-SAG-001", key="ocr_eq")
        ocr_fr = st.number_input(t("reliability.failure_rate"), value=2.0, min_value=0.1, step=0.1)
    with col2:
        ocr_cf = st.number_input(t("reliability.cost_per_failure"), value=50000, min_value=100, step=1000)
        ocr_cp = st.number_input(t("reliability.cost_per_pm"), value=5000, min_value=100, step=500)
    with col3:
        ocr_ci = st.number_input(t("reliability.current_interval"), value=90, min_value=7, max_value=365)

    if st.button(t("reliability.optimize"), key="ocr_run", type="primary"):
        try:
            result = api_client.calculate_ocr({
                "equipment_id": ocr_eq, "failure_rate": ocr_fr,
                "cost_per_failure": ocr_cf, "cost_per_pm": ocr_cp,
                "current_pm_interval_days": ocr_ci,
            })
            col_r1, col_r2, col_r3 = st.columns(3)
            col_r1.metric(t("reliability.optimal_interval"), f"{result.get('optimal_interval_days', 0)}d")
            col_r2.metric(t("reliability.savings"), f"{result.get('savings_pct', 0):.1f}%")
            col_r3.metric(t("reliability.optimal_cost"), f"${result.get('cost_at_optimal', 0):,.0f}/yr")
            st.info(result.get("recommendation", ""))
        except Exception as e:
            st.error(str(e))

with tab_ba:
    st.subheader(t("reliability.bad_actors_title"))
    jk_tab, pareto_tab = st.tabs([t("reliability.jackknife_tab"), t("reliability.pareto_tab")])

    with jk_tab:
        ba_plant = st.text_input(t("common.plant_id"), value="OCP-JFC1", key="jk_plant")
        if st.button(t("reliability.run_jackknife"), key="jk_run", type="primary"):
            equipment_data = [
                {"equipment_id": f"EQ-{i+1}", "equipment_tag": f"BRY-SAG-{i+1:03d}",
                 "failure_count": [15, 3, 8, 1, 12][i], "total_downtime_hours": [120, 48, 24, 96, 60][i],
                 "operating_hours": 8760}
                for i in range(5)
            ]
            try:
                result = api_client.analyze_jackknife(ba_plant, equipment_data)
                col1, col2, col3, col4 = st.columns(4)
                col1.metric(t("reliability.acute"), result.get("acute_count", 0))
                col2.metric(t("reliability.chronic"), result.get("chronic_count", 0))
                col3.metric(t("reliability.complex"), result.get("complex_count", 0))
                col4.metric(t("reliability.controlled"), result.get("controlled_count", 0))
                st.plotly_chart(jackknife_chart(result.get("points", [])), width="stretch")
            except Exception as e:
                st.error(str(e))

    with pareto_tab:
        pareto_plant = st.text_input(t("common.plant_id"), value="OCP-JFC1", key="pareto_plant")
        pareto_metric = st.selectbox(t("reliability.metric_type"), ["failures", "cost", "downtime"])
        if st.button(t("reliability.run_pareto"), key="pareto_run", type="primary"):
            records = [
                {"equipment_id": f"EQ-{i+1}", "equipment_tag": f"BRY-{i+1:03d}",
                 "cost": [50000, 30000, 15000, 8000, 5000, 3000, 2000, 1500, 1000, 500][i],
                 "downtime_hours": [120, 80, 40, 20, 15, 10, 8, 5, 3, 1][i]}
                for i in range(10)
            ]
            try:
                result = api_client.analyze_pareto(pareto_plant, pareto_metric, records)
                st.metric(t("reliability.bad_actors_count"), f"{result.get('bad_actor_count', 0)} / {len(result.get('items', []))}")
                st.plotly_chart(pareto_chart(result.get("items", [])), width="stretch")
            except Exception as e:
                st.error(str(e))

with tab_rbi:
    st.subheader(t("reliability.rbi_title"))
    st.markdown(t("reliability.rbi_desc"))

    rbi_plant = st.text_input(t("common.plant_id"), value="OCP-JFC1", key="rbi_plant")
    if st.button(t("reliability.run_rbi"), key="rbi_run", type="primary"):
        equipment_list = [
            {"equipment_id": f"EQ-S-{i+1}", "equipment_type": ["PRESSURE_VESSEL", "HEAT_EXCHANGER", "PIPING", "TANK", "STRUCTURE"][i % 5],
             "damage_mechanisms": [["CORROSION"], ["FATIGUE", "CORROSION"], ["EROSION"], ["CORROSION", "STRESS_CORROSION"], ["FATIGUE"]][i % 5],
             "age_years": [5, 12, 20, 8, 25][i % 5], "design_life_years": 25,
             "last_inspection_date": "2024-01-15"}
            for i in range(5)
        ]
        try:
            result = api_client.assess_rbi(rbi_plant, equipment_list)
            col1, col2, col3 = st.columns(3)
            col1.metric(t("reliability.total_equipment"), result.get("total_equipment", 0))
            col2.metric(t("reliability.high_risk"), result.get("high_risk_count", 0))
            col3.metric(t("reliability.overdue"), result.get("overdue_count", 0))
            st.plotly_chart(rbi_risk_matrix(result.get("assessments", [])), width="stretch")
            if result.get("assessments"):
                st.dataframe([{
                    "Equipment": a["equipment_id"], "Type": a["equipment_type"],
                    "Risk": a["risk_level"], "Score": a["risk_score"],
                    "Technique": a["recommended_technique"],
                    "Interval": f"{a['recommended_interval_months']}m",
                } for a in result["assessments"]])
        except Exception as e:
            st.error(str(e))

feedback_widget("reliability")
