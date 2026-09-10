"""
dashboard/app.py
================
Entry point for the Cambodian Car Data Quality Center.

Usage (local):
    streamlit run dashboard/app.py

Architecture (current phase):
    Bronze → dbt Staging → dbt Intermediate → Silver → Data Quality Dashboard

Navigation (left sidebar):
    1. Overview
    2. Collection Monitoring
    3. Cleaning & Transformation
    4. Data Quality
    5. Data Anomalies
    6. Feature Profiling
    7. Silver Readiness
"""

from __future__ import annotations

import sys
from pathlib import Path

# ── Ensure project root is on sys.path ─────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

# ── Page configuration (must be the very first Streamlit call) ─────────────────
st.set_page_config(
    page_title="Car Data Quality Center | Khmer24",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/PHALMenghak/car-price-prediction",
        "Report a bug": "https://github.com/PHALMenghak/car-price-prediction/issues",
        "About": "Cambodian Car Data Quality Center — Bronze → Silver Pipeline Monitoring.",
    },
)

# ── Professional Word/Report-Style CSS ────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* Main container */
.block-container {
    padding-top: 1.25rem;
    padding-bottom: 2rem;
    max-width: 98%;
}

/* Hide arrow icons on st.metric delta */
[data-testid="stMetricDelta"] svg { display: none; }

/* Metric cards — clean white with navy top border */
[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-top: 3px solid #1e3a8a;
    border-radius: 6px;
    padding: 14px 16px 12px 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

[data-testid="stMetricLabel"] {
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    color: #475569 !important;
    text-transform: uppercase;
    letter-spacing: 0.4px;
}

[data-testid="stMetricValue"] {
    font-size: 1.55rem !important;
    font-weight: 700 !important;
    color: #1e293b !important;
}

[data-testid="stMetricDelta"] {
    font-size: 0.77rem !important;
    font-weight: 500 !important;
}

/* Sidebar styling */
[data-testid="stSidebar"] {
    background-color: #f8fafc;
    border-right: 1px solid #e2e8f0;
}

/* Dataframe table */
[data-testid="stDataFrame"] {
    border: 1px solid #e2e8f0;
    border-radius: 5px;
}

/* Divider */
hr {
    border-color: #e2e8f0;
    margin: 1.25rem 0;
}

/* Section headers */
h1 { color: #0f172a; font-weight: 800; }
h2 { color: #1e293b; font-weight: 700; font-size: 1.25rem; }
h3 { color: #1e293b; font-weight: 700; font-size: 1.1rem; }

/* Status badges inline */
.badge-good    { background:#dcfce7; color:#166534; padding:2px 8px; border-radius:4px; font-size:0.75rem; font-weight:600; }
.badge-warning { background:#fef9c3; color:#854d0e; padding:2px 8px; border-radius:4px; font-size:0.75rem; font-weight:600; }
.badge-danger  { background:#fee2e2; color:#991b1b; padding:2px 8px; border-radius:4px; font-size:0.75rem; font-weight:600; }
.badge-info    { background:#dbeafe; color:#1d4ed8; padding:2px 8px; border-radius:4px; font-size:0.75rem; font-weight:600; }
.badge-gray    { background:#f1f5f9; color:#475569; padding:2px 8px; border-radius:4px; font-size:0.75rem; font-weight:600; }

/* Report-style section title block */
.section-title {
    border-left: 4px solid #1e3a8a;
    padding-left: 12px;
    margin-bottom: 4px;
}
</style>
""", unsafe_allow_html=True)

# ── Module imports ─────────────────────────────────────────────────────────────
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
    pipeline_monitoring,
)
from dashboard.views import (
    collection_monitoring,
    cleaning_transformation,
    data_anomalies,
    silver_readiness,
)

# ── Page definitions ──────────────────────────────────────────────────────────
PAGES = {
    "Overview": "📊",
    "Collection Monitoring": "📥",
    "Cleaning & Transformation": "🔧",
    "Data Quality": "🛡️",
    "Data Anomalies": "🔍",
    "Feature Profiling": "📈",
    "Silver Readiness": "✅",
}

# ── Initialize session state ──────────────────────────────────────────────────
if "active_page" not in st.session_state:
    st.session_state.active_page = "Overview"
if "active_scrape_date" not in st.session_state:
    st.session_state.active_scrape_date = None

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    # Brand header
    st.markdown("""
    <div style='padding:4px 0 12px 0;'>
        <div style='font-size:1.05rem; font-weight:800; color:#0f172a; letter-spacing:-0.3px;'>
            🚗 Car Data Quality Center
        </div>
        <div style='font-size:0.76rem; color:#64748b; margin-top:3px; font-weight:500;'>
            Bronze → Silver | Pipeline Monitoring
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Navigation
    st.markdown("<div style='font-size:0.72rem; font-weight:700; color:#64748b; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px;'>NAVIGATION</div>", unsafe_allow_html=True)
    for page_name, icon in PAGES.items():
        is_active = st.session_state.active_page == page_name
        btn_style = (
            "background:#e0f2fe; color:#0369a1; border:1px solid #bae6fd;"
            if is_active
            else "background:transparent; color:#374151; border:1px solid transparent;"
        )
        if st.button(
            f"{icon}  {page_name}",
            key=f"nav_{page_name}",
            use_container_width=True,
            type="secondary",
        ):
            st.session_state.active_page = page_name
            st.rerun()

    st.divider()

    # Snapshot filter
    st.markdown("<div style='font-size:0.72rem; font-weight:700; color:#64748b; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px;'>FILTERS</div>", unsafe_allow_html=True)

    available_dates = load_available_dates()
    selected_snapshot = st.selectbox(
        "Scrape Date",
        options=["All Dates (Latest)"] + available_dates,
        index=0,
        help="Filter dashboard to a specific scrape snapshot, or view the latest aggregated data.",
    )
    active_date = None if selected_snapshot == "All Dates (Latest)" else selected_snapshot
    st.session_state.active_scrape_date = active_date

    st.divider()

    # dbt contract badge
    dbt_status = load_dbt_test_status()
    if dbt_status.get("available"):
        dbt_ok = dbt_status["failed"] == 0
        dbt_color = "#059669" if dbt_ok else "#dc2626"
        dbt_icon = "✅" if dbt_ok else "❌"
        st.markdown(
            f"""
            <div style='padding:10px 12px; border-radius:6px; border:1px solid {dbt_color};
                        background:{dbt_color}12; margin-bottom:10px;'>
                <div style='font-weight:700; font-size:0.82rem; color:{dbt_color};'>
                    {dbt_icon} dbt Tests: {dbt_status['passed']}/{dbt_status['total']}
                </div>
                <div style='font-size:0.72rem; color:#64748b; margin-top:2px;'>
                    Pass Rate: <b>{dbt_status['pass_rate_pct']}%</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Report download
    report_content = generate_markdown_report(active_date)
    st.download_button(
        label="📑 Export Audit Report",
        data=report_content,
        file_name=f"dq_audit_report_{active_date or 'latest'}.md",
        mime="text/markdown",
        use_container_width=True,
        help="Download a markdown audit report for this snapshot.",
    )

    st.divider()

    # Cache refresh
    if st.button("🔄 Refresh Data Cache", use_container_width=True):
        st.cache_data.clear()
        st.success("Cache cleared!")
        st.rerun()

    # Footer links
    st.markdown("""
    <div style='font-size:0.72rem; color:#94a3b8; margin-top:8px;'>
        <a href='https://github.com/PHALMenghak/car-price-prediction' style='color:#94a3b8;'>GitHub Repo</a>
        &nbsp;·&nbsp;
        <a href='https://github.com/PHALMenghak/car-price-prediction/blob/main/docs/DATA_DICTIONARY.md' style='color:#94a3b8;'>Data Dictionary</a>
    </div>
    """, unsafe_allow_html=True)

# ── Global Header ─────────────────────────────────────────────────────────────
# Read live values for header
manifest = load_manifest()
quality_df = load_quality_summary()

last_update = "—"
latest_scrape = "—"
if manifest:
    ts = manifest.get("timestamp", "")
    latest_scrape = ts[:10] if ts else "—"
    last_update = ts[:16].replace("T", " ") + " UTC" if ts else "—"
elif not quality_df.empty:
    latest_scrape = quality_df.iloc[0]["scrape_date"]
    last_update = latest_scrape

env_label = "DuckDB + Parquet"
data_source = "Khmer24 (Cambodia)"

st.markdown(f"""
<div style='border-bottom:2px solid #e2e8f0; padding-bottom:14px; margin-bottom:18px;'>
    <div style='display:flex; justify-content:space-between; align-items:flex-end; flex-wrap:wrap; gap:8px;'>
        <div>
            <div style='font-size:0.72rem; font-weight:700; color:#0369a1; text-transform:uppercase;
                        letter-spacing:0.6px; background:#e0f2fe; display:inline-block;
                        padding:2px 8px; border-radius:3px; margin-bottom:6px;'>
                DATA QUALITY MONITORING · CAMBODIA AUTOMOTIVE
            </div>
            <h1 style='margin:0; font-size:1.75rem; font-weight:800; color:#0f172a; letter-spacing:-0.5px;'>
                Cambodian Car Data Quality Center
            </h1>
            <p style='color:#64748b; margin:3px 0 0 0; font-size:0.85rem;'>
                <b>Bronze → Silver</b> | Data Pipeline Monitoring &nbsp;·&nbsp;
                Khmer24 Automotive Marketplace
            </p>
        </div>
        <div style='text-align:right; font-size:0.78rem; color:#64748b; line-height:1.8;'>
            <div><span style='color:#94a3b8; font-weight:600;'>Last Update:</span> <b style='color:#334155;'>{last_update}</b></div>
            <div><span style='color:#94a3b8; font-weight:600;'>Latest Scrape:</span> <b style='color:#334155;'>{latest_scrape}</b></div>
            <div><span style='color:#94a3b8; font-weight:600;'>Engine:</span> <b style='color:#334155;'>{env_label}</b></div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Page Router ───────────────────────────────────────────────────────────────
page = st.session_state.active_page

if page == "Overview":
    executive_pulse.render(active_date)
elif page == "Collection Monitoring":
    collection_monitoring.render(active_date)
elif page == "Cleaning & Transformation":
    cleaning_transformation.render(active_date)
elif page == "Data Quality":
    data_quality_monitoring.render(active_date)
elif page == "Data Anomalies":
    data_anomalies.render(active_date)
elif page == "Feature Profiling":
    feature_profiling.render(active_date)
elif page == "Silver Readiness":
    silver_readiness.render(active_date)

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    "<p style='text-align:center; color:#94a3b8; font-size:0.72rem;'>"
    "Cambodian Car Data Quality Center &nbsp;·&nbsp; Bronze → Silver Pipeline Monitoring &nbsp;·&nbsp; "
    "Built with Streamlit, DuckDB &amp; dbt Core &nbsp;·&nbsp; "
    "<a href='https://github.com/PHALMenghak/car-price-prediction' style='color:#94a3b8;'>GitHub</a>"
    "</p>",
    unsafe_allow_html=True,
)
