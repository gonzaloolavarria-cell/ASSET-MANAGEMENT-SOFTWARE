"""Page 25: Expert Portal — GAP-W13.

Token-based consultation portal for retired experts.
Simple, mobile-friendly interface: see fault context, submit guidance.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Expert Portal", page_icon="🧑‍🔬", layout="wide")

try:
    from streamlit_app.i18n import page_init, t as _t
    page_init()
except Exception:
    _t = lambda key, **kw: key.split(".")[-1]

try:
    from streamlit_app.components.role_banner import role_context_banner
    role_context_banner(25)
except Exception:
    pass

try:
    from streamlit_app import api_client
    _BACKEND_OK = True
except ImportError as exc:
    _BACKEND_OK = False
    _IMPORT_ERROR = str(exc)


# ── FM code options for multi-select ─────────────────────────────────

FM_CODE_OPTIONS = [f"FM-{i:02d}" for i in range(1, 73)]

CONFIDENCE_COLORS = {
    "high": "#4CAF50",
    "medium": "#FF9800",
    "low": "#F44336",
}


def _confidence_bar(conf: float) -> str:
    if conf >= 0.8:
        color = CONFIDENCE_COLORS["high"]
    elif conf >= 0.5:
        color = CONFIDENCE_COLORS["medium"]
    else:
        color = CONFIDENCE_COLORS["low"]
    pct = int(conf * 100)
    return (
        f'<div style="background:#eee;border-radius:4px;height:20px;width:100%">'
        f'<div style="background:{color};border-radius:4px;height:20px;width:{pct}%;'
        f'text-align:center;color:white;font-size:0.75em;line-height:20px">'
        f'{pct}%</div></div>'
    )


# ═════════════════════════════════════════════════════════════════════
# Token extraction
# ═════════════════════════════════════════════════════════════════════

st.title(_t("expert_portal.title"))
st.caption(_t("expert_portal.subtitle"))

if not _BACKEND_OK:
    st.error(f"Backend modules unavailable: {_IMPORT_ERROR}")
    st.stop()

# Get token from URL query params or manual input
token = st.query_params.get("token", "")

if not token:
    st.info(_t("expert_portal.enter_token"))
    token = st.text_input(_t("expert_portal.token_label"), key="portal_token_input")

if not token:
    st.warning(_t("expert_portal.no_token"))
    st.stop()


# ═════════════════════════════════════════════════════════════════════
# Load consultation via token
# ═════════════════════════════════════════════════════════════════════

try:
    consultation = api_client.get_portal_consultation(token)
except Exception as exc:
    error_msg = str(exc)
    if "403" in error_msg:
        st.error(_t("expert_portal.token_expired"))
    elif "404" in error_msg:
        st.error(_t("expert_portal.invalid_token"))
    else:
        st.error(_t("common.error", error=error_msg))
    st.stop()


# Mark as viewed
consultation_id = consultation.get("consultation_id", "")
status = consultation.get("status", "")

if status == "REQUESTED":
    try:
        api_client.mark_consultation_viewed(consultation_id)
    except Exception:
        pass


# ═════════════════════════════════════════════════════════════════════
# Already responded guard
# ═════════════════════════════════════════════════════════════════════

if status in ("RESPONDED", "CLOSED"):
    st.success(_t("expert_portal.already_responded"))
    st.balloons()
    resp_time = consultation.get("response_time_minutes")
    if resp_time:
        st.info(_t("expert_portal.response_time", minutes=resp_time))
    st.stop()


# ═════════════════════════════════════════════════════════════════════
# Consultation context + Response form
# ═════════════════════════════════════════════════════════════════════

col_context, col_response = st.columns([1, 1])

# ── Left: Consultation context ──

with col_context:
    st.subheader(_t("expert_portal.context_title"))

    # Equipment info
    st.markdown(f"**{_t('expert_portal.equipment')}:** {consultation.get('equipment_type_id', '')} "
                f"({consultation.get('equipment_tag', '')})")
    st.markdown(f"**{_t('expert_portal.plant')}:** {consultation.get('plant_id', '')}")
    st.markdown(f"**{_t('expert_portal.requested_at')}:** {consultation.get('requested_at', '')}")

    st.divider()

    # Reported symptoms
    st.markdown(f"### {_t('expert_portal.reported_symptoms')}")
    symptoms = consultation.get("symptoms_snapshot", [])
    if isinstance(symptoms, list):
        for sym in symptoms:
            if isinstance(sym, dict):
                cat = sym.get("category", "")
                desc = sym.get("description", "")
                sev = sym.get("severity", "")
                st.markdown(f"- **[{cat}]** {desc} ({sev})")
            else:
                st.markdown(f"- {sym}")
    elif symptoms:
        st.markdown(str(symptoms))
    else:
        st.caption(_t("expert_portal.no_symptoms"))

    st.divider()

    # AI suggestion / candidates
    st.markdown(f"### {_t('expert_portal.ai_suggestion')}")
    ai_text = consultation.get("ai_suggestion", "")
    if ai_text:
        st.markdown(ai_text)

    candidates = consultation.get("candidates_snapshot", [])
    if isinstance(candidates, list):
        for cand in candidates:
            if isinstance(cand, dict):
                fm = cand.get("fm_code", "")
                desc = cand.get("description", cand.get("mechanism", ""))
                conf = cand.get("confidence", 0.0)
                st.markdown(f"**{fm}** — {desc}")
                st.markdown(_confidence_bar(conf), unsafe_allow_html=True)
    elif candidates:
        st.markdown(str(candidates))


# ── Right: Response form ──

with col_response:
    st.subheader(_t("expert_portal.guidance_title"))

    with st.form("expert_response_form"):
        guidance = st.text_area(
            _t("expert_portal.guidance_label"),
            placeholder=_t("expert_portal.guidance_placeholder"),
            height=200,
        )

        fm_codes = st.multiselect(
            _t("expert_portal.fm_codes_label"),
            FM_CODE_OPTIONS,
            help=_t("expert_portal.fm_codes_help"),
        )

        confidence = st.slider(
            _t("expert_portal.confidence_label"),
            min_value=0.0,
            max_value=1.0,
            value=0.7,
            step=0.05,
        )

        submitted = st.form_submit_button(
            _t("expert_portal.submit_guidance"),
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not guidance.strip():
            st.warning(_t("expert_portal.guidance_required"))
        else:
            try:
                api_client.submit_expert_response(consultation_id, {
                    "expert_guidance": guidance.strip(),
                    "fm_codes": fm_codes,
                    "confidence": confidence,
                })
                st.success(_t("expert_portal.thank_you"))
                st.markdown(_t("expert_portal.thank_you_detail"))
                st.balloons()
            except Exception as exc:
                st.error(_t("common.error", error=str(exc)))
