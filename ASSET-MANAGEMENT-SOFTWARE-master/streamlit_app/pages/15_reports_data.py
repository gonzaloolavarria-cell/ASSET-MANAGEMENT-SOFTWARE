"""Page 15: Reports & Data Management — report generation, import, export."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
from streamlit_app import api_client
from streamlit_app.i18n import page_init, t
from streamlit_app.style import apply_style
from streamlit_app.components.feedback import feedback_widget
from streamlit_app.components.role_banner import role_context_banner
from streamlit_app.components.column_mapper import column_mapper_widget
from streamlit_app.components.import_errors import (
    import_result_summary, import_error_table, import_data_preview,
)

st.set_page_config(page_title="Reports & Data", layout="wide")
page_init()
apply_style()
role_context_banner(15)

st.title(t("reports.title"))

plant_id = st.text_input(t("common.plant_id"), value="OCP-JFC")

# ── Import type labels (order matches template numbering) ──────────
_IMPORT_TYPES = [
    "EQUIPMENT_HIERARCHY",       # 01
    "CRITICALITY_ASSESSMENT",    # 02
    "FAILURE_MODES",             # 03
    "MAINTENANCE_TASKS",         # 04
    "MAINTENANCE_PLAN",          # 05
    "WORK_ORDER_HISTORY",        # 06
    "SPARE_PARTS_INVENTORY",     # 07
    "SHUTDOWN_CALENDAR",         # 08
    "WORKFORCE",                 # 09
    "FIELD_CAPTURE",             # 10
    "RCA_EVENTS",                # 11
    "PLANNING_KPI",              # 12
    "DE_KPI",                    # 13
    "MAINTENANCE_STRATEGY",      # 14
    "FAILURE_HISTORY",           # legacy alias for 06
]

# Template number lookup for download
_TYPE_TO_TEMPLATE: dict[str, str] = {
    "EQUIPMENT_HIERARCHY": "01_equipment_hierarchy.xlsx",
    "CRITICALITY_ASSESSMENT": "02_criticality_assessment.xlsx",
    "FAILURE_MODES": "03_failure_modes.xlsx",
    "MAINTENANCE_TASKS": "04_maintenance_tasks.xlsx",
    "MAINTENANCE_PLAN": "05_work_packages.xlsx",
    "WORK_ORDER_HISTORY": "06_work_order_history.xlsx",
    "SPARE_PARTS_INVENTORY": "07_spare_parts_inventory.xlsx",
    "SHUTDOWN_CALENDAR": "08_shutdown_calendar.xlsx",
    "WORKFORCE": "09_workforce.xlsx",
    "FIELD_CAPTURE": "10_field_capture.xlsx",
    "RCA_EVENTS": "11_rca_events.xlsx",
    "PLANNING_KPI": "12_planning_kpi_input.xlsx",
    "DE_KPI": "13_de_kpi_input.xlsx",
    "MAINTENANCE_STRATEGY": "14_maintenance_strategy.xlsx",
    "FAILURE_HISTORY": "06_work_order_history.xlsx",
}

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    t("reports.tab_generate"), t("reports.tab_history"), t("reports.tab_import"), t("reports.tab_export"),
    t("import.history_tab"),
])

# ── Tab 1: Generate Report ─────────────────────────────────────────
with tab1:
    st.subheader(t("reports.generate_report"))
    report_type = st.selectbox(t("reports.report_type"), [t("reports.weekly"), t("reports.monthly"), t("reports.quarterly")])

    if report_type == t("reports.weekly"):
        col1, col2 = st.columns(2)
        week = col1.number_input(t("reports.week_number"), 1, 52, 1)
        year = col2.number_input(t("reports.year"), 2020, 2030, 2025)
        safety = st.number_input(t("reports.safety_incidents"), 0, 100, 0)
        backlog = st.number_input(t("reports.backlog_hours"), 0.0, 100000.0, 0.0)
        if st.button(t("reports.generate_weekly")):
            try:
                result = api_client.generate_weekly_report(plant_id, week, year, {
                    "safety_incidents": safety, "backlog_hours": backlog,
                })
                st.success(t("reports.weekly_generated"))
                st.json(result)
            except Exception as e:
                st.error(f"Failed: {e}")

    elif report_type == t("reports.monthly"):
        col1, col2 = st.columns(2)
        month = col1.number_input(t("reports.month"), 1, 12, 1)
        year = col2.number_input(t("reports.year"), 2020, 2030, 2025)
        if st.button(t("reports.generate_monthly")):
            try:
                result = api_client.generate_monthly_report(plant_id, month, year)
                st.success(t("reports.monthly_generated"))
                st.json(result)
            except Exception as e:
                st.error(f"Failed: {e}")

    else:
        col1, col2 = st.columns(2)
        quarter = col1.number_input(t("reports.quarter"), 1, 4, 1)
        year = col2.number_input(t("reports.year"), 2020, 2030, 2025)
        if st.button(t("reports.generate_quarterly")):
            try:
                result = api_client.generate_quarterly_report(plant_id, quarter, year)
                st.success(t("reports.quarterly_generated"))
                st.json(result)
            except Exception as e:
                st.error(f"Failed: {e}")

# ── Tab 2: Report History ──────────────────────────────────────────
with tab2:
    st.subheader(t("reports.report_history"))
    type_filter = st.selectbox(t("reports.filter_type"), ["All", "WEEKLY_MAINTENANCE", "MONTHLY_KPI", "QUARTERLY_REVIEW"])
    try:
        rt = None if type_filter == "All" else type_filter
        reports = api_client.list_reports(plant_id, rt)
        if reports:
            for r in reports:
                with st.expander(f"{r.get('report_type')} — {r.get('generated_at', '')[:10]}"):
                    st.write(f"**Report ID:** {r.get('report_id')}")
                    st.write(f"**Period:** {r.get('period_start')} to {r.get('period_end')}")
                    if st.button("View", key=r.get("report_id")):
                        detail = api_client.get_report(r["report_id"])
                        st.json(detail)
        else:
            st.info(t("reports.no_reports"))
    except Exception:
        st.warning(t("common.could_not_connect"))

# ── Tab 3: Data Import (GAP-W12 rewrite) ──────────────────────────
with tab3:
    st.subheader(t("reports.data_import"))

    # Step 1 — Select import type
    import_type = st.selectbox(t("reports.import_type"), _IMPORT_TYPES)

    # Template download button
    tpl_file = _TYPE_TO_TEMPLATE.get(import_type)
    if tpl_file:
        tpl_path = Path(__file__).resolve().parents[2] / "templates" / tpl_file
        if tpl_path.exists():
            with open(tpl_path, "rb") as f:
                st.download_button(
                    t("import.download_template"),
                    f.read(),
                    file_name=tpl_file,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

    st.info(t("reports.upload_info"))

    # Step 2 — Upload file OR paste JSON
    input_mode = st.radio(
        t("import.input_mode"),
        [t("import.mode_file"), t("import.mode_json")],
        horizontal=True,
    )

    if input_mode == t("import.mode_file"):
        uploaded = st.file_uploader(t("reports.upload_file"), type=["csv", "xlsx"])
        if uploaded is not None:
            file_bytes = uploaded.read()
            filename = uploaded.name

            # Parse file locally
            from tools.engines.file_parser_engine import FileParserEngine

            parse_result = FileParserEngine.parse_file(file_bytes, filename)

            if not parse_result.success:
                st.error(t("import.parse_failed"))
                for err in parse_result.errors:
                    st.write(f"- {err.message}")
            else:
                st.success(
                    t("import.file_parsed", rows=parse_result.total_rows, sheet=parse_result.sheet_parsed or "—")
                )

                # Sheet selector if multi-sheet
                if len(parse_result.sheets_available) > 1:
                    selected_sheet = st.selectbox(
                        t("import.select_sheet"),
                        parse_result.sheets_available,
                        index=parse_result.sheets_available.index(parse_result.sheet_parsed)
                        if parse_result.sheet_parsed in parse_result.sheets_available
                        else 0,
                    )
                    if selected_sheet != parse_result.sheet_parsed:
                        parse_result = FileParserEngine.parse_file(file_bytes, filename, selected_sheet)

                # Step 3 — Column mapping
                if parse_result.headers:
                    from tools.engines.data_import_engine import DataImportEngine
                    from tools.models.schemas import ImportSource

                    source_enum = ImportSource(import_type)
                    mapping = DataImportEngine.detect_column_mapping(parse_result.headers, source_enum)

                    with st.expander(t("import.column_mapping"), expanded=True):
                        final_mapping = column_mapper_widget(mapping)

                    # Step 4 — Validate + Ingest (via API)
                    if st.button(t("reports.validate_import"), key="validate_file"):
                        try:
                            entry = api_client.import_file(
                                plant_id=plant_id,
                                source=import_type,
                                file_bytes=file_bytes,
                                filename=filename,
                                sheet_name=parse_result.sheet_parsed,
                            )
                            # Reconstruct a display-compatible result from the API response
                            from tools.models.schemas import ImportResult, ImportValidationError
                            display_result = ImportResult(
                                source=source_enum,
                                total_rows=entry.get("total_rows", 0),
                                valid_rows=entry.get("valid_rows", 0),
                                error_rows=entry.get("error_rows", 0),
                                errors=[ImportValidationError(**e) for e in entry.get("errors", [])],
                            )
                            import_result_summary(display_result)
                            import_error_table(display_result)
                            import_data_preview(display_result)
                            if entry.get("status") in ("success", "partial"):
                                st.success(f"✓ {t('import.ingested')} — ID: `{entry.get('import_id', '')}`")
                        except Exception as api_err:
                            # Fallback: local validation (no DB persist)
                            col_map = final_mapping if final_mapping else None
                            result = DataImportEngine._validate(parse_result.rows, source_enum, col_map)
                            import_result_summary(result)
                            import_error_table(result)
                            import_data_preview(result)
                            st.warning(f"⚠ {t('common.could_not_connect')} — {api_err}")

    else:
        # JSON paste mode (backward compatible)
        sample_data = st.text_area(
            t("reports.paste_json"),
            value='[{"equipment_id": "EQ-001", "description": "Pump", "equipment_type": "ROTATING"}]',
        )
        if st.button(t("reports.validate_import"), key="validate_json"):
            try:
                rows = json.loads(sample_data)
                from tools.engines.data_import_engine import DataImportEngine
                from tools.models.schemas import ImportSource

                source_enum = ImportSource(import_type)
                result = DataImportEngine.validate_data(rows, source_enum)
                import_result_summary(result)
                import_error_table(result)
                import_data_preview(result)
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON: {e}")
            except Exception as e:
                st.error(f"Validation failed: {e}")

# ── Tab 4: Data Export ─────────────────────────────────────────────
with tab4:
    st.subheader(t("reports.data_export"))
    export_type = st.selectbox(t("reports.export_type"), ["equipment", "kpis", "schedule", "report"])
    if st.button(t("reports.prepare_export")):
        try:
            result = api_client.export_data(export_type, {})
            st.success(f"Export prepared with {len(result.get('sheets', []))} sheet(s)")
            for sheet in result.get("sheets", []):
                st.write(f"**{sheet.get('name')}**: {len(sheet.get('rows', []))} rows")
                if sheet.get("headers"):
                    st.write(f"Headers: {', '.join(sheet['headers'])}")
        except Exception as e:
            st.error(f"Export failed: {e}")

# ── Tab 5: Import History ──────────────────────────────────────────
with tab5:
    st.subheader(t("import.history_tab"))

    col_f1, col_f2 = st.columns([2, 1])
    source_filter = col_f1.selectbox(
        t("import.history_source"),
        ["All"] + _IMPORT_TYPES,
        key="hist_source_filter",
    )
    if col_f2.button(t("common.refresh"), key="hist_refresh"):
        st.rerun()

    try:
        src_param = None if source_filter == "All" else source_filter
        history = api_client.get_import_history(plant_id=plant_id, source=src_param, limit=100)

        if not history:
            st.info(t("import.history_empty"))
        else:
            _STATUS_ICON = {"success": "🟢", "partial": "🟡", "failed": "🔴"}
            for entry in history:
                status = entry.get("status", "")
                icon = _STATUS_ICON.get(status, "⚪")
                date_str = (entry.get("imported_at") or "")[:19].replace("T", " ")
                label = (
                    f"{icon} {entry.get('filename', '—')}  |  "
                    f"{entry.get('source', '—')}  |  "
                    f"{date_str}  |  "
                    f"{entry.get('valid_rows', 0)}/{entry.get('total_rows', 0)} {t('import.rows_valid')}"
                )
                with st.expander(label):
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric(t("import.history_status"), f"{icon} {t(f'import.history_status_{status}')}")
                    col_b.metric(t("reports.valid_rows"), f"{entry.get('valid_rows', 0)}/{entry.get('total_rows', 0)}")
                    col_c.metric(t("reports.error_rows"), entry.get("error_rows", 0))

                    errors = entry.get("errors", [])
                    if errors:
                        st.write(f"**{t('reports.validation_errors')}**")
                        import pandas as pd
                        df = pd.DataFrame(errors)[["row", "column", "message", "severity"]]
                        df.columns = [t("import.col_row"), t("import.col_column"), t("import.col_message"), "Severity"]
                        st.dataframe(df, use_container_width=True, hide_index=True)
    except Exception:
        st.warning(t("common.could_not_connect"))

feedback_widget("reports_data")
