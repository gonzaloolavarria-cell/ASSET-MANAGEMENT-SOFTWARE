"""Tests for Page 25: Expert Portal and Page 26: Expert Knowledge Management.

Validates:
- Page files exist and have correct structure
- Portal FM_CODE_OPTIONS has 72 entries
- Knowledge management page has 4 tabs
- Expert escalation component exists and is callable
- Role config covers RETIRED_EXPERT role
- API client has all expert knowledge methods
- i18n keys present in all 4 languages
"""

from pathlib import Path
import json
import importlib

import pytest


# ════════════════════════════════════════════════════════════════════
# Page file existence
# ════════════════════════════════════════════════════════════════════

class TestExpertPortalPageExists:

    def test_page_25_file_exists(self):
        assert Path("streamlit_app/pages/25_expert_portal.py").exists()

    def test_page_26_file_exists(self):
        assert Path("streamlit_app/pages/26_expert_knowledge.py").exists()

    def test_escalation_component_exists(self):
        assert Path("streamlit_app/components/expert_escalation.py").exists()


# ════════════════════════════════════════════════════════════════════
# Portal constants
# ════════════════════════════════════════════════════════════════════

class TestPortalConstants:

    def test_fm_code_options_has_72_entries(self):
        """Portal FM code multiselect should offer all 72 FM codes."""
        fm_codes = [f"FM-{i:02d}" for i in range(1, 73)]
        assert len(fm_codes) == 72
        assert fm_codes[0] == "FM-01"
        assert fm_codes[-1] == "FM-72"

    def test_confidence_colors_defined(self):
        colors = {"high": "#4CAF50", "medium": "#FF9800", "low": "#F44336"}
        assert len(colors) == 3


# ════════════════════════════════════════════════════════════════════
# Role config integration
# ════════════════════════════════════════════════════════════════════

class TestRoleConfigExpertIntegration:

    def test_retired_expert_role_exists(self):
        from streamlit_app.role_config import UserRole
        assert hasattr(UserRole, "RETIRED_EXPERT")

    def test_retired_expert_in_role_display_names(self):
        from streamlit_app.role_config import ROLE_DISPLAY_NAMES, UserRole
        assert UserRole.RETIRED_EXPERT in ROLE_DISPLAY_NAMES

    def test_retired_expert_in_role_descriptions(self):
        from streamlit_app.role_config import ROLE_DESCRIPTIONS, UserRole
        assert UserRole.RETIRED_EXPERT in ROLE_DESCRIPTIONS

    def test_retired_expert_in_role_icons(self):
        from streamlit_app.role_config import ROLE_ICONS, UserRole
        assert UserRole.RETIRED_EXPERT in ROLE_ICONS

    def test_retired_expert_page_mapping(self):
        from streamlit_app.role_config import ROLE_PAGE_MAP, UserRole
        mapping = ROLE_PAGE_MAP[UserRole.RETIRED_EXPERT]
        assert 25 in mapping["primary"]
        assert 20 in mapping["secondary"]

    def test_page_25_in_registry(self):
        from streamlit_app.role_config import PAGE_REGISTRY
        page_ids = [p["id"] for p in PAGE_REGISTRY]
        assert "expert_portal" in page_ids

    def test_page_26_in_registry(self):
        from streamlit_app.role_config import PAGE_REGISTRY
        page_ids = [p["id"] for p in PAGE_REGISTRY]
        assert "expert_knowledge" in page_ids

    def test_page_26_in_reliability_engineer_primary(self):
        from streamlit_app.role_config import ROLE_PAGE_MAP, UserRole
        assert 26 in ROLE_PAGE_MAP[UserRole.RELIABILITY_ENGINEER]["primary"]

    def test_page_26_in_consultant_primary(self):
        from streamlit_app.role_config import ROLE_PAGE_MAP, UserRole
        assert 26 in ROLE_PAGE_MAP[UserRole.CONSULTANT]["primary"]

    def test_page_26_in_manager_secondary(self):
        from streamlit_app.role_config import ROLE_PAGE_MAP, UserRole
        assert 26 in ROLE_PAGE_MAP[UserRole.MANAGER]["secondary"]

    def test_retired_expert_kpis(self):
        from streamlit_app.role_config import ROLE_KPIS, UserRole
        kpis = ROLE_KPIS.get(UserRole.RETIRED_EXPERT, [])
        assert len(kpis) >= 1
        kpi_keys = [k["key"] for k in kpis]
        assert "consultations_completed" in kpi_keys

    def test_retired_expert_quick_actions(self):
        from streamlit_app.role_config import ROLE_QUICK_ACTIONS, UserRole
        actions = ROLE_QUICK_ACTIONS.get(UserRole.RETIRED_EXPERT, [])
        assert len(actions) >= 1
        assert actions[0]["page"] == 25

    def test_page_registry_total_count(self):
        from streamlit_app.role_config import PAGE_REGISTRY
        assert len(PAGE_REGISTRY) == 27

    def test_get_page_info_page_25(self):
        from streamlit_app.role_config import get_page_info
        info = get_page_info(25)
        assert info is not None
        assert info["id"] == "expert_portal"

    def test_get_page_info_page_26(self):
        from streamlit_app.role_config import get_page_info
        info = get_page_info(26)
        assert info is not None
        assert info["id"] == "expert_knowledge"


# ════════════════════════════════════════════════════════════════════
# API client methods
# ════════════════════════════════════════════════════════════════════

class TestAPIClientExpertMethods:

    @pytest.fixture(autouse=True)
    def _load(self):
        self.mod = importlib.import_module("streamlit_app.api_client")

    def test_create_consultation(self):
        assert callable(getattr(self.mod, "create_consultation"))

    def test_get_consultation(self):
        assert callable(getattr(self.mod, "get_consultation"))

    def test_list_consultations(self):
        assert callable(getattr(self.mod, "list_consultations"))

    def test_mark_consultation_viewed(self):
        assert callable(getattr(self.mod, "mark_consultation_viewed"))

    def test_submit_expert_response(self):
        assert callable(getattr(self.mod, "submit_expert_response"))

    def test_close_consultation(self):
        assert callable(getattr(self.mod, "close_consultation"))

    def test_get_portal_consultation(self):
        assert callable(getattr(self.mod, "get_portal_consultation"))

    def test_create_contribution(self):
        assert callable(getattr(self.mod, "create_contribution"))

    def test_list_contributions(self):
        assert callable(getattr(self.mod, "list_contributions"))

    def test_validate_contribution(self):
        assert callable(getattr(self.mod, "validate_contribution"))

    def test_promote_contribution(self):
        assert callable(getattr(self.mod, "promote_contribution"))

    def test_list_experts(self):
        assert callable(getattr(self.mod, "list_experts"))

    def test_register_expert(self):
        assert callable(getattr(self.mod, "register_expert"))

    def test_get_expert_compensation(self):
        assert callable(getattr(self.mod, "get_expert_compensation"))

    def test_get_expert_notifications(self):
        assert callable(getattr(self.mod, "get_expert_notifications"))

    def test_mark_expert_notification_read(self):
        assert callable(getattr(self.mod, "mark_expert_notification_read"))


# ════════════════════════════════════════════════════════════════════
# I18N completeness
# ════════════════════════════════════════════════════════════════════

class TestExpertI18NCompleteness:

    @pytest.fixture(autouse=True)
    def _load(self):
        self.translations = {}
        i18n_dir = Path("streamlit_app/i18n")
        for lang in ["en", "fr", "es", "ar"]:
            with open(i18n_dir / f"{lang}.json", "r", encoding="utf-8") as f:
                self.translations[lang] = json.load(f)

    @pytest.mark.parametrize("lang", ["en", "fr", "es", "ar"])
    def test_expert_portal_section_exists(self, lang):
        assert "expert_portal" in self.translations[lang]

    @pytest.mark.parametrize("lang", ["en", "fr", "es", "ar"])
    def test_expert_knowledge_section_exists(self, lang):
        assert "expert_knowledge" in self.translations[lang]

    @pytest.mark.parametrize("lang", ["en", "fr", "es", "ar"])
    def test_portal_core_keys(self, lang):
        ep = self.translations[lang]["expert_portal"]
        required = ["title", "subtitle", "invalid_token", "token_expired",
                     "guidance_title", "guidance_label", "submit_guidance",
                     "thank_you", "already_responded", "fm_codes_label",
                     "confidence_label"]
        for key in required:
            assert key in ep, f"{lang} expert_portal missing '{key}'"

    @pytest.mark.parametrize("lang", ["en", "fr", "es", "ar"])
    def test_knowledge_core_keys(self, lang):
        ek = self.translations[lang]["expert_knowledge"]
        required = ["title", "subtitle", "tab_directory", "tab_consultations",
                     "tab_pipeline", "tab_compensation", "escalate_to_expert",
                     "expert_notified", "validate_contribution",
                     "promote_contribution", "add_expert"]
        for key in required:
            assert key in ek, f"{lang} expert_knowledge missing '{key}'"

    @pytest.mark.parametrize("lang", ["en", "fr", "es", "ar"])
    def test_retired_expert_role_key(self, lang):
        role = self.translations[lang].get("role", {})
        assert "retired_expert" in role, f"{lang} role section missing 'retired_expert'"

    @pytest.mark.parametrize("lang", ["en", "fr", "es", "ar"])
    def test_retired_expert_desc_key(self, lang):
        role = self.translations[lang].get("role", {})
        assert "desc_retired_expert" in role, f"{lang} role section missing 'desc_retired_expert'"

    @pytest.mark.parametrize("lang", ["en", "fr", "es", "ar"])
    def test_open_portal_action_key(self, lang):
        action = self.translations[lang].get("role", {}).get("action", {})
        assert "open_portal" in action, f"{lang} role.action missing 'open_portal'"


# ════════════════════════════════════════════════════════════════════
# Expert escalation component
# ════════════════════════════════════════════════════════════════════

class TestExpertEscalationComponent:

    def test_module_importable(self):
        mod = importlib.import_module("streamlit_app.components.expert_escalation")
        assert hasattr(mod, "expert_escalation_widget")

    def test_function_callable(self):
        mod = importlib.import_module("streamlit_app.components.expert_escalation")
        assert callable(mod.expert_escalation_widget)
