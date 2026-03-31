"""Tests for streamlit_app.role_config — GAP-W05 role-based UI views."""

import pytest
from streamlit_app.role_config import (
    UserRole,
    DEFAULT_ROLE,
    ROLE_DISPLAY_NAMES,
    ROLE_DESCRIPTIONS,
    ROLE_ICONS,
    PAGE_REGISTRY,
    ROLE_PAGE_MAP,
    ROLE_KPIS,
    ROLE_QUICK_ACTIONS,
    get_page_info,
    get_role_pages,
    get_role_kpis,
    get_role_quick_actions,
    is_primary_page,
    is_relevant_page,
)


# --- Valid page numbers ---

VALID_PAGE_NUMBERS = {p["number"] for p in PAGE_REGISTRY}


class TestUserRole:
    """Test UserRole enum."""

    def test_has_six_roles(self):
        assert len(UserRole) == 7

    def test_role_values(self):
        expected = {"MANAGER", "RELIABILITY_ENGINEER", "PLANNER", "SUPERVISOR", "TECHNICIAN", "CONSULTANT", "RETIRED_EXPERT"}
        assert {r.value for r in UserRole} == expected

    def test_default_role_is_consultant(self):
        assert DEFAULT_ROLE == UserRole.CONSULTANT


class TestDisplayMaps:
    """Test that display name/description/icon maps cover all roles."""

    def test_display_names_cover_all_roles(self):
        for role in UserRole:
            assert role in ROLE_DISPLAY_NAMES, f"Missing display name for {role}"

    def test_descriptions_cover_all_roles(self):
        for role in UserRole:
            assert role in ROLE_DESCRIPTIONS, f"Missing description for {role}"

    def test_icons_cover_all_roles(self):
        for role in UserRole:
            assert role in ROLE_ICONS, f"Missing icon for {role}"

    def test_display_names_are_i18n_keys(self):
        for role, key in ROLE_DISPLAY_NAMES.items():
            assert key.startswith("role."), f"Display name for {role} should be an i18n key"

    def test_descriptions_are_i18n_keys(self):
        for role, key in ROLE_DESCRIPTIONS.items():
            assert key.startswith("role."), f"Description for {role} should be an i18n key"


class TestPageRegistry:
    """Test PAGE_REGISTRY completeness."""

    def test_has_24_pages(self):
        assert len(PAGE_REGISTRY) == 27

    def test_page_numbers_are_1_to_24(self):
        numbers = sorted(p["number"] for p in PAGE_REGISTRY)
        assert numbers == list(range(1, 28))

    def test_each_page_has_required_fields(self):
        required = {"number", "id", "file", "i18n_key", "milestone"}
        for page in PAGE_REGISTRY:
            missing = required - set(page.keys())
            assert not missing, f"Page {page.get('number')} missing fields: {missing}"

    def test_page_files_end_with_py(self):
        for page in PAGE_REGISTRY:
            assert page["file"].endswith(".py"), f"Page {page['number']} file should end with .py"


class TestRolePageMap:
    """Test ROLE_PAGE_MAP structure and validity."""

    def test_all_roles_have_page_maps(self):
        for role in UserRole:
            assert role in ROLE_PAGE_MAP, f"Missing page map for {role}"

    def test_page_maps_have_primary_and_secondary(self):
        for role, pages in ROLE_PAGE_MAP.items():
            assert "primary" in pages, f"{role} missing 'primary' key"
            assert "secondary" in pages, f"{role} missing 'secondary' key"

    def test_all_page_numbers_are_valid(self):
        for role, pages in ROLE_PAGE_MAP.items():
            for page_num in pages["primary"] + pages["secondary"]:
                assert page_num in VALID_PAGE_NUMBERS, f"Invalid page {page_num} in {role} map"

    def test_no_duplicate_pages_within_role(self):
        for role, pages in ROLE_PAGE_MAP.items():
            all_pages = pages["primary"] + pages["secondary"]
            assert len(all_pages) == len(set(all_pages)), f"Duplicate pages in {role} map"

    def test_primary_pages_not_empty(self):
        for role, pages in ROLE_PAGE_MAP.items():
            assert len(pages["primary"]) > 0, f"{role} has no primary pages"

    def test_consultant_has_most_pages(self):
        """Consultant should have access to the widest set of pages."""
        consultant_total = len(ROLE_PAGE_MAP[UserRole.CONSULTANT]["primary"]) + len(ROLE_PAGE_MAP[UserRole.CONSULTANT]["secondary"])
        for role in UserRole:
            if role == UserRole.CONSULTANT:
                continue
            role_total = len(ROLE_PAGE_MAP[role]["primary"]) + len(ROLE_PAGE_MAP[role]["secondary"])
            assert consultant_total >= role_total, f"Consultant should have >= pages than {role}"


class TestRoleKPIs:
    """Test ROLE_KPIS structure."""

    def test_all_roles_have_kpis(self):
        for role in UserRole:
            assert role in ROLE_KPIS, f"Missing KPIs for {role}"

    def test_kpis_not_empty(self):
        for role, kpis in ROLE_KPIS.items():
            assert len(kpis) > 0, f"{role} has no KPIs"

    def test_kpi_structure(self):
        required_keys = {"key", "i18n_key", "target", "unit"}
        for role, kpis in ROLE_KPIS.items():
            for kpi in kpis:
                missing = required_keys - set(kpi.keys())
                assert not missing, f"KPI {kpi.get('key')} in {role} missing: {missing}"

    def test_kpi_i18n_keys_start_with_kpi(self):
        for role, kpis in ROLE_KPIS.items():
            for kpi in kpis:
                assert kpi["i18n_key"].startswith("kpi."), f"KPI {kpi['key']} in {role} i18n_key should start with 'kpi.'"


class TestRoleQuickActions:
    """Test ROLE_QUICK_ACTIONS structure."""

    def test_all_roles_have_quick_actions(self):
        for role in UserRole:
            assert role in ROLE_QUICK_ACTIONS, f"Missing quick actions for {role}"

    def test_quick_actions_not_empty(self):
        for role, actions in ROLE_QUICK_ACTIONS.items():
            assert len(actions) > 0, f"{role} has no quick actions"

    def test_quick_action_pages_are_valid(self):
        for role, actions in ROLE_QUICK_ACTIONS.items():
            for action in actions:
                assert action["page"] in VALID_PAGE_NUMBERS, f"Invalid page {action['page']} in {role} quick actions"

    def test_quick_action_structure(self):
        for role, actions in ROLE_QUICK_ACTIONS.items():
            for action in actions:
                assert "label_key" in action, f"Quick action in {role} missing label_key"
                assert "page" in action, f"Quick action in {role} missing page"


class TestHelperFunctions:
    """Test helper functions."""

    def test_get_page_info_valid(self):
        info = get_page_info(1)
        assert info is not None
        assert info["id"] == "hierarchy"

    def test_get_page_info_invalid(self):
        info = get_page_info(99)
        assert info is None

    def test_get_role_pages(self):
        pages = get_role_pages(UserRole.MANAGER)
        assert "primary" in pages
        assert "secondary" in pages
        assert 14 in pages["primary"]  # Executive Dashboard

    def test_get_role_kpis(self):
        kpis = get_role_kpis(UserRole.RELIABILITY_ENGINEER)
        assert len(kpis) > 0
        keys = [k["key"] for k in kpis]
        assert "mtbf" in keys

    def test_get_role_quick_actions(self):
        actions = get_role_quick_actions(UserRole.PLANNER)
        assert len(actions) > 0

    def test_is_primary_page_true(self):
        assert is_primary_page(UserRole.MANAGER, 14) is True

    def test_is_primary_page_false(self):
        assert is_primary_page(UserRole.TECHNICIAN, 14) is False

    def test_is_relevant_page_primary(self):
        assert is_relevant_page(UserRole.MANAGER, 14) is True

    def test_is_relevant_page_secondary(self):
        assert is_relevant_page(UserRole.MANAGER, 1) is True  # Hierarchy is secondary for Manager

    def test_is_relevant_page_neither(self):
        # Find a page that's not in Manager's primary or secondary
        manager_pages = ROLE_PAGE_MAP[UserRole.MANAGER]
        all_manager = set(manager_pages["primary"] + manager_pages["secondary"])
        irrelevant = VALID_PAGE_NUMBERS - all_manager
        if irrelevant:
            page = next(iter(irrelevant))
            assert is_relevant_page(UserRole.MANAGER, page) is False
