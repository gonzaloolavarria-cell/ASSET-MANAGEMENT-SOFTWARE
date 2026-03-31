"""Tests for role_selector() integration — GAP-W05."""

import pytest
from unittest.mock import MagicMock, patch
from streamlit_app.role_config import UserRole, DEFAULT_ROLE


class _SessionStateMock(dict):
    """Dict subclass that supports attribute access like Streamlit session_state."""
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)
    def __setattr__(self, key, value):
        self[key] = value
    def __delattr__(self, key):
        del self[key]


class TestRoleSelectorInit:
    """Test that _init_role() initializes session state correctly."""

    @patch("streamlit_app.i18n.st")
    def test_init_role_sets_default(self, mock_st):
        """_init_role() should set user_role to DEFAULT_ROLE when missing."""
        mock_st.session_state = _SessionStateMock()
        from streamlit_app.i18n import _init_role
        _init_role()
        assert mock_st.session_state["user_role"] == DEFAULT_ROLE

    @patch("streamlit_app.i18n.st")
    def test_init_role_preserves_existing(self, mock_st):
        """_init_role() should not overwrite an existing user_role."""
        mock_st.session_state = _SessionStateMock({"user_role": UserRole.MANAGER})
        from streamlit_app.i18n import _init_role
        _init_role()
        assert mock_st.session_state["user_role"] == UserRole.MANAGER

    @patch("streamlit_app.i18n.st")
    def test_default_role_is_consultant(self, mock_st):
        """Default role should be CONSULTANT per workshop decision."""
        mock_st.session_state = _SessionStateMock()
        from streamlit_app.i18n import _init_role
        _init_role()
        assert mock_st.session_state["user_role"] == UserRole.CONSULTANT


class TestRoleSelectorImport:
    """Test that role_selector is importable and callable."""

    def test_role_selector_importable(self):
        from streamlit_app.i18n import role_selector
        assert callable(role_selector)

    def test_init_role_importable(self):
        from streamlit_app.i18n import _init_role
        assert callable(_init_role)


class TestRoleBannerImport:
    """Test that role_context_banner component is importable."""

    def test_role_banner_importable(self):
        from streamlit_app.components.role_banner import role_context_banner
        assert callable(role_context_banner)


class TestRoleConfigModuleImport:
    """Test that role_config module exports all expected symbols."""

    def test_imports_all_enums(self):
        from streamlit_app.role_config import UserRole, DEFAULT_ROLE
        assert UserRole is not None
        assert DEFAULT_ROLE is not None

    def test_imports_all_maps(self):
        from streamlit_app.role_config import (
            ROLE_DISPLAY_NAMES, ROLE_DESCRIPTIONS, ROLE_ICONS,
            PAGE_REGISTRY, ROLE_PAGE_MAP, ROLE_KPIS, ROLE_QUICK_ACTIONS,
        )
        assert all(v is not None for v in [
            ROLE_DISPLAY_NAMES, ROLE_DESCRIPTIONS, ROLE_ICONS,
            PAGE_REGISTRY, ROLE_PAGE_MAP, ROLE_KPIS, ROLE_QUICK_ACTIONS,
        ])

    def test_imports_all_helpers(self):
        from streamlit_app.role_config import (
            get_page_info, get_role_pages, get_role_kpis,
            get_role_quick_actions, is_primary_page, is_relevant_page,
        )
        assert all(callable(f) for f in [
            get_page_info, get_role_pages, get_role_kpis,
            get_role_quick_actions, is_primary_page, is_relevant_page,
        ])
