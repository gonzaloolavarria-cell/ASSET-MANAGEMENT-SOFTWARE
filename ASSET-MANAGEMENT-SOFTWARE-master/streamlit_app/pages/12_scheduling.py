"""Page 12: Weekly Scheduling — Phase 4B Scheduling Engine + GAP-W09 Crew Assignment."""

import streamlit as st
from datetime import date, timedelta
from streamlit_app import api_client
from streamlit_app.components.charts import gantt_chart, schedule_utilization_chart
from streamlit_app.i18n import page_init, t
from streamlit_app.style import apply_style
from streamlit_app.components.feedback import feedback_widget
from streamlit_app.components.role_banner import role_context_banner

st.set_page_config(page_title="Weekly Scheduling", page_icon="📅", layout="wide")
page_init()
apply_style()
role_context_banner(12)

st.title(t("scheduling.title"))
st.markdown(t("scheduling.subtitle"))

tab_programs, tab_resources, tab_gantt, tab_assignments = st.tabs([
    t("scheduling.tab_programs"), t("scheduling.tab_resources"),
    t("scheduling.tab_gantt"), t("scheduling.tab_assignments"),
])

with tab_programs:
    st.subheader(t("scheduling.weekly_programs"))

    col_c1, col_c2, col_c3 = st.columns(3)
    with col_c1:
        plant_id = st.text_input(t("common.plant_id"), value="OCP-JFC1")
    with col_c2:
        week_num = st.number_input(t("scheduling.week_number"), min_value=1, max_value=53, value=1)
    with col_c3:
        year = st.number_input(t("scheduling.year"), min_value=2020, max_value=2030, value=2025)

    if st.button(t("scheduling.create_program"), type="primary"):
        try:
            result = api_client.create_program(plant_id, week_num, year)
            st.session_state["last_program"] = result
            st.success(f"Program created: {result.get('program_id', '')}")
        except Exception as e:
            st.error(f"Error: {e}")

    st.divider()
    st.subheader(t("scheduling.existing_programs"))

    try:
        programs = api_client.list_programs(plant_id=plant_id)
    except Exception:
        programs = []

    if programs:
        for prog in programs:
            col_p1, col_p2, col_p3, col_p4 = st.columns([3, 1, 1, 2])
            col_p1.write(f"**{prog.get('program_id', '')[:12]}...** — W{prog.get('week_number')}/{prog.get('year')}")
            col_p2.write(prog.get("status", ""))
            col_p3.write(f"{prog.get('total_hours', 0):.0f}h")
            with col_p4:
                pid = prog.get("program_id", "")
                if prog.get("status") == "DRAFT":
                    if st.button(t("scheduling.finalize"), key=f"fin-{pid}"):
                        try:
                            r = api_client.finalize_program(pid)
                            st.success(r.get("message", ""))
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
    else:
        st.info(t("scheduling.no_programs"))

with tab_resources:
    st.subheader(t("scheduling.resource_utilization"))

    prog = st.session_state.get("last_program")
    if prog:
        pid = prog.get("program_id", "")
        try:
            details = api_client.get_program(pid)
        except Exception:
            details = None

        if details:
            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric(t("scheduling.total_hours"), f"{details.get('total_hours', 0):.0f}h")
            col_m2.metric(t("backlog.work_packages"), len(details.get("work_packages") or []))
            conflicts = details.get("conflicts") or []
            col_m3.metric(t("scheduling.conflicts"), len(conflicts))

            slots = details.get("resource_slots") or []
            if slots:
                st.plotly_chart(schedule_utilization_chart(
                    [{"date": s.get("slot_date", ""), "utilization_percent": s.get("utilization_pct", 0)} for s in slots]
                ), width="stretch")

            if conflicts:
                st.subheader(t("scheduling.conflicts"))
                for c in conflicts:
                    st.warning(f"**{c.get('shift', '')}** — {c.get('description', '')}")
    else:
        st.info(t("scheduling.create_first_resources"))

with tab_gantt:
    st.subheader(t("scheduling.gantt_chart"))

    prog = st.session_state.get("last_program")
    if prog:
        pid = prog.get("program_id", "")
        try:
            gantt_data = api_client.get_gantt(pid)
        except Exception:
            gantt_data = None

        if gantt_data:
            st.plotly_chart(gantt_chart(gantt_data), width="stretch")

            st.download_button(
                label=t("scheduling.download_excel"),
                data=b"",  # Placeholder — actual download via API
                file_name=f"gantt_{pid}.xlsx",
                disabled=True,
                help="Use the API endpoint /scheduling/programs/{id}/gantt/export",
            )
        else:
            st.info(t("scheduling.no_gantt"))
    else:
        st.info(t("scheduling.create_first_gantt"))

# ── GAP-W09: Crew Assignment Tab ─────────────────────────────────────
with tab_assignments:
    st.subheader(t("scheduling.crew_assignment"))

    # Controls
    col_a1, col_a2, col_a3 = st.columns(3)
    with col_a1:
        assign_plant = st.text_input(
            t("common.plant_id"), value="OCP-JFC1", key="assign_plant",
        )
    with col_a2:
        assign_date = st.date_input(
            t("scheduling.assign_date"),
            value=date.today() + timedelta(days=1),
            key="assign_date",
        )
    with col_a3:
        assign_shift = st.selectbox(
            t("scheduling.assign_shift"),
            ["MORNING", "AFTERNOON", "NIGHT"],
            key="assign_shift",
        )

    # Crew status
    st.markdown(f"#### {t('scheduling.crew_status')}")
    try:
        technicians = api_client.get(
            f"/assignments/technicians?plant_id={assign_plant}&shift={assign_shift}"
        )
    except Exception:
        technicians = []

    if technicians:
        available = [tc for tc in technicians if tc.get("available")]
        absent = [tc for tc in technicians if not tc.get("available")]

        col_s1, col_s2, col_s3 = st.columns(3)
        col_s1.metric(t("scheduling.total_crew"), len(technicians))
        col_s2.metric(t("scheduling.available"), len(available))
        col_s3.metric(t("scheduling.absent"), len(absent))

        # Crew table
        crew_rows = []
        for tc in technicians:
            status_icon = "✅" if tc.get("available") else "❌"
            crew_rows.append({
                t("scheduling.col_name"): tc.get("name", ""),
                t("scheduling.col_specialty"): tc.get("specialty", ""),
                t("scheduling.col_level"): next(
                    (c.get("level", "?") for c in tc.get("competencies", [])
                     if c.get("specialty") == tc.get("specialty")),
                    tc.get("competency_level", "B") if "competency_level" in tc else "B",
                ),
                t("scheduling.col_status"): f"{status_icon} {t('scheduling.available') if tc.get('available') else t('scheduling.absent')}",
                t("scheduling.col_experience"): f"{tc.get('years_experience', 0)} {t('scheduling.years')}",
            })
        st.dataframe(crew_rows, use_container_width=True, hide_index=True)
    else:
        st.info(t("scheduling.no_crew_data"))

    st.divider()

    # Optimize button
    st.markdown(f"#### {t('scheduling.suggested_assignments')}")

    # Task input (from session state or manual)
    tasks_json = st.text_area(
        t("scheduling.tasks_json"),
        value=st.session_state.get("assignment_tasks_json", "[]"),
        height=100,
        help=t("scheduling.tasks_json_help"),
    )

    col_opt1, col_opt2 = st.columns([1, 4])
    with col_opt1:
        optimize_clicked = st.button(
            t("scheduling.optimize_btn"), type="primary",
        )

    if optimize_clicked:
        import json
        try:
            tasks_data = json.loads(tasks_json)
            result = api_client.post("/assignments/optimize", json={
                "tasks": tasks_data,
                "plant_id": assign_plant,
                "date": assign_date.isoformat(),
                "shift": assign_shift,
            })
            st.session_state["last_assignment_result"] = result
        except json.JSONDecodeError:
            st.error(t("scheduling.invalid_json"))
        except Exception as e:
            st.error(f"{t('scheduling.optimize_error')}: {e}")

    # Show results
    assignment_result = st.session_state.get("last_assignment_result")
    if assignment_result:
        assignments = assignment_result.get("assignments", [])
        unassigned = assignment_result.get("unassigned_task_ids", [])
        warnings = assignment_result.get("warnings", [])
        utilization = assignment_result.get("crew_utilization_pct", 0)

        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
        col_r1.metric(t("scheduling.assigned_tasks"), len(assignments))
        col_r2.metric(t("scheduling.unassigned_tasks"), len(unassigned))
        col_r3.metric(t("scheduling.utilization"), f"{utilization:.0f}%")
        col_r4.metric(
            t("scheduling.underqualified"),
            assignment_result.get("underqualified_assignments", 0),
        )

        # Assignment table
        if assignments:
            assign_rows = []
            for a in assignments:
                score = a.get("match_score", 0)
                if score >= 80:
                    score_color = "🟢"
                elif score >= 60:
                    score_color = "🟡"
                else:
                    score_color = "🔴"

                is_underqualified = any(
                    "Under-qualified" in r for r in a.get("match_reasons", [])
                )

                assign_rows.append({
                    t("scheduling.col_task"): a.get("task_id", ""),
                    t("scheduling.col_worker"): f"{a.get('worker_name', '')} ({a.get('competency_level', '')})",
                    t("scheduling.col_match"): f"{score_color} {score:.0f}%",
                    t("scheduling.col_hours"): a.get("estimated_hours", 0),
                    t("scheduling.col_assignment_status"): a.get("status", ""),
                    "⚠": "⚠ SUPERVISION" if is_underqualified else "",
                })
            st.dataframe(assign_rows, use_container_width=True, hide_index=True)

        # Warnings
        if warnings:
            st.markdown(f"#### {t('scheduling.warnings')}")
            for w in warnings:
                if "Under-qualified" in w or "Unassigned" in w:
                    st.warning(w)
                else:
                    st.info(w)

        # Re-optimize with absences
        st.divider()
        st.markdown(f"#### {t('scheduling.reoptimize')}")
        absent_ids = st.multiselect(
            t("scheduling.mark_absent"),
            options=[tc.get("worker_id", "") for tc in (technicians or []) if tc.get("available")],
            format_func=lambda wid: next(
                (tc.get("name", wid) for tc in (technicians or []) if tc.get("worker_id") == wid),
                wid,
            ),
        )

        col_re1, col_re2 = st.columns([1, 4])
        with col_re1:
            if st.button(t("scheduling.reoptimize_btn")):
                try:
                    import json
                    tasks_data = json.loads(tasks_json)
                    result = api_client.post("/assignments/reoptimize", json={
                        "existing_assignments": assignments,
                        "absent_worker_ids": absent_ids,
                        "tasks": tasks_data,
                        "plant_id": assign_plant,
                        "date": assign_date.isoformat(),
                        "shift": assign_shift,
                    })
                    st.session_state["last_assignment_result"] = result
                    st.rerun()
                except Exception as e:
                    st.error(f"{t('scheduling.reoptimize_error')}: {e}")

        # Confirm all
        with col_re2:
            if assignments and st.button(t("scheduling.confirm_all")):
                st.success(t("scheduling.all_confirmed"))

feedback_widget("scheduling")
