"""Page 26: Expert Knowledge Management — GAP-W13.

4-tab management interface:
  Tab 1 — Expert Directory (active + retired experts, stats)
  Tab 2 — Active Consultations (status tracking, reassign/cancel)
  Tab 3 — Knowledge Pipeline (RAW → VALIDATED → PROMOTED)
  Tab 4 — Compensation (monthly summaries, approve/pay)
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Expert Knowledge", page_icon="🧠", layout="wide")

try:
    from streamlit_app.i18n import page_init, t as _t
    page_init()
except Exception:
    _t = lambda key, **kw: key.split(".")[-1]

try:
    from streamlit_app.components.role_banner import role_context_banner
    role_context_banner(26)
except Exception:
    pass

try:
    from streamlit_app import api_client
    _BACKEND_OK = True
except ImportError as exc:
    _BACKEND_OK = False
    _IMPORT_ERROR = str(exc)


# ── Constants ────────────────────────────────────────────────────────

FM_CODE_OPTIONS = [f"FM-{i:02d}" for i in range(1, 73)]

STATUS_COLORS = {
    "REQUESTED": "🟡",
    "VIEWED": "🔵",
    "IN_PROGRESS": "🔵",
    "RESPONDED": "🟢",
    "CLOSED": "⚫",
    "EXPIRED": "🔴",
    "CANCELLED": "🔴",
    "RAW": "🟡",
    "VALIDATED": "🔵",
    "PROMOTED": "🟢",
    "REJECTED": "🔴",
}


# ═════════════════════════════════════════════════════════════════════
# Header
# ═════════════════════════════════════════════════════════════════════

st.title(_t("expert_knowledge.title"))
st.caption(_t("expert_knowledge.subtitle"))

if not _BACKEND_OK:
    st.error(f"Backend modules unavailable: {_IMPORT_ERROR}")
    st.stop()


# ═════════════════════════════════════════════════════════════════════
# Tabs
# ═════════════════════════════════════════════════════════════════════

tab_dir, tab_consult, tab_pipeline, tab_comp = st.tabs([
    _t("expert_knowledge.tab_directory"),
    _t("expert_knowledge.tab_consultations"),
    _t("expert_knowledge.tab_pipeline"),
    _t("expert_knowledge.tab_compensation"),
])


# ═════════════════════════════════════════════════════════════════════
# Tab 1: Expert Directory
# ═════════════════════════════════════════════════════════════════════

with tab_dir:
    st.subheader(_t("expert_knowledge.tab_directory"))

    col_filter, col_add = st.columns([3, 1])
    show_retired = col_filter.checkbox(_t("expert_knowledge.show_retired_only"), value=False)

    try:
        experts = api_client.list_experts(retired_only=show_retired)
    except Exception as exc:
        experts = []
        st.warning(_t("common.error", error=str(exc)))

    if experts:
        rows = []
        for e in experts:
            rows.append({
                _t("expert_knowledge.col_name"): e.get("name", ""),
                _t("expert_knowledge.col_domains"): ", ".join(e.get("domains", [])),
                _t("expert_knowledge.col_equipment"): ", ".join(e.get("equipment_expertise", [])[:3]),
                _t("expert_knowledge.col_experience"): e.get("years_experience", 0),
                _t("expert_knowledge.col_resolutions"): e.get("resolution_count", 0),
                _t("expert_knowledge.col_retired"): "Yes" if e.get("is_retired") else "No",
                _t("expert_knowledge.col_rate"): f"${e.get('hourly_rate_usd', 50)}/h",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info(_t("common.no_data_available"))

    # Add expert form
    with col_add:
        if st.button(_t("expert_knowledge.add_expert"), use_container_width=True):
            st.session_state["show_add_expert"] = True

    if st.session_state.get("show_add_expert"):
        with st.form("add_expert_form"):
            st.markdown(f"### {_t('expert_knowledge.add_expert')}")
            name = st.text_input(_t("expert_knowledge.expert_name"))
            domains = st.multiselect(_t("expert_knowledge.col_domains"),
                                     ["RELIABILITY", "MECHANICAL", "ELECTRICAL", "INSTRUMENTATION",
                                      "PROCESS", "WELDING", "HYDRAULIC", "LUBRICATION"])
            equipment = st.text_input(_t("expert_knowledge.col_equipment"),
                                      help="Comma-separated equipment type IDs")
            years = st.number_input(_t("expert_knowledge.col_experience"), min_value=0, max_value=50, value=15)
            languages = st.multiselect(_t("expert_knowledge.languages"), ["FR", "EN", "ES", "AR"], default=["FR"])
            is_retired = st.checkbox(_t("expert_knowledge.col_retired"), value=True)
            hourly_rate = st.number_input(_t("expert_knowledge.col_rate"), min_value=0.0, value=50.0, step=5.0)

            if st.form_submit_button(_t("common.submit")):
                try:
                    eq_list = [e.strip() for e in equipment.split(",") if e.strip()]
                    api_client.register_expert({
                        "name": name,
                        "domains": domains,
                        "equipment_expertise": eq_list,
                        "years_experience": years,
                        "languages": languages,
                        "is_retired": is_retired,
                        "hourly_rate_usd": hourly_rate,
                    })
                    st.success(_t("expert_knowledge.expert_registered"))
                    st.session_state["show_add_expert"] = False
                    st.rerun()
                except Exception as exc:
                    st.error(_t("common.error", error=str(exc)))


# ═════════════════════════════════════════════════════════════════════
# Tab 2: Active Consultations
# ═════════════════════════════════════════════════════════════════════

with tab_consult:
    st.subheader(_t("expert_knowledge.tab_consultations"))

    col_f1, col_f2 = st.columns(2)
    filter_status = col_f1.selectbox(
        _t("common.filter_by_status"),
        ["", "REQUESTED", "VIEWED", "IN_PROGRESS", "RESPONDED", "CLOSED", "EXPIRED"],
        key="consult_status_filter",
    )
    filter_expert = col_f2.text_input(_t("expert_knowledge.filter_expert_id"), key="consult_expert_filter")

    try:
        params = {}
        if filter_status:
            params["status"] = filter_status
        if filter_expert:
            params["expert_id"] = filter_expert
        consultations = api_client.list_consultations(**params)
    except Exception as exc:
        consultations = []
        st.warning(_t("common.error", error=str(exc)))

    if consultations:
        for c in consultations:
            cid = c.get("consultation_id", "")
            cstatus = c.get("status", "")
            icon = STATUS_COLORS.get(cstatus, "")

            with st.expander(f"{icon} {cid} — {c.get('equipment_type_id', '')} [{cstatus}]"):
                col1, col2, col3 = st.columns(3)
                col1.markdown(f"**Expert:** {c.get('expert_id', '')}")
                col2.markdown(f"**Plant:** {c.get('plant_id', '')}")
                col3.markdown(f"**Requested:** {c.get('requested_at', '')}")

                if c.get("expert_guidance"):
                    st.markdown(f"**{_t('expert_portal.guidance_title')}:** {c['expert_guidance'][:200]}...")

                col_a1, col_a2 = st.columns(2)
                if cstatus == "RESPONDED":
                    if col_a1.button(_t("expert_knowledge.close_consultation"), key=f"close_{cid}"):
                        try:
                            api_client.close_consultation(cid)
                            st.toast(_t("expert_knowledge.consultation_closed"))
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))

                    if col_a2.button(_t("expert_knowledge.create_contribution"), key=f"contrib_{cid}"):
                        try:
                            api_client.create_contribution(cid)
                            st.toast(_t("expert_knowledge.contribution_created"))
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))
    else:
        st.info(_t("common.no_data_available"))


# ═════════════════════════════════════════════════════════════════════
# Tab 3: Knowledge Pipeline (RAW → VALIDATED → PROMOTED)
# ═════════════════════════════════════════════════════════════════════

with tab_pipeline:
    st.subheader(_t("expert_knowledge.tab_pipeline"))

    col_raw, col_val, col_prom = st.columns(3)

    try:
        all_contributions = api_client.list_contributions()
    except Exception:
        all_contributions = []

    raw = [c for c in all_contributions if c.get("status") == "RAW"]
    validated = [c for c in all_contributions if c.get("status") == "VALIDATED"]
    promoted = [c for c in all_contributions if c.get("status") == "PROMOTED"]

    # RAW column
    with col_raw:
        st.markdown(f"### {STATUS_COLORS.get('RAW', '')} RAW ({len(raw)})")
        for c in raw:
            cid = c.get("contribution_id", "")
            with st.container(border=True):
                st.markdown(f"**{cid[:12]}...**")
                st.caption(f"Expert: {c.get('expert_id', '')}")
                st.caption(f"Equipment: {c.get('equipment_type_id', '')}")
                fm_list = c.get("fm_codes", [])
                if fm_list:
                    st.caption(f"FM: {', '.join(fm_list[:3])}")

                # Validate action
                with st.form(f"validate_{cid}"):
                    validated_by = st.text_input("Validated by", key=f"vby_{cid}")
                    new_fm = st.multiselect("FM Codes", FM_CODE_OPTIONS, default=fm_list, key=f"vfm_{cid}")
                    if st.form_submit_button(_t("expert_knowledge.validate_contribution")):
                        try:
                            api_client.validate_contribution(cid, {
                                "fm_codes": new_fm,
                                "validated_by": validated_by,
                            })
                            st.toast(_t("expert_knowledge.contribution_validated"))
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))

    # VALIDATED column
    with col_val:
        st.markdown(f"### {STATUS_COLORS.get('VALIDATED', '')} VALIDATED ({len(validated)})")
        for c in validated:
            cid = c.get("contribution_id", "")
            with st.container(border=True):
                st.markdown(f"**{cid[:12]}...**")
                st.caption(f"Expert: {c.get('expert_id', '')}")
                st.caption(f"FM: {', '.join(c.get('fm_codes', []))}")

                targets = st.multiselect(
                    _t("expert_knowledge.promote_targets"),
                    ["symptom-catalog", "decision-tree", "manual", "memory"],
                    default=["symptom-catalog", "manual"],
                    key=f"targets_{cid}",
                )

                if st.button(_t("expert_knowledge.promote_contribution"), key=f"promote_{cid}"):
                    try:
                        api_client.promote_contribution(cid, {"targets": targets})
                        st.toast(_t("expert_knowledge.contribution_promoted"))
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

    # PROMOTED column
    with col_prom:
        st.markdown(f"### {STATUS_COLORS.get('PROMOTED', '')} PROMOTED ({len(promoted)})")
        for c in promoted:
            cid = c.get("contribution_id", "")
            with st.container(border=True):
                st.markdown(f"**{cid[:12]}...**")
                st.caption(f"Expert: {c.get('expert_id', '')}")
                targets = c.get("promoted_targets", [])
                if targets:
                    st.caption(f"Targets: {', '.join(targets)}")
                st.caption(f"Promoted: {c.get('promoted_at', '')}")


# ═════════════════════════════════════════════════════════════════════
# Tab 4: Compensation
# ═════════════════════════════════════════════════════════════════════

with tab_comp:
    st.subheader(_t("expert_knowledge.tab_compensation"))

    try:
        experts = api_client.list_experts(retired_only=True)
    except Exception:
        experts = []

    if not experts:
        st.info(_t("expert_knowledge.no_retired_experts"))
    else:
        for e in experts:
            eid = e.get("expert_id", "")
            name = e.get("name", eid)

            with st.expander(f"{name} — ${e.get('hourly_rate_usd', 50)}/h"):
                try:
                    comp = api_client.get_expert_compensation(eid)
                except Exception:
                    comp = {}

                col1, col2, col3 = st.columns(3)
                col1.metric(
                    _t("expert_knowledge.total_consultations"),
                    comp.get("total_consultations", 0),
                )
                col2.metric(
                    _t("expert_knowledge.total_minutes"),
                    comp.get("total_response_minutes", 0),
                )
                col3.metric(
                    _t("expert_knowledge.total_due"),
                    f"${comp.get('total_due_usd', 0):.2f}",
                )

                comp_status = comp.get("status", "PENDING")
                st.markdown(f"**{_t('common.status')}:** {comp_status}")
