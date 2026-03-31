"""Page 23: Troubleshooting Assistant — GAP-W02.

Guided diagnostic workflow: equipment selection, symptom input,
candidate diagnosis, test recording, finalization, and feedback.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Troubleshooting", page_icon="🔍", layout="wide")

try:
    from streamlit_app.i18n import page_init, t as _t
    page_init()
except Exception:
    _t = lambda key, **kw: key.split(".")[-1]

try:
    from streamlit_app.components.role_banner import role_context_banner
    role_context_banner(23)
except Exception:
    pass

try:
    from streamlit_app import api_client
    _BACKEND_OK = True
except ImportError as exc:
    _BACKEND_OK = False
    _IMPORT_ERROR = str(exc)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EQUIPMENT_TYPES = [
    ("ET-SAG-MILL", "SAG Mill"),
    ("ET-BALL-MILL", "Ball Mill"),
    ("ET-ROD-MILL", "Rod Mill"),
    ("ET-SLURRY-PUMP", "Slurry Pump"),
    ("ET-FLOTATION-CELL", "Flotation Cell"),
    ("ET-BELT-CONVEYOR", "Belt Conveyor"),
    ("ET-THICKENER", "Thickener"),
    ("ET-BELT-FILTER", "Belt Filter"),
    ("ET-ROTARY-DRYER", "Rotary Dryer"),
    ("ET-CRUSHER", "Crusher"),
    ("ET-SCREEN", "Vibrating Screen"),
    ("ET-CYCLONE", "Hydrocyclone"),
    ("ET-AGITATOR", "Agitator"),
    ("ET-COMPRESSOR", "Compressor"),
    ("ET-HEAT-EXCHANGER", "Heat Exchanger"),
]

SYMPTOM_CATEGORIES = [
    "vibration", "temperature", "noise", "performance", "electrical",
    "leak", "pressure", "flow", "visual", "contamination", "alignment",
]

SEVERITY_OPTIONS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

CONFIDENCE_COLORS = {
    "high": "#4CAF50",
    "medium": "#FF9800",
    "low": "#F44336",
}


def _confidence_level(conf: float) -> str:
    if conf >= 0.8:
        return "high"
    if conf >= 0.5:
        return "medium"
    return "low"


def _confidence_bar(conf: float) -> str:
    level = _confidence_level(conf)
    color = CONFIDENCE_COLORS[level]
    pct = int(conf * 100)
    return (
        f'<div style="background:#eee;border-radius:4px;height:20px;width:100%">'
        f'<div style="background:{color};border-radius:4px;height:20px;width:{pct}%;'
        f'text-align:center;color:white;font-size:0.75em;line-height:20px">'
        f'{pct}%</div></div>'
    )


# ═══════════════════════════════════════════════════════════════════════════
# Page header
# ═══════════════════════════════════════════════════════════════════════════

st.title(_t("troubleshooting.title"))
st.caption(_t("troubleshooting.subtitle"))

if not _BACKEND_OK:
    st.error(f"Backend modules unavailable: {_IMPORT_ERROR}")
    st.stop()


# ═══════════════════════════════════════════════════════════════════════════
# Tabs
# ═══════════════════════════════════════════════════════════════════════════

tab_new, tab_history, tab_trees = st.tabs([
    _t("troubleshooting.tab_new"),
    _t("troubleshooting.tab_history"),
    _t("troubleshooting.tab_trees"),
])


# ═══════════════════════════════════════════════════════════════════════════
# Tab 1: New Diagnosis
# ═══════════════════════════════════════════════════════════════════════════

with tab_new:

    # ── Step 1: Equipment selection & session creation ──

    if "ts_session" not in st.session_state:
        st.subheader("Step 1: Select Equipment")
        with st.form("create_session_form"):
            eq_idx = st.selectbox(
                _t("troubleshooting.select_equipment_type"),
                range(len(EQUIPMENT_TYPES)),
                format_func=lambda i: f"{EQUIPMENT_TYPES[i][0]} — {EQUIPMENT_TYPES[i][1]}",
            )
            eq_tag = st.text_input(_t("troubleshooting.equipment_tag"))
            tech_id = st.text_input(_t("troubleshooting.technician_id"))
            submitted = st.form_submit_button(_t("troubleshooting.start_session"))

        if submitted:
            try:
                eq_type_id = EQUIPMENT_TYPES[eq_idx][0]
                result = api_client.create_troubleshooting_session(
                    equipment_type_id=eq_type_id,
                    equipment_tag=eq_tag,
                    technician_id=tech_id,
                )
                st.session_state["ts_session"] = result
                st.success(_t("troubleshooting.session_started", session_id=result["session_id"]))
                st.rerun()
            except Exception as exc:
                st.error(f"Error: {exc}")
        st.stop()

    session = st.session_state["ts_session"]
    sid = session["session_id"]
    status = session.get("status", "IN_PROGRESS")

    # Header with session info
    col_h1, col_h2, col_h3 = st.columns([3, 1, 1])
    col_h1.subheader(f"{session.get('equipment_type_id', '')} — {sid}")
    col_h2.metric("Status", status)
    n_symptoms = len(session.get("symptoms", []))
    col_h3.metric("Symptoms", n_symptoms)

    if st.button("New Session", key="new_session_btn"):
        del st.session_state["ts_session"]
        st.rerun()

    st.divider()

    # ── Step 2: Add symptoms ──

    if status == "IN_PROGRESS":
        st.subheader("Step 2: Describe Symptoms")

        with st.form("add_symptom_form"):
            description = st.text_area(
                _t("troubleshooting.symptom_description"),
                placeholder="e.g. Excessive vibration from drive end bearing",
            )
            col_s1, col_s2 = st.columns(2)
            category = col_s1.selectbox(
                _t("troubleshooting.symptom_category"),
                SYMPTOM_CATEGORIES,
            )
            severity = col_s2.selectbox(
                _t("troubleshooting.symptom_severity"),
                SEVERITY_OPTIONS,
                index=1,
            )
            add_btn = st.form_submit_button(_t("troubleshooting.add_symptom"))

        if add_btn and description:
            try:
                result = api_client.add_troubleshooting_symptom(
                    sid, description, category, severity,
                )
                st.session_state["ts_session"] = result
                st.toast(_t("troubleshooting.symptom_added"))
                st.rerun()
            except Exception as exc:
                st.error(f"Error: {exc}")

        # Show current symptoms
        symptoms = session.get("symptoms", [])
        if symptoms:
            with st.expander(f"Current Symptoms ({len(symptoms)})", expanded=True):
                for sym in symptoms:
                    sev = sym.get("severity", "MEDIUM")
                    sev_color = {"LOW": "blue", "MEDIUM": "orange", "HIGH": "red", "CRITICAL": "red"}.get(sev, "gray")
                    st.markdown(
                        f"- **[{sym.get('category', '')}]** {sym.get('description', '')} "
                        f"(:{sev_color}[{sev}])"
                    )

        st.divider()

        # ── Step 3: Candidate diagnoses ──

        candidates = session.get("candidate_diagnoses", [])
        if candidates:
            st.subheader("Step 3: " + _t("troubleshooting.candidate_diagnoses"))

            for i, cand in enumerate(candidates):
                conf = cand.get("confidence", 0.0)
                fm_code = cand.get("fm_code", "")
                mechanism = cand.get("mechanism", "")
                cause = cand.get("cause", "")

                with st.container():
                    c1, c2 = st.columns([3, 1])
                    c1.markdown(f"**{fm_code}** — {mechanism} / {cause}")
                    c2.markdown(_confidence_bar(conf), unsafe_allow_html=True)

                    # Show matched symptoms and recommended tests
                    matched = cand.get("matched_symptoms", [])
                    if matched:
                        st.caption(f"Matched: {', '.join(matched[:3])}")

                    rec_tests = cand.get("recommended_tests", [])
                    if rec_tests:
                        st.caption(f"Recommended: {', '.join(t.get('test_type', '') for t in rec_tests[:2])}")

                    st.markdown("---")

        st.divider()

        # ── Step 4: Record test results ──

        st.subheader("Step 4: " + _t("troubleshooting.record_test"))

        with st.form("record_test_form"):
            test_id = st.text_input("Test ID", placeholder="e.g. TST-VIB-001")
            col_t1, col_t2 = st.columns(2)
            test_result = col_t1.selectbox(
                _t("troubleshooting.test_result"),
                ["NORMAL", "ABNORMAL", "INCONCLUSIVE"],
            )
            measured = col_t2.text_input("Measured Value", placeholder="e.g. 12.5 mm/s RMS")
            record_btn = st.form_submit_button(_t("troubleshooting.record_test"))

        if record_btn and test_id:
            try:
                result = api_client.record_troubleshooting_test(
                    sid, test_id, test_result, measured,
                )
                st.session_state["ts_session"] = result
                st.toast(_t("troubleshooting.test_recorded"))
                st.rerun()
            except Exception as exc:
                st.error(f"Error: {exc}")

        # Show performed tests
        tests = session.get("tests_performed", [])
        if tests:
            with st.expander(f"Tests Performed ({len(tests)})"):
                for t in tests:
                    result_icon = {"NORMAL": "✅", "ABNORMAL": "⚠️", "INCONCLUSIVE": "❓"}.get(
                        t.get("result", ""), ""
                    )
                    st.markdown(
                        f"- {result_icon} **{t.get('test_id', '')}** — "
                        f"{t.get('result', '')} ({t.get('measured_value', '')})"
                    )

        st.divider()

        # ── Step 5: Finalize diagnosis ──

        if candidates:
            st.subheader("Step 5: " + _t("troubleshooting.finalize"))
            fm_options = [c.get("fm_code", "") for c in candidates]
            fm_labels = [
                f"{c.get('fm_code', '')} — {c.get('mechanism', '')} / {c.get('cause', '')} "
                f"({int(c.get('confidence', 0) * 100)}%)"
                for c in candidates
            ]
            selected_idx = st.selectbox("Select Final Diagnosis", range(len(fm_options)), format_func=lambda i: fm_labels[i])

            if st.button(_t("troubleshooting.finalize"), key="finalize_btn"):
                try:
                    result = api_client.finalize_troubleshooting(sid, fm_options[selected_idx])
                    st.session_state["ts_session"] = result
                    st.toast(_t("troubleshooting.diagnosis_finalized"))
                    st.rerun()
                except Exception as exc:
                    st.error(f"Error: {exc}")

    # ── Completed session: show final diagnosis + feedback ──

    elif status == "COMPLETED":
        st.success(f"Diagnosis Complete: {session.get('final_fm_code', '')}")

        col_f1, col_f2, col_f3 = st.columns(3)
        col_f1.metric(_t("troubleshooting.mechanism"), session.get("final_mechanism", "—"))
        col_f2.metric(_t("troubleshooting.cause"), session.get("final_cause", "—"))
        conf = session.get("final_confidence")
        col_f3.metric(_t("troubleshooting.confidence"), f"{int(conf * 100)}%" if conf else "—")

        st.divider()

        # Feedback
        if not session.get("actual_cause_feedback"):
            st.subheader(_t("troubleshooting.feedback_label"))
            with st.form("feedback_form"):
                actual_cause = st.text_area(_t("troubleshooting.actual_cause"))
                notes = st.text_area(_t("troubleshooting.feedback_notes"))
                fb_btn = st.form_submit_button(_t("troubleshooting.submit_feedback"))

            if fb_btn and actual_cause:
                try:
                    result = api_client.troubleshooting_feedback(sid, actual_cause, notes)
                    st.session_state["ts_session"] = result
                    st.toast(_t("troubleshooting.feedback_submitted"))
                    st.rerun()
                except Exception as exc:
                    st.error(f"Error: {exc}")
        else:
            st.info(f"Feedback recorded: {session.get('actual_cause_feedback', '')}")


# ═══════════════════════════════════════════════════════════════════════════
# Tab 2: Session History
# ═══════════════════════════════════════════════════════════════════════════

with tab_history:
    st.subheader(_t("troubleshooting.tab_history"))
    st.info(
        "Session history requires a list endpoint. "
        "Use the API directly: `GET /api/v1/troubleshooting/sessions/{session_id}`"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Tab 3: Decision Trees
# ═══════════════════════════════════════════════════════════════════════════

with tab_trees:
    st.subheader(_t("troubleshooting.tree_viewer"))

    col_tree1, col_tree2 = st.columns(2)
    tree_eq_idx = col_tree1.selectbox(
        _t("troubleshooting.select_equipment_type"),
        range(len(EQUIPMENT_TYPES)),
        format_func=lambda i: f"{EQUIPMENT_TYPES[i][0]} — {EQUIPMENT_TYPES[i][1]}",
        key="tree_eq_select",
    )
    tree_cat = col_tree2.selectbox(
        _t("troubleshooting.select_category"),
        [""] + SYMPTOM_CATEGORIES,
        key="tree_cat_select",
    )

    if st.button("Load Tree", key="load_tree_btn"):
        try:
            eq_id = EQUIPMENT_TYPES[tree_eq_idx][0]
            tree = api_client.get_troubleshooting_tree(eq_id, tree_cat)
            st.session_state["ts_tree"] = tree
        except Exception as exc:
            st.warning(_t("troubleshooting.no_tree"))
            st.session_state["ts_tree"] = None

    tree = st.session_state.get("ts_tree")
    if tree:
        nodes = tree.get("nodes", {})
        entry_nodes = tree.get("entry_nodes", {})

        if entry_nodes:
            st.markdown("**Entry Points:**")
            for cat, node_id in entry_nodes.items():
                st.markdown(f"- **{cat}** -> `{node_id}`")

        # Walk through nodes as expandable items
        st.divider()
        st.markdown(f"**Total Nodes:** {len(nodes)}")

        terminal_count = sum(1 for n in nodes.values() if n.get("is_terminal"))
        question_count = len(nodes) - terminal_count
        st.markdown(f"Question nodes: {question_count} | Diagnosis nodes: {terminal_count}")

        with st.expander("Browse Nodes", expanded=False):
            for nid, node in sorted(nodes.items()):
                if node.get("is_terminal"):
                    fm = node.get("terminal_diagnosis", "")
                    mech = node.get("terminal_mechanism", "")
                    cause = node.get("terminal_cause", "")
                    action = node.get("corrective_action", "")
                    st.markdown(
                        f"**`{nid}`** — DIAGNOSIS: **{fm}** ({mech} / {cause})"
                    )
                    if action:
                        st.caption(f"Action: {action[:120]}...")
                else:
                    q = node.get("question", "")
                    st.markdown(f"**`{nid}`** — {q[:120]}")
                    branches = node.get("branches", {})
                    if branches:
                        st.caption(f"Branches: {', '.join(f'{k}->{v}' for k, v in branches.items())}")
