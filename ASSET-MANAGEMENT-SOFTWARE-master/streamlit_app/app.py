"""OCP Maintenance AI MVP — Streamlit Dashboard.

Launch: streamlit run streamlit_app/app.py
Requires: FastAPI backend running at http://localhost:8000
"""

import streamlit as st
from streamlit_app.i18n import init_language, language_switcher, role_selector, apply_rtl, t
from streamlit_app.style import apply_style
from streamlit_app.role_config import (
    ROLE_DESCRIPTIONS, ROLE_ICONS, ROLE_DISPLAY_NAMES,
    get_role_pages, get_role_quick_actions, get_page_info, DEFAULT_ROLE,
)

st.set_page_config(
    page_title="OCP Maintenance AI",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_language()
if "user_role" not in st.session_state:
    st.session_state.user_role = DEFAULT_ROLE
apply_rtl()
apply_style()
language_switcher()
role_selector()

st.title(t("common.app_title"))
st.markdown(t("common.app_subtitle"))

# --- Role-aware landing page ---
role = st.session_state.get("user_role", DEFAULT_ROLE)
icon = ROLE_ICONS.get(role, "")
role_name = t(ROLE_DISPLAY_NAMES[role])
role_desc = t(ROLE_DESCRIPTIONS[role])

st.markdown(f"### {icon} {role_name}")
st.caption(role_desc)

pages = get_role_pages(role)
actions = get_role_quick_actions(role)

# Quick Actions
if actions:
    st.markdown(f"#### {t('role.primary_pages')}")
    cols = st.columns(min(len(actions), 4))
    for i, action in enumerate(actions):
        with cols[i % len(cols)]:
            page_info = get_page_info(action["page"])
            if page_info:
                page_path = f"pages/{page_info['file']}"
                st.page_link(page_path, label=t(action["label_key"]), icon="▶️")

# Primary pages grid
primary = pages.get("primary", [])
if primary:
    cols = st.columns(min(len(primary), 4))
    for i, page_num in enumerate(primary):
        info = get_page_info(page_num)
        if info:
            with cols[i % min(len(primary), 4)]:
                page_title = t(info["i18n_key"])
                page_path = f"pages/{info['file']}"
                st.page_link(page_path, label=f"**{page_title}**", icon="📄")
                st.caption(info["milestone"])

# Secondary pages
secondary = pages.get("secondary", [])
if secondary:
    with st.expander(t("role.secondary_pages")):
        cols = st.columns(min(len(secondary), 4))
        for i, page_num in enumerate(secondary):
            info = get_page_info(page_num)
            if info:
                with cols[i % min(len(secondary), 4)]:
                    page_title = t(info["i18n_key"])
                    page_path = f"pages/{info['file']}"
                    st.page_link(page_path, label=page_title)

# Full modules table (discoverability)
with st.expander(t("role.all_pages")):
    st.markdown(t("home.modules_table"))

st.markdown(t("home.getting_started"))
st.markdown(t("home.safety_first"))

# Quick status check
try:
    from streamlit_app import api_client
    stats = api_client.get_stats()
    st.sidebar.success(t("common.api_connected", nodes=stats.get("total_nodes", 0)))
except Exception:
    st.sidebar.error(t("common.api_not_connected"))
