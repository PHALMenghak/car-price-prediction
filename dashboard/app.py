"""
dashboard/app.py
================
Entry point for the Cambodian Car Data Quality Center.

Usage:
    uv run streamlit run dashboard/app.py

Pipeline Scope:
    Bronze (Khmer24 Scraper) → dbt Staging → dbt Intermediate → Silver (Conformed)

4 Streamlined Executive Pages:
    1. Overview & Collection     (executive_pulse.py)
    2. Cleaning & Transformation (cleaning_transformation.py)
    3. Data Quality & Anomalies  (data_quality_monitoring.py)
    4. Feature Profiling         (feature_profiling.py)
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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    color: #0f172a;
}

/* Main content container */
.block-container {
    padding-top: 1.25rem !important;
    padding-bottom: 2rem !important;
    max-width: 98% !important;
}

/* Sidebar styling */
[data-testid="stSidebar"] {
    background-color: #f8fafc;
    border-right: 1px solid #e2e8f0;
}

/* Active navigation button styling */
[data-testid="stSidebar"] button[kind="primary"] {
    background-color: #1e3a8a !important;
    color: #ffffff !important;
    border: 1px solid #1e3a8a !important;
    font-weight: 700 !important;
}

[data-testid="stSidebar"] button[kind="secondary"] {
    background-color: transparent !important;
    color: #334155 !important;
    border: 1px solid transparent !important;
    text-align: left !important;
}

[data-testid="stSidebar"] button[kind="secondary"]:hover {
    background-color: #e2e8f0 !important;
    color: #0f172a !important;
}

/* Dataframe table */
[data-testid="stDataFrame"] {
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    overflow: hidden;
}

/* Section dividers */
hr {
    border-color: #e2e8f0;
    margin: 1.25rem 0;
}

/* Typography scale */
h1 { color: #0f172a; font-weight: 800; font-size: 1.65rem; }
h2 { color: #1e293b; font-weight: 700; font-size: 1.20rem; }
h3 { color: #1e293b; font-weight: 700; font-size: 1.02rem; }
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
    cleaning_transformation,
    data_quality_monitoring,
    executive_pulse,
    feature_profiling,
)

# ── Streamlined 4-Page Catalog ────────────────────────────────────────────────
PAGES = {
    "Overview & Collection":     "📊",
    "Cleaning & Transformation": "🔧",
    "Data Quality & Anomalies":  "🛡️",
    "Feature Profiling":         "📈",
}

# ── Initialize session state ──────────────────────────────────────────────────
if "active_page" not in st.session_state or st.session_state.active_page not in PAGES:
    st.session_state.active_page = "Overview & Collection"
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
        <div style='font-size:0.75rem; color:#64748b; margin-top:3px; font-weight:500;'>
            Bronze → Silver | Khmer24 Pipeline
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # 1. Streamlined Navigation Menu
    st.markdown("<div style='font-size:0.70rem; font-weight:700; color:#64748b; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px;'>NAVIGATION</div>", unsafe_allow_html=True)
    for page_name, icon in PAGES.items():
        is_active = (st.session_state.active_page == page_name)
        btn_type = "primary" if is_active else "secondary"
        if st.button(
            f"{icon}  {page_name}",
            key=f"nav_{page_name}",
            use_container_width=True,
            type=btn_type,
        ):
            st.session_state.active_page = page_name
            st.rerun()

    st.divider()

    # 2. Snapshot Date Filter
    st.markdown("<div style='font-size:0.70rem; font-weight:700; color:#64748b; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px;'>SNAPSHOT FILTER</div>", unsafe_allow_html=True)

    available_dates = load_available_dates()
    selected_snapshot = st.selectbox(
        "Scrape Partition Date",
        options=["All Dates (Latest)"] + available_dates,
        index=0,
        help="Filter dashboard to a specific daily scrape snapshot, or view aggregated latest state.",
    )
    active_date = None if selected_snapshot == "All Dates (Latest)" else selected_snapshot
    st.session_state.active_scrape_date = active_date

    st.divider()

    # 3. dbt Contract Health Badge
    dbt_status = load_dbt_test_status()
    if dbt_status.get("available"):
        dbt_ok = dbt_status["failed"] == 0
        dbt_color = "#10b981" if dbt_ok else "#ef4444"
        dbt_icon = "✅" if dbt_ok else "❌"
        st.markdown(
            f"""
            <div style='padding:10px 12px; border-radius:6px; border:1px solid {dbt_color}40;
                        background:{dbt_color}12; margin-bottom:10px;'>
                <div style='font-weight:700; font-size:0.80rem; color:{dbt_color};'>
                    {dbt_icon} dbt Tests: {dbt_status['passed']}/{dbt_status['total']}
                </div>
                <div style='font-size:0.72rem; color:#64748b; margin-top:2px;'>
                    Contract Pass Rate: <b>{dbt_status['pass_rate_pct']}%</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 4. Export & Cache Actions
    report_content = generate_markdown_report(active_date)
    st.download_button(
        label="📑 Export Audit Report",
        data=report_content,
        file_name=f"dq_audit_report_{active_date or 'latest'}.md",
        mime="text/markdown",
        use_container_width=True,
        help="Download a markdown audit summary for this snapshot.",
    )

    if st.button("🔄 Refresh Data Cache", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # 5. Technical Attribution Footer
    st.markdown("""
    <div style='font-size:0.70rem; color:#94a3b8; line-height:1.5; margin-top:10px;'>
        ITC Year 4 Internship · Phal Menghak<br>
        Source: Khmer24 · DuckDB + dbt + Streamlit<br>
        <a href='https://github.com/PHALMenghak/car-price-prediction' target='_blank' style='color:#3b82f6;'>GitHub Repository ↗</a>
    </div>
    """, unsafe_allow_html=True)


# ── Global Page Header ────────────────────────────────────────────────────────
manifest   = load_manifest()
quality_df = load_quality_summary()

last_update = "—"
latest_scrape = "—"
if manifest:
    ts = manifest.get("timestamp", "")
    latest_scrape = ts[:10] if ts else "—"
    last_update = ts[:16].replace("T", " ") + " UTC" if ts else "—"
elif not quality_df.empty:
    latest_scrape = str(quality_df.iloc[0]["scrape_date"])
    last_update = latest_scrape

page = st.session_state.active_page
icon = PAGES.get(page, "📊")

st.markdown(f"""
<div style='border-bottom:2px solid #e2e8f0; padding-bottom:12px; margin-bottom:18px;'>
    <div style='display:flex; justify-content:space-between; align-items:flex-end; flex-wrap:wrap; gap:8px;'>
        <div>
            <div style='font-size:0.68rem; font-weight:800; color:#1e3a8a; text-transform:uppercase;
                        letter-spacing:0.8px; background:#eff6ff; display:inline-block;
                        padding:2px 8px; border-radius:3px; margin-bottom:4px; border:1px solid #bfdbfe;'>
                CAMBODIAN CAR DATA QUALITY CENTER
            </div>
            <h1 style='margin:0; font-size:1.65rem; font-weight:800; color:#0f172a; letter-spacing:-0.5px;'>
                {icon} &nbsp;{page}
            </h1>
            <p style='color:#64748b; margin:3px 0 0 0; font-size:0.82rem;'>
                <b>Bronze → Silver</b> | Data Pipeline Observability &amp; Quality Assurance &nbsp;·&nbsp; Khmer24 Marketplace
            </p>
        </div>
        <div style='display:flex; gap:10px; align-items:center; flex-wrap:wrap;'>
            <span style='background:#f8fafc; border:1px solid #e2e8f0; padding:4px 10px;
                         border-radius:20px; font-weight:600; font-size:0.75rem; color:#475569;'>
                Snapshot: <b style='color:#0f172a;'>{selected_snapshot}</b>
            </span>
            <span style='background:#f8fafc; border:1px solid #e2e8f0; padding:4px 10px;
                         border-radius:20px; font-weight:600; font-size:0.75rem; color:#475569;'>
                Latest Ingest: <b style='color:#0f172a;'>{latest_scrape}</b>
            </span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)


# ── Page Router ───────────────────────────────────────────────────────────────
if page == "Overview & Collection":
    executive_pulse.render(active_date)
elif page == "Cleaning & Transformation":
    cleaning_transformation.render(active_date)
elif page == "Data Quality & Anomalies":
    data_quality_monitoring.render(active_date)
elif page == "Feature Profiling":
    feature_profiling.render(active_date)
else:
    executive_pulse.render(active_date)


# ── Global Footer ─────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    "<p style='text-align:center; color:#94a3b8; font-size:0.72rem;'>"
    "Cambodian Car Data Quality Center &nbsp;·&nbsp; Bronze → Silver Pipeline Monitoring &nbsp;·&nbsp; "
    "Built with Streamlit, DuckDB &amp; dbt Core &nbsp;·&nbsp; "
    "<a href='https://github.com/PHALMenghak/car-price-prediction' style='color:#94a3b8;'>GitHub Repository</a>"
    "</p>",
    unsafe_allow_html=True,
)
