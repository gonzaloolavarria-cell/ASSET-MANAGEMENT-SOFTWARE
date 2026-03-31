"""Role context banner for Streamlit pages.

Shows a subtle hint when the current page is not in the user's primary tools.
Add `role_context_banner(N)` to each page after `apply_style()`.
"""

import streamlit as st
from streamlit_app.i18n import t
from streamlit_app.role_config import (
    is_primary_page, ROLE_DISPLAY_NAMES, DEFAULT_ROLE,
)


def role_context_banner(page_number: int):
    """Show subtle caption if this page is not primary for the user's role."""
    role = st.session_state.get("user_role", DEFAULT_ROLE)
    if not is_primary_page(role, page_number):
        role_name = t(ROLE_DISPLAY_NAMES.get(role, "role.consultant"))
        st.caption(t("role.not_primary_hint", role=role_name))
