"""Expert escalation widget for troubleshooting pages — GAP-W13.

Renders an 'Escalate to Expert' section when AI candidates are low-confidence.
"""

from __future__ import annotations

import streamlit as st
from streamlit_app.i18n import t


def expert_escalation_widget(session_data: dict) -> dict | None:
    """Render expert escalation UI.

    Shows when all candidates < 0.5 confidence after 3+ tests, or on-demand.
    Returns the created consultation dict if escalation is triggered, else None.

    Args:
        session_data: Current troubleshooting session dict from API.
    """
    candidates = session_data.get("candidate_diagnoses", [])
    tests = session_data.get("tests_performed", [])
    max_conf = max((c.get("confidence", 0.0) for c in candidates), default=0.0)

    # Auto-suggest when conditions met
    auto_suggest = len(tests) >= 3 and max_conf < 0.5 and len(candidates) > 0

    if auto_suggest:
        st.warning(t("expert_knowledge.escalation_auto_hint"))

    with st.expander(t("expert_knowledge.escalate_to_expert"), expanded=auto_suggest):
        st.caption(t("expert_knowledge.escalation_description"))

        try:
            from streamlit_app import api_client

            experts = api_client.list_experts(retired_only=True)
            if not experts:
                st.info(t("expert_knowledge.no_experts_available"))
                return None

            # Show top experts
            expert_options = {
                e.get("expert_id", ""): (
                    f"{e.get('name', '')} — "
                    f"{', '.join(e.get('domains', [])[:2])} — "
                    f"{e.get('years_experience', 0)}y exp"
                )
                for e in experts[:5]
            }

            selected_id = st.selectbox(
                t("expert_knowledge.select_expert"),
                list(expert_options.keys()),
                format_func=lambda eid: expert_options[eid],
                key="escalation_expert_select",
            )

            language = st.selectbox(
                t("expert_knowledge.preferred_language"),
                ["fr", "en", "es", "ar"],
                format_func=lambda l: {"fr": "Français", "en": "English", "es": "Español", "ar": "العربية"}[l],
                key="escalation_lang_select",
            )

            if st.button(t("expert_knowledge.send_consultation"), key="escalate_btn", type="primary"):
                try:
                    # Build AI suggestion summary
                    ai_summary = ""
                    if candidates:
                        lines = []
                        for c in candidates[:3]:
                            fm = c.get("fm_code", "")
                            desc = c.get("description", c.get("mechanism", ""))
                            conf = c.get("confidence", 0.0)
                            lines.append(f"{fm}: {desc} ({int(conf*100)}%)")
                        ai_summary = "\n".join(lines)

                    result = api_client.create_consultation({
                        "session": session_data,
                        "expert_id": selected_id,
                        "ai_suggestion": ai_summary,
                        "language": language,
                    })
                    st.success(t("expert_knowledge.expert_notified"))
                    return result
                except Exception as exc:
                    st.error(f"Error: {exc}")
                    return None

        except ImportError:
            st.error("Backend modules unavailable")
            return None

    return None
