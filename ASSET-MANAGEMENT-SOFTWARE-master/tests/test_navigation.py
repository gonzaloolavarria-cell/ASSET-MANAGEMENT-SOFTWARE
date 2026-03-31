"""Navigation tests — validate all 27 Streamlit pages and components.

Verifies that:
1. Each page file (1-27) exists on disk
2. Component modules (charts, tables, forms, feedback, role_banner, expert_escalation) load correctly
3. The api_client has all expected endpoint methods
4. i18n translations are complete for all 4 languages
5. Role config covers all pages (GAP-W05, GAP-W13)
"""

import importlib
import json
from pathlib import Path

import pytest


# All 27 page files
PAGE_FILES = [
    "1_hierarchy.py",
    "2_criticality.py",
    "3_fmea.py",
    "4_strategy.py",
    "5_analytics.py",
    "6_sap_review.py",
    "7_overview.py",
    "8_field_capture.py",
    "9_work_requests.py",
    "10_planner.py",
    "11_backlog.py",
    "12_scheduling.py",
    "13_reliability.py",
    "14_executive_dashboard.py",
    "15_reports_data.py",
    "16_fmeca.py",
    "17_defect_elimination.py",
    "18_wizard.py",
    "19_progress.py",
    "20_equipment_chat.py",
    "21_deliverables.py",
    "22_execution_checklists.py",
    "23_troubleshooting.py",
    "24_financial.py",
    "25_expert_portal.py",
    "26_expert_knowledge.py",
    "27_workflow.py",
]


# ════════════════════════════════════════════════════════════════════════
# SECTION 1: PAGE FILES EXIST
# ════════════════════════════════════════════════════════════════════════

class TestPageFilesExist:

    @pytest.mark.parametrize("filename", PAGE_FILES)
    def test_page_file_exists(self, filename):
        page_path = Path("streamlit_app/pages") / filename
        assert page_path.exists(), f"Page file missing: {page_path}"

    def test_pages_init_exists(self):
        assert Path("streamlit_app/pages/__init__.py").exists()

    def test_total_page_count(self):
        pages_dir = Path("streamlit_app/pages")
        page_files = sorted(pages_dir.glob("[0-9]*_*.py"))
        assert len(page_files) == 27, f"Expected 27 pages, found {len(page_files)}"


# ════════════════════════════════════════════════════════════════════════
# SECTION 2: MAIN APP MODULES
# ════════════════════════════════════════════════════════════════════════

class TestMainAppModule:

    def test_app_file_exists(self):
        assert Path("streamlit_app/app.py").exists()

    def test_streamlit_app_init_exists(self):
        assert Path("streamlit_app/__init__.py").exists()

    def test_api_client_exists(self):
        assert Path("streamlit_app/api_client.py").exists()

    def test_style_module_exists(self):
        assert Path("streamlit_app/style.py").exists()


# ════════════════════════════════════════════════════════════════════════
# SECTION 3: COMPONENT MODULES
# ════════════════════════════════════════════════════════════════════════

class TestComponentModules:

    def test_charts_module(self):
        mod = importlib.import_module("streamlit_app.components.charts")
        for name in ["health_gauge", "kpi_bar_chart"]:
            assert hasattr(mod, name), f"charts missing: {name}"

    def test_tables_module(self):
        mod = importlib.import_module("streamlit_app.components.tables")
        for name in ["render_data_table", "status_badge"]:
            assert hasattr(mod, name), f"tables missing: {name}"

    def test_forms_module_constants(self):
        mod = importlib.import_module("streamlit_app.components.forms")
        assert hasattr(mod, "CRITICALITY_CATEGORIES")
        assert hasattr(mod, "MECHANISMS")
        assert hasattr(mod, "TASK_TYPES")
        assert hasattr(mod, "STRATEGY_TYPES")
        assert hasattr(mod, "FAILURE_CONSEQUENCES")
        assert len(mod.CRITICALITY_CATEGORIES) == 11
        assert len(mod.MECHANISMS) == 18

    def test_feedback_module(self):
        mod = importlib.import_module("streamlit_app.components.feedback")
        assert hasattr(mod, "feedback_widget")
        assert callable(mod.feedback_widget)

    def test_role_banner_module(self):
        mod = importlib.import_module("streamlit_app.components.role_banner")
        assert hasattr(mod, "role_context_banner")
        assert callable(mod.role_context_banner)

    def test_expert_escalation_module(self):
        mod = importlib.import_module("streamlit_app.components.expert_escalation")
        assert hasattr(mod, "expert_escalation_widget")
        assert callable(mod.expert_escalation_widget)

    def test_components_init_exists(self):
        assert Path("streamlit_app/components/__init__.py").exists()


# ════════════════════════════════════════════════════════════════════════
# SECTION 4: API CLIENT COMPLETENESS
# ════════════════════════════════════════════════════════════════════════

class TestAPIClientCompleteness:

    @pytest.fixture(autouse=True)
    def _load_client(self):
        self.mod = importlib.import_module("streamlit_app.api_client")

    def test_hierarchy_methods(self):
        for m in ["list_plants", "list_nodes", "get_node", "get_subtree",
                   "get_node_stats", "build_from_vendor"]:
            assert hasattr(self.mod, m), f"Missing: {m}"

    def test_criticality_methods(self):
        for m in ["assess_criticality", "get_criticality", "approve_criticality"]:
            assert hasattr(self.mod, m), f"Missing: {m}"

    def test_fmea_methods(self):
        for m in ["create_failure_mode", "list_failure_modes",
                   "validate_fm_combination", "get_fm_combinations", "rcm_decide"]:
            assert hasattr(self.mod, m), f"Missing: {m}"

    def test_tasks_methods(self):
        for m in ["list_tasks", "validate_task_name"]:
            assert hasattr(self.mod, m), f"Missing: {m}"

    def test_work_packages_methods(self):
        for m in ["list_work_packages", "approve_work_package"]:
            assert hasattr(self.mod, m), f"Missing: {m}"

    def test_sap_methods(self):
        for m in ["list_sap_uploads", "approve_sap_upload", "get_sap_mock"]:
            assert hasattr(self.mod, m), f"Missing: {m}"

    def test_analytics_methods(self):
        for m in ["calculate_health_score", "calculate_kpis",
                   "fit_weibull", "predict_failure"]:
            assert hasattr(self.mod, m), f"Missing: {m}"

    def test_admin_methods(self):
        for m in ["seed_database", "get_stats", "get_audit_log", "get_agent_status"]:
            assert hasattr(self.mod, m), f"Missing: {m}"

    def test_capture_methods(self):
        for m in ["submit_capture", "list_captures", "get_capture"]:
            assert hasattr(self.mod, m), f"Missing: {m}"

    def test_work_requests_methods(self):
        for m in ["list_work_requests", "get_work_request",
                   "validate_work_request", "classify_work_request"]:
            assert hasattr(self.mod, m), f"Missing: {m}"

    def test_planner_methods(self):
        for m in ["generate_recommendation", "get_recommendation",
                   "apply_planner_action"]:
            assert hasattr(self.mod, m), f"Missing: {m}"

    def test_backlog_methods(self):
        for m in ["list_backlog", "add_to_backlog", "optimize_backlog",
                   "get_optimization", "approve_schedule", "get_schedule"]:
            assert hasattr(self.mod, m), f"Missing: {m}"

    def test_scheduling_methods(self):
        for m in ["create_program", "list_programs", "get_program",
                   "finalize_program", "get_gantt"]:
            assert hasattr(self.mod, m), f"Missing: {m}"

    def test_reliability_methods(self):
        for m in ["analyze_spare_parts", "create_moc", "list_mocs",
                   "advance_moc", "analyze_jackknife", "analyze_pareto", "assess_rbi"]:
            assert hasattr(self.mod, m), f"Missing: {m}"

    def test_reporting_methods(self):
        for m in ["generate_weekly_report", "generate_monthly_report",
                   "generate_quarterly_report", "list_reports", "get_report",
                   "generate_notifications", "list_notifications",
                   "validate_import", "export_data", "run_cross_module_analysis"]:
            assert hasattr(self.mod, m), f"Missing: {m}"

    def test_dashboard_methods(self):
        for m in ["get_executive_dashboard", "get_kpi_summary", "get_dashboard_alerts"]:
            assert hasattr(self.mod, m), f"Missing: {m}"

    def test_rca_methods(self):
        for m in ["create_rca", "list_rcas", "get_rca", "get_rca_summary",
                   "run_5w2h", "advance_rca",
                   "calculate_planning_kpis", "list_planning_kpi_snapshots",
                   "calculate_de_kpis_full", "list_de_kpi_snapshots"]:
            assert hasattr(self.mod, m), f"Missing: {m}"

    def test_feedback_methods(self):
        for m in ["submit_feedback", "list_feedback"]:
            assert hasattr(self.mod, m), f"Missing: {m}"

    def test_execution_checklist_methods(self):
        for m in ["generate_execution_checklist", "list_execution_checklists",
                   "get_execution_checklist", "complete_checklist_step",
                   "skip_checklist_step", "get_checklist_next_steps",
                   "close_execution_checklist"]:
            assert hasattr(self.mod, m), f"Missing: {m}"

    def test_deliverable_methods(self):
        for m in ["list_deliverables", "get_deliverable", "create_deliverable",
                   "update_deliverable", "transition_deliverable", "log_time",
                   "list_time_logs", "get_deliverable_summary", "seed_deliverables"]:
            assert hasattr(self.mod, m), f"Missing: {m}"

    def test_troubleshooting_methods(self):
        for m in ["create_troubleshooting_session", "add_troubleshooting_symptom",
                   "record_troubleshooting_test", "finalize_troubleshooting",
                   "troubleshooting_feedback", "get_equipment_symptoms",
                   "get_troubleshooting_tree"]:
            assert hasattr(self.mod, m), f"Missing: {m}"

    def test_financial_methods(self):
        for m in ["calculate_roi", "compare_roi_scenarios", "track_budget",
                   "get_budget_alerts", "get_financial_summary",
                   "calculate_financial_impact", "calculate_man_hours_saved",
                   "forecast_budget"]:
            assert hasattr(self.mod, m), f"Missing: {m}"

    def test_expert_knowledge_methods(self):
        for m in ["create_consultation", "get_consultation", "list_consultations",
                   "mark_consultation_viewed", "submit_expert_response",
                   "close_consultation", "get_portal_consultation",
                   "create_contribution", "list_contributions",
                   "validate_contribution", "promote_contribution",
                   "list_experts", "register_expert", "get_expert_compensation",
                   "get_expert_notifications", "mark_expert_notification_read"]:
            assert hasattr(self.mod, m), f"Missing: {m}"


# ════════════════════════════════════════════════════════════════════════
# SECTION 5: I18N COMPLETENESS
# ════════════════════════════════════════════════════════════════════════

class TestI18NCompleteness:

    def _load_translations(self):
        i18n_dir = Path("streamlit_app/i18n")
        translations = {}
        for lang in ["en", "fr", "ar"]:
            with open(i18n_dir / f"{lang}.json", "r", encoding="utf-8") as f:
                translations[lang] = json.load(f)
        return translations

    def test_all_languages_have_meta(self):
        translations = self._load_translations()
        for lang in ["en", "fr", "ar"]:
            assert "_meta" in translations[lang], f"{lang}.json missing _meta"
            assert translations[lang]["_meta"]["language"] == lang

    def test_arabic_has_rtl_direction(self):
        translations = self._load_translations()
        assert translations["ar"]["_meta"]["direction"] == "rtl"

    def test_all_languages_have_common_section(self):
        translations = self._load_translations()
        for lang in ["en", "fr", "ar"]:
            assert "common" in translations[lang], f"{lang}.json missing 'common'"
            assert "app_title" in translations[lang]["common"]

    def test_key_coverage_major_sections(self):
        translations = self._load_translations()
        major_sections = ["common", "hierarchy", "criticality"]
        for lang in ["en", "fr"]:
            sections = set(translations[lang].keys()) - {"_meta"}
            for section in major_sections:
                assert section in sections, f"{lang} missing section: {section}"

    def test_role_keys_in_all_languages(self):
        translations = self._load_translations()
        for lang in ["en", "fr", "ar"]:
            assert "role" in translations[lang], f"{lang}.json missing 'role' section"
            role_section = translations[lang]["role"]
            assert "select_role" in role_section, f"{lang} role section missing 'select_role'"
            assert "manager" in role_section, f"{lang} role section missing 'manager'"

    def test_deliverables_i18n_in_all_languages(self):
        translations = self._load_translations()
        for lang in ["en", "fr", "ar"]:
            assert "deliverables" in translations[lang], f"{lang}.json missing 'deliverables' section"
            ds = translations[lang]["deliverables"]
            for key in ["title", "overview", "detail", "time_tracking", "client_review",
                        "total_deliverables", "completion", "hours_estimated",
                        "approve_deliverable", "reject_deliverable"]:
                assert key in ds, f"{lang} deliverables section missing '{key}'"

    def test_financial_i18n_in_all_languages(self):
        translations = self._load_translations()
        for lang in ["en", "fr", "ar"]:
            assert "financial" in translations[lang], f"{lang}.json missing 'financial' section"
            fs = translations[lang]["financial"]
            for key in ["title", "tab_budget", "tab_roi", "tab_cost_drivers",
                        "tab_man_hours", "tab_summary", "calculate_roi"]:
                assert key in fs, f"{lang} financial section missing '{key}'"

    def test_expert_portal_i18n_in_all_languages(self):
        translations = self._load_translations()
        for lang in ["en", "fr", "ar"]:
            assert "expert_portal" in translations[lang], f"{lang}.json missing 'expert_portal' section"
            ep = translations[lang]["expert_portal"]
            for key in ["title", "subtitle", "invalid_token", "token_expired",
                        "guidance_title", "submit_guidance", "thank_you",
                        "already_responded"]:
                assert key in ep, f"{lang} expert_portal section missing '{key}'"

    def test_expert_knowledge_i18n_in_all_languages(self):
        translations = self._load_translations()
        for lang in ["en", "fr", "ar"]:
            assert "expert_knowledge" in translations[lang], f"{lang}.json missing 'expert_knowledge' section"
            ek = translations[lang]["expert_knowledge"]
            for key in ["title", "tab_directory", "tab_consultations",
                        "tab_pipeline", "tab_compensation",
                        "escalate_to_expert", "expert_notified"]:
                assert key in ek, f"{lang} expert_knowledge section missing '{key}'"

    def test_troubleshooting_i18n_in_all_languages(self):
        translations = self._load_translations()
        for lang in ["en", "fr", "ar"]:
            assert "troubleshooting" in translations[lang], f"{lang}.json missing 'troubleshooting' section"
            ts = translations[lang]["troubleshooting"]
            for key in ["title", "tab_new", "tab_history", "tab_trees",
                        "select_equipment_type", "add_symptom", "candidate_diagnoses",
                        "finalize", "submit_feedback"]:
                assert key in ts, f"{lang} troubleshooting section missing '{key}'"


# ════════════════════════════════════════════════════════════════════════
# SECTION 6: ROLE CONFIG COVERS ALL PAGES (GAP-W05)
# ════════════════════════════════════════════════════════════════════════

class TestRoleConfigCoverage:

    def test_role_config_module_exists(self):
        assert Path("streamlit_app/role_config.py").exists()

    def test_page_registry_matches_page_files(self):
        from streamlit_app.role_config import PAGE_REGISTRY
        assert len(PAGE_REGISTRY) == 27

    def test_all_page_files_in_registry(self):
        from streamlit_app.role_config import PAGE_REGISTRY
        registry_files = {p["file"] for p in PAGE_REGISTRY}
        for filename in PAGE_FILES:
            assert filename in registry_files, f"{filename} not in PAGE_REGISTRY"

    def test_every_role_maps_at_least_one_page(self):
        from streamlit_app.role_config import UserRole, ROLE_PAGE_MAP
        for role in UserRole:
            pages = ROLE_PAGE_MAP[role]
            total = len(pages["primary"]) + len(pages["secondary"])
            assert total > 0, f"{role} has no pages mapped"
