"""
dashboard/app.py
================
CARIQ — Cambodia Used-Car Intelligence Platform
Entry point: navigation shell, sidebar, global CSS, and page router.

Usage:
    uv run streamlit run dashboard/app.py

Pipeline Architecture:
    Khmer24 → Bronze (Parquet) → dbt → Silver (Conformed) → Gold (Analytics + ML)

Pages:
    1. Executive Overview      (views/executive_pulse.py)
    2. Market Intelligence     (views/market_intelligence.py)   ← primary market BI page
    3. Pipeline & Ingestion    (views/pipeline.py)
    4. Data Quality            (views/data_quality_monitoring.py)
    5. Feature Exploration     (views/feature_profiling.py)
    6. ML Readiness            (views/ml_readiness.py)
"""

from __future__ import annotations

import sys
from pathlib import Path

# ── Ensure project root is on sys.path ─────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

# ── Page configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CARIQ | Cambodia Used-Car Intelligence",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/PHALMenghak/car-price-prediction",
        "Report a bug": "https://github.com/PHALMenghak/car-price-prediction/issues",
        "About": "CARIQ — Cambodia Used-Car Intelligence. Built with Streamlit, DuckDB & dbt.",
    },
)

# ── Global CSS (light professional theme) ──────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* Main content area */
.block-container {
    padding-top: 1.25rem !important;
    padding-bottom: 2rem !important;
    max-width: 98% !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #f8fafc !important;
    border-right: 1px solid #e2e8f0 !important;
}

/* Active nav button */
[data-testid="stSidebar"] button[kind="primary"] {
    background-color: #eff6ff !important;
    color: #1e3a8a !important;
    border: 1px solid #bfdbfe !important;
    border-left: 4px solid #1e3a8a !important;
    font-weight: 700 !important;
    box-shadow: 0 1px 3px rgba(15,43,92,0.08) !important;
}

[data-testid="stSidebar"] button[kind="secondary"] {
    background-color: transparent !important;
    border: 1px solid transparent !important;
    text-align: left !important;
    color: #334155 !important;
}

[data-testid="stSidebar"] button[kind="secondary"]:hover {
    background-color: #f1f5f9 !important;
    border-color: #e2e8f0 !important;
}

/* Dataframe */
[data-testid="stDataFrame"] {
    border-radius: 6px;
    overflow: hidden;
}

/* Dividers */
hr { border-color: #e2e8f0; margin: 1.25rem 0; }
</style>
""", unsafe_allow_html=True)

# ── Imports ───────────────────────────────────────────────────────────────────
from dashboard.data_loader import (
    generate_markdown_report,
    load_available_dates,
    load_dbt_test_status,
    load_manifest,
    load_quality_summary,
)
from dashboard.views import (
    data_quality_monitoring,
    executive_pulse,
    feature_profiling,
    market_intelligence,
    ml_readiness,
    pipeline,
)


# ── Navigation structure ──────────────────────────────────────────────────────
NAV_SECTIONS = [
    ("OVERVIEW", [
        ("Executive Overview", "🏠", "Executive Overview"),
    ]),
    ("MARKET INTELLIGENCE", [
        ("Market Intelligence", "📈", "Market Intelligence"),
    ]),
    ("DATA PIPELINE", [
        ("Pipeline & Ingestion", "⚙", "Pipeline & Ingestion"),
        ("Data Quality", "✓", "Data Quality"),
    ]),
    ("ANALYTICS & ML", [
        ("Feature Exploration", "📖", "Feature Exploration"),
        ("ML Readiness", "🧪", "ML Readiness"),
    ]),
]

# Flat lookup: page_key -> icon
PAGE_ICONS = {key: icon for _, pages in NAV_SECTIONS for key, icon, _ in pages}

# ── Session state ─────────────────────────────────────────────────────────────
valid_pages = list(PAGE_ICONS.keys())
if "active_page" not in st.session_state or st.session_state.active_page not in valid_pages:
    st.session_state.active_page = "Executive Overview"
if "active_scrape_date" not in st.session_state:
    st.session_state.active_scrape_date = None

# ── Load sidebar data ─────────────────────────────────────────────────────────
manifest    = load_manifest()
dbt_status  = load_dbt_test_status()
quality_df  = load_quality_summary()
available_dates = load_available_dates()

# Derive sidebar status values
_ts = manifest.get("timestamp", "") if manifest else ""
_data_date = _ts[:16].replace("T", " ") + " UTC" if _ts else "No data"
_dbt_ok = dbt_status.get("available") and dbt_status.get("failed", 1) == 0
_dbt_label = f"{dbt_status.get('passed', 0)}/{dbt_status.get('total', 0)} tests"

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    # Product branding
    st.markdown("""
    <div style='padding: 4px 0 14px 0;'>
        <div style='font-size: 0.60rem; font-weight: 800; color: #1e3a8a;
                    text-transform: uppercase; letter-spacing: 1px;
                    background: #eff6ff; display: inline-block;
                    padding: 2px 8px; border-radius: 3px; margin-bottom: 6px;
                    border: 1px solid #bfdbfe;'>
            CARIQ PLATFORM
        </div>
        <div style='font-size: 1.05rem; font-weight: 800; color: #0f172a;
                    letter-spacing: -0.3px; line-height: 1.2;'>
            🚗 Cambodia Used-Car<br>Intelligence
        </div>
        <div style='font-size: 0.72rem; color: #64748b; margin-top: 4px;'>
            Khmer24 · Data Pipeline · ML
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Grouped navigation
    for section_label, pages in NAV_SECTIONS:
        st.markdown(
            f"<div style='font-size:0.65rem; font-weight:700; color:#94a3b8; "
            f"text-transform:uppercase; letter-spacing:0.6px; "
            f"margin: 10px 0 4px 2px;'>{section_label}</div>",
            unsafe_allow_html=True,
        )
        for page_key, icon, display_name in pages:
            is_active = st.session_state.active_page == page_key
            if st.button(
                f"{icon}  {display_name}",
                key=f"nav_{page_key}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state.active_page = page_key
                st.rerun()

    st.divider()

    # Snapshot date filter
    st.markdown(
        "<div style='font-size:0.65rem; font-weight:700; color:#94a3b8; "
        "text-transform:uppercase; letter-spacing:0.6px; margin-bottom:6px;'>DATA FILTER</div>",
        unsafe_allow_html=True,
    )

    preset = st.radio(
        "Time Range",
        options=["All Partitions", "Latest Snapshot", "Custom Date"],
        index=0,
        horizontal=False,
        label_visibility="collapsed",
    )

    if preset == "All Partitions":
        active_date = None
        st.caption("Showing: full data lake (all partitions)")
    elif preset == "Latest Snapshot" and available_dates:
        active_date = available_dates[0]
        st.caption(f"Showing latest: {active_date}")
    else:  # Custom Date
        if available_dates:
            selected_date = st.selectbox(
                "Select date",
                options=available_dates,
                label_visibility="collapsed",
            )
            active_date = selected_date
        else:
            active_date = None
            st.caption("No partitions available")

    st.session_state.active_scrape_date = active_date

    # Export tools
    st.divider()
    st.markdown(
        "<div style='font-size:0.65rem; font-weight:700; color:#94a3b8; "
        "text-transform:uppercase; letter-spacing:0.6px; margin-bottom:6px;'>TOOLS</div>",
        unsafe_allow_html=True,
    )
    report_content = generate_markdown_report(active_date)
    st.download_button(
        label="📑 Export Audit Report",
        data=report_content,
        file_name=f"cariq_audit_{active_date or 'full'}.md",
        mime="text/markdown",
        use_container_width=True,
        help="Download a markdown audit summary for the selected snapshot.",
    )
    if st.button("🔄 Refresh Cache", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # Status footer
    st.divider()
    _pipeline_dot = "🟢" if _dbt_ok else "🔴"
    st.markdown(
        f"""
        <div style='font-size:0.68rem; color:#64748b; line-height:1.8;'>
            <div>🕐 Data: <b style='color:#0f172a;'>{_data_date}</b></div>
            <div>{_pipeline_dot} Pipeline: <b style='color:#0f172a;'>{_dbt_label}</b></div>
            <div>🤖 Model: <b style='color:#64748b;'>champion_model.joblib</b></div>
            <div style='margin-top:6px; color:#94a3b8;'>
                ITC Year 4 · Phal Menghak<br>
                <a href='https://github.com/PHALMenghak/car-price-prediction'
                   target='_blank' style='color:#0f2b5c;'>GitHub ↗</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Page header (slim) ────────────────────────────────────────────────────────
page = st.session_state.active_page
icon = PAGE_ICONS.get(page, "📊")
_snapshot_label = active_date if active_date else "All Partitions"
_latest_date = _ts[:10] if _ts else "—"

st.markdown(
    f"""
    <div style='border-bottom: 1px solid #e2e8f0; padding-bottom: 10px; margin-bottom: 16px;'>
        <div style='display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;'>
            <div>
                <div style='font-size: 0.68rem; color: #64748b; font-weight: 600;
                            text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 3px;'>
                    CARIQ &rsaquo; {page}
                </div>
                <h1 style='margin: 0; font-size: 1.45rem; font-weight: 800;
                           color: #0f172a; letter-spacing: -0.5px;'>
                    {icon}&nbsp; {page}
                </h1>
            </div>
            <div style='display: flex; gap: 8px; align-items: center; flex-wrap: wrap;'>
                <span style='background: #f1f5f9; border: 1px solid #e2e8f0;
                             padding: 3px 10px; border-radius: 20px;
                             font-size: 0.72rem; font-weight: 600; color: #64748b;'>
                    Filter: <b style='color: #0f2b5c;'>{_snapshot_label}</b>
                </span>
                <span style='background: #f1f5f9; border: 1px solid #e2e8f0;
                             padding: 3px 10px; border-radius: 20px;
                             font-size: 0.72rem; font-weight: 600; color: #64748b;'>
                    Latest data: <b style='color: #0f2b5c;'>{_latest_date}</b>
                </span>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ── Page router ───────────────────────────────────────────────────────────────
if page == "Executive Overview":
    executive_pulse.render(active_date)
elif page == "Market Intelligence":
    market_intelligence.render(active_date)
elif page == "Pipeline & Ingestion":
    pipeline.render(active_date)
elif page == "Data Quality":
    data_quality_monitoring.render(active_date)
elif page == "Feature Exploration":
    feature_profiling.render(active_date)
elif page == "ML Readiness":
    ml_readiness.render(active_date)
else:
    executive_pulse.render(active_date)


# ── Global footer ─────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    "<p style='text-align:center; color:#94a3b8; font-size:0.70rem;'>"
    "CARIQ &mdash; Cambodia Used-Car Intelligence &nbsp;·&nbsp; "
    "Bronze → Silver → Gold Pipeline &nbsp;·&nbsp; "
    "Streamlit · DuckDB · dbt Core · Plotly &nbsp;·&nbsp; "
    "<a href='https://github.com/PHALMenghak/car-price-prediction' style='color:#0f2b5c;'>GitHub</a>"
    "</p>",
    unsafe_allow_html=True,
)
