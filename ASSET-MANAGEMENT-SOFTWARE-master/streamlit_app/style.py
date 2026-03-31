"""Shared CSS styling for OCP Maintenance AI Streamlit app."""

import streamlit as st


def apply_style():
    """Inject OCP-branded CSS styling."""
    st.markdown("""
    <style>
        /* Metric card styling */
        [data-testid="stMetric"] {
            background-color: #E8F5E9;
            border: 1px solid #C8E6C9;
            border-radius: 8px;
            padding: 12px 16px;
        }
        [data-testid="stMetricLabel"] {
            font-size: 0.85rem;
            color: #1B5E20;
            font-weight: 600;
        }

        /* Tab styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 6px 6px 0 0;
            padding: 8px 20px;
        }

        /* Table header styling */
        .stDataFrame thead th {
            background-color: #1B5E20 !important;
            color: white !important;
        }

        /* Button refinements */
        .stButton > button[kind="primary"] {
            border-radius: 6px;
        }

        /* Sidebar branding */
        section[data-testid="stSidebar"] > div:first-child {
            padding-top: 1rem;
        }

        /* Expander styling */
        .streamlit-expanderHeader {
            font-weight: 600;
            color: #1B5E20;
        }
    </style>
    """, unsafe_allow_html=True)


def apply_hierarchy_style():
    """Inject modern hierarchy-specific CSS."""
    st.markdown("""
    <style>
        /* ── Tree Panel ── */
        .tree-panel-header {
            font-size: 0.78rem;
            font-weight: 700;
            color: #1B5E20;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            padding: 10px 0 8px;
            border-bottom: 2px solid #E8F5E9;
            margin-bottom: 6px;
        }
        .tree-container {
            max-height: 65vh;
            overflow-y: auto;
            padding-right: 4px;
        }
        .tree-container::-webkit-scrollbar { width: 4px; }
        .tree-container::-webkit-scrollbar-thumb { background: #C8E6C9; border-radius: 4px; }

        /* Style the hierarchy tree radio (target by aria-label) */
        [aria-label="Asset Tree"] { gap: 0px !important; }
        [aria-label="Asset Tree"] [data-baseweb="radio"] {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif !important;
            font-size: 0.82rem !important;
            padding: 4px 8px !important;
            margin: 0 !important;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.12s ease;
            white-space: pre !important;
            border-left: 3px solid transparent;
            line-height: 1.5;
        }
        [aria-label="Asset Tree"] [data-baseweb="radio"]:hover {
            background: linear-gradient(135deg, #f0f7f0 0%, #e8f5e9 100%);
        }
        [aria-label="Asset Tree"] [data-baseweb="radio"]:has(input:checked) {
            background: linear-gradient(135deg, #E8F5E9 0%, #C8E6C9 100%);
            border-left: 3px solid #1B5E20;
            font-weight: 600 !important;
        }
        /* Hide radio circle indicator */
        [aria-label="Asset Tree"] [data-baseweb="radio"] > div:first-child {
            display: none !important;
        }
        /* Hide native radio input */
        [aria-label="Asset Tree"] input[type="radio"] {
            display: none !important;
        }

        /* ── Breadcrumb ── */
        .hierarchy-breadcrumb {
            background: #FAFAFA;
            border: 1px solid #E8E8E8;
            border-radius: 8px;
            padding: 10px 16px;
            font-size: 0.82rem;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 2px;
        }
        .bc-sep { color: #BDBDBD; margin: 0 6px; font-size: 0.7rem; }
        .bc-item { font-weight: 500; }
        .bc-current { font-weight: 700; }

        /* ── Node Header Card ── */
        .node-header-card {
            background: white;
            border: 1px solid #E0E0E0;
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 16px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        }
        .node-header-top {
            display: flex;
            gap: 10px;
            align-items: center;
            margin-bottom: 8px;
        }
        .node-type-badge {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.02em;
        }
        .node-status-badge {
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }
        .status-active { background: #E8F5E9; color: #1B5E20; }
        .status-inactive { background: #FFEBEE; color: #C62828; }
        .node-title {
            font-size: 1.35rem;
            font-weight: 700;
            color: #212121;
            margin: 4px 0 8px;
            letter-spacing: -0.01em;
        }
        .node-meta-row {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }
        .meta-chip {
            background: #F5F5F5;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.75rem;
            color: #616161;
            font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
        }
        .crit-chip {
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 700;
            color: white;
        }

        /* ── Info Cards ── */
        .info-card {
            background: white;
            border: 1px solid #EEEEEE;
            border-radius: 10px;
            padding: 16px 20px;
            margin-bottom: 12px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.03);
        }
        .info-card-title {
            font-size: 0.75rem;
            font-weight: 700;
            color: #1B5E20;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            padding-bottom: 10px;
            margin-bottom: 10px;
            border-bottom: 1px solid #F5F5F5;
        }
        .info-row {
            display: flex;
            justify-content: space-between;
            padding: 5px 0;
            border-bottom: 1px solid #FAFAFA;
        }
        .info-row:last-child { border-bottom: none; }
        .info-label { color: #757575; font-size: 0.8rem; }
        .info-value { color: #212121; font-size: 0.8rem; font-weight: 500; font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace; }

        /* ── Spec Cards (metadata) ── */
        .spec-card {
            background: white;
            border: 1px solid #EEEEEE;
            border-radius: 10px;
            padding: 16px;
            text-align: center;
            box-shadow: 0 1px 4px rgba(0,0,0,0.03);
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }
        .spec-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }
        .spec-icon { font-size: 1.5rem; margin-bottom: 4px; }
        .spec-value { font-size: 1.05rem; font-weight: 700; color: #212121; }
        .spec-label {
            font-size: 0.68rem;
            color: #9E9E9E;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-top: 4px;
        }

        /* ── Empty State ── */
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #9E9E9E;
        }
        .empty-icon { font-size: 3rem; margin-bottom: 16px; opacity: 0.4; }
        .empty-state h3 { color: #616161; font-weight: 600; margin: 0 0 8px; }
        .empty-state p { color: #9E9E9E; font-size: 0.88rem; margin: 0; }

        /* ── Stats Pill ── */
        .stats-pill {
            background: linear-gradient(135deg, #1B5E20, #2E7D32);
            color: white;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.78rem;
            font-weight: 600;
            display: inline-block;
        }
    </style>
    """, unsafe_allow_html=True)


def apply_r8_module_style():
    """Inject R8-style module CSS for FMEA, Strategy, Work Packages, FMECA pages."""
    st.markdown("""
    <style>
        /* ── R8 Toolbar ── */
        .r8-toolbar {
            display: flex;
            gap: 6px;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid #E0E0E0;
            margin-bottom: 12px;
            flex-wrap: wrap;
        }
        .r8-toolbar .stButton > button {
            font-size: 0.75rem !important;
            padding: 4px 12px !important;
            border-radius: 4px !important;
            background: #F5F5F5 !important;
            border: 1px solid #E0E0E0 !important;
            color: #424242 !important;
            font-weight: 500 !important;
        }
        .r8-toolbar .stButton > button:hover {
            background: #E8F5E9 !important;
            border-color: #1B5E20 !important;
        }

        /* ── R8 Filter Bar ── */
        .r8-filter-bar {
            background: #FAFAFA;
            border: 1px solid #E8E8E8;
            border-radius: 6px;
            padding: 8px 12px;
            margin-bottom: 12px;
            font-size: 0.82rem;
        }

        /* ── R8 Form Cards ── */
        .r8-form-card {
            background: white;
            border: 1px solid #EEEEEE;
            border-radius: 10px;
            padding: 16px 20px;
            margin-bottom: 12px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.03);
        }
        .r8-form-title {
            font-size: 0.78rem;
            font-weight: 700;
            color: #1B5E20;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            padding-bottom: 8px;
            margin-bottom: 10px;
            border-bottom: 1px solid #F5F5F5;
        }

        /* ── R8 Status Chips ── */
        .r8-chip {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }
        .r8-chip-draft { background: #FFF3E0; color: #E65100; }
        .r8-chip-approved { background: #E8F5E9; color: #1B5E20; }
        .r8-chip-reviewed { background: #E3F2FD; color: #0D47A1; }
        .r8-chip-recommended { background: #F3E5F5; color: #4A148C; }

        /* ── R8 Action Row ── */
        .r8-action-row {
            display: flex;
            gap: 6px;
            padding: 8px 0;
            flex-wrap: wrap;
        }

        /* ── R8 Data Grid enhancements ── */
        .r8-grid-container {
            border: 1px solid #E0E0E0;
            border-radius: 8px;
            overflow: hidden;
            margin-bottom: 12px;
        }

        /* ── R8 Detail Section ── */
        .r8-detail-section {
            background: #FAFAFA;
            border: 1px solid #E8E8E8;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 12px;
        }
        .r8-detail-title {
            font-size: 0.72rem;
            font-weight: 700;
            color: #616161;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 8px;
        }

        /* ── R8 Two-list allocator ── */
        .r8-allocator-panel {
            background: white;
            border: 1px solid #E0E0E0;
            border-radius: 8px;
            padding: 12px;
            min-height: 200px;
        }
        .r8-allocator-title {
            font-size: 0.72rem;
            font-weight: 700;
            color: #1B5E20;
            text-transform: uppercase;
            margin-bottom: 8px;
        }
    </style>
    """, unsafe_allow_html=True)
