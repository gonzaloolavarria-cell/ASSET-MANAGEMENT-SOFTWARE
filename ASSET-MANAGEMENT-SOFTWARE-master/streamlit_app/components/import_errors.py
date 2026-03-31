"""Error visualization component for data import results.

Shows summary metrics, detailed error table, and CSV download.
"""

from __future__ import annotations

import csv
import io

import streamlit as st
from streamlit_app.i18n import t
from tools.models.schemas import ImportResult


def import_result_summary(result: ImportResult) -> None:
    """Show metric cards for total/valid/error rows."""
    c1, c2, c3 = st.columns(3)
    c1.metric(t("reports.total_rows"), result.total_rows)
    c2.metric(t("reports.valid_rows"), result.valid_rows)
    c3.metric(
        t("reports.error_rows"),
        result.error_rows,
        delta=f"-{result.error_rows}" if result.error_rows else None,
        delta_color="inverse",
    )

    if result.total_rows > 0:
        pct = result.valid_rows / result.total_rows * 100
        st.progress(pct / 100, text=f"{pct:.0f}% {t('import.rows_valid')}")


def import_error_table(result: ImportResult) -> None:
    """Show detailed error table with download option."""
    if not result.errors:
        st.success(t("import.no_errors"))
        return

    st.warning(f"{len(result.errors)} {t('import.errors_found')}")

    # Build error data for dataframe
    error_data = [
        {
            t("import.col_row"): e.row,
            t("import.col_column"): e.column,
            t("import.col_message"): e.message,
        }
        for e in result.errors
    ]
    st.dataframe(error_data, use_container_width=True)

    # Download errors as CSV
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["row", "column", "message"])
    writer.writeheader()
    for e in result.errors:
        writer.writerow({"row": e.row, "column": e.column, "message": e.message})
    st.download_button(
        t("import.download_errors"),
        buf.getvalue(),
        file_name="import_errors.csv",
        mime="text/csv",
    )


def import_data_preview(result: ImportResult, max_rows: int = 50) -> None:
    """Show first N rows of validated data."""
    if not result.validated_data:
        return
    st.subheader(t("import.data_preview"))
    preview = result.validated_data[:max_rows]
    st.dataframe(preview, use_container_width=True)
    if len(result.validated_data) > max_rows:
        st.caption(f"{t('import.showing')} {max_rows} / {len(result.validated_data)}")
