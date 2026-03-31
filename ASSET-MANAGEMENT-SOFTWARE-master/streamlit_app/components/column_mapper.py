"""Column mapping component for data import.

Shows auto-detected source→target mapping with confidence indicators
and manual override dropdowns for unmapped columns.
"""

import streamlit as st
from streamlit_app.i18n import t
from tools.models.schemas import ImportMapping


def column_mapper_widget(
    mapping: ImportMapping,
    key_prefix: str = "colmap",
) -> dict[str, str]:
    """Render column mapping UI and return the (possibly user-edited) mapping.

    Returns final mapping dict: {source_column: target_column}.
    """
    confidence = mapping.confidence
    if confidence >= 0.9:
        color, label = "green", t("import.mapping_high")
    elif confidence >= 0.5:
        color, label = "orange", t("import.mapping_medium")
    else:
        color, label = "red", t("import.mapping_low")

    st.markdown(
        f"**{t('import.mapping_confidence')}:** "
        f":{color}[{label} ({confidence:.0%})]"
    )

    final_mapping: dict[str, str] = {}
    target_options = ["—"] + mapping.target_columns

    cols = st.columns([2, 1, 2])
    cols[0].markdown(f"**{t('import.source_column')}**")
    cols[1].markdown("")
    cols[2].markdown(f"**{t('import.target_column')}**")

    for src_col in mapping.source_columns:
        auto_target = mapping.mapping.get(src_col)
        default_idx = (
            target_options.index(auto_target) if auto_target in target_options else 0
        )

        c1, c2, c3 = st.columns([2, 1, 2])
        c1.text(src_col)
        c2.markdown("→" if default_idx > 0 else "")
        selected = c3.selectbox(
            src_col,
            target_options,
            index=default_idx,
            key=f"{key_prefix}_{src_col}",
            label_visibility="collapsed",
        )
        if selected != "—":
            final_mapping[src_col] = selected

    return final_mapping
