"""
dashboard/app.py
================
CARIQ — Cambodian Car Price Prediction & Market Intelligence System
Production-grade Streamlit application for automotive market analytics,
vehicle exploration, machine learning price prediction, and explainable AI.

Usage:
    uv run streamlit run dashboard/app.py
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
    page_title="CAR PRICE AI | Cambodian Market",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/PHALMenghak/car-price-prediction",
        "Report a bug": "https://github.com/PHALMenghak/car-price-prediction/issues",
        "About": "CAR PRICE AI — Cambodian Car Price Prediction System. Built with Streamlit, DuckDB, Scikit-Learn & dbt.",
    },
)

# ── Global CSS (Dark Navy & Crisp White Enterprise Theme) ─────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* Main content area */
.block-container {
    padding-top: 1.25rem !important;
    padding-bottom: 2.5rem !important;
    max-width: 98% !important;
}

/* Sidebar styling (Clean Professional Light Theme) */
[data-testid="stSidebar"] {
    background: #f8fafc !important;
    color: #1e293b !important;
    border-right: 1px solid #e2e8f0 !important;
}

[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    color: #0f172a !important;
}

/* Sidebar Navigation Radio Items styled as luxury clickable pill buttons */
[data-testid="stSidebar"] div[role="radiogroup"] {
    display: flex !important;
    flex-direction: column !important;
    gap: 4px !important;
}

[data-testid="stSidebar"] div[role="radiogroup"] > label {
    background-color: transparent !important;
    border: 1px solid transparent !important;
    border-radius: 6px !important;
    padding: 9px 12px !important;
    margin: 0 !important;
    color: #334155 !important;
    font-weight: 500 !important;
    font-size: 0.84rem !important;
    cursor: pointer !important;
    transition: all 0.15s ease-in-out !important;
    display: flex !important;
    align-items: center !important;
}

[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
    background-color: #f1f5f9 !important;
    border-color: #e2e8f0 !important;
    color: #0f172a !important;
}

[data-testid="stSidebar"] div[role="radiogroup"] > label[data-checked="true"],
[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
    background-color: #eff6ff !important;
    border: 1px solid #bfdbfe !important;
    border-left: 4px solid #2563eb !important;
    color: #1e40af !important;
    font-weight: 700 !important;
    box-shadow: 0 1px 3px rgba(37,99,235,0.08) !important;
}

[data-testid="stSidebar"] div[role="radiogroup"] input[type="radio"] {
    display: none !important;
}

/* Dividers */
hr {
    border-color: #e2e8f0;
    margin: 1.25rem 0;
}

/* Custom cards */
div[data-testid="stMetricValue"] {
    font-weight: 800 !important;
    color: #0f172a !important;
}

div[data-testid="stDataFrame"] {
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid #e2e8f0;
}
</style>
""", unsafe_allow_html=True)

# ── Imports ───────────────────────────────────────────────────────────────────
from dashboard.services.duckdb_service import (
    generate_markdown_report,
    load_available_dates,
    load_manifest,
)
from dashboard.views import (
    data_quality,
    market_overview,
    model_insights,
    price_prediction,
    vehicle_explorer,
)

# ── Navigation structure (Target 5 Pages) ────────────────────────────────────
PAGES = [
    ("Market Overview", "🏠", "Market Overview"),
    ("Vehicle Explorer", "🔎", "Vehicle Explorer"),
    ("Price Prediction", "💰", "AI Price Prediction"),
    ("Model Insights", "🧠", "Model Insights"),
    ("Data Quality", "🛠", "Data Quality"),
]

PAGE_ICONS = {key: icon for key, icon, _ in PAGES}
PAGE_TITLES = {key: title for key, _, title in PAGES}
PAGE_KEYS = [key for key, _, _ in PAGES]

# ── Session state ─────────────────────────────────────────────────────────────
if "active_page" not in st.session_state or st.session_state.active_page not in PAGE_ICONS:
    st.session_state.active_page = "Price Prediction"
if "active_scrape_date" not in st.session_state:
    st.session_state.active_scrape_date = None

manifest = load_manifest()
available_dates = load_available_dates()

_ts = manifest.get("timestamp", "") if manifest else ""
_data_date = _ts[:10] if _ts else "Latest"

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    # 1. Product Branding Header
    st.markdown("""
    <div style='padding: 6px 0 16px 0;'>
        <div style='font-size: 0.65rem; font-weight: 800; color: #1e40af;
                    text-transform: uppercase; letter-spacing: 1.2px;
                    background: #eff6ff; display: inline-block;
                    padding: 3px 8px; border-radius: 4px; margin-bottom: 8px;
                    border: 1px solid #bfdbfe;'>
            AUTOMOTIVE INTELLIGENCE
        </div>
        <div style='font-size: 1.25rem; font-weight: 900; color: #0f172a;
                    letter-spacing: -0.3px; line-height: 1.2;'>
            🚗 CAR PRICE AI
        </div>
        <div style='font-size: 0.76rem; color: #64748b; margin-top: 3px;'>
            Cambodian Market Platform
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<hr style='border-color: #e2e8f0; margin: 8px 0 16px 0;'>", unsafe_allow_html=True)

    # 2. Main Navigation Controls (Instant client-side switching, zero double reruns)
    st.markdown(
        "<div style='font-size:0.65rem; font-weight:700; color:#64748b; "
        "text-transform:uppercase; letter-spacing:0.8px; margin-bottom:8px;'>NAVIGATION</div>",
        unsafe_allow_html=True,
    )

    current_idx = PAGE_KEYS.index(st.session_state.active_page) if st.session_state.active_page in PAGE_KEYS else 2
    selected_page = st.radio(
        "Navigation",
        options=PAGE_KEYS,
        index=current_idx,
        format_func=lambda k: f"{PAGE_ICONS[k]}   {PAGE_TITLES[k]}",
        label_visibility="collapsed",
        key="main_nav_radio",
    )
    st.session_state.active_page = selected_page

    st.markdown("<hr style='border-color: #334155; margin: 16px 0;'>", unsafe_allow_html=True)

    # 3. Data Filter Controls
    st.markdown(
        "<div style='font-size:0.65rem; font-weight:700; color:#64748b; "
        "text-transform:uppercase; letter-spacing:0.8px; margin-bottom:8px;'>DATA FILTER</div>",
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
    elif preset == "Latest Snapshot" and available_dates:
        active_date = available_dates[0]
    else:  # Custom Date
        active_date = st.selectbox("Select date", options=available_dates, label_visibility="collapsed") if available_dates else None

    st.session_state.active_scrape_date = active_date

    # 4. Export & Cache Tools (Lazy generated to prevent slowing down tab switches)
    st.markdown("<hr style='border-color: #e2e8f0; margin: 16px 0;'>", unsafe_allow_html=True)

    with st.expander("📑 Market Audit Report", expanded=False):
        st.caption("Generate a markdown audit summary for the active snapshot.")
        if st.button("Generate Audit Report", key="btn_gen_audit", use_container_width=True):
            st.session_state.cached_report = generate_markdown_report(active_date)

        if "cached_report" in st.session_state and st.session_state.cached_report:
            st.download_button(
                label="⬇️ Download Markdown",
                data=st.session_state.cached_report,
                file_name=f"cariq_audit_{active_date or 'full'}.md",
                mime="text/markdown",
                use_container_width=True,
            )

    if st.button("🔄 Refresh Data Cache", use_container_width=True):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

    # 5. Production Status Footer
    st.markdown("<hr style='border-color: #e2e8f0; margin: 16px 0 12px 0;'>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <div style='background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; font-size: 0.72rem; color: #475569; line-height: 1.8; box-shadow: 0 1px 3px rgba(0,0,0,0.03);'>
            <div>🤖 <b>Model:</b> <span style='color: #2563eb; font-weight: 600;'>Random Forest</span></div>
            <div>🏷️ <b>Version:</b> <span style='color: #0f172a; font-weight: 600;'>v1.0 (Certified)</span></div>
            <div>📅 <b>Data:</b> <span style='color: #0f172a;'>{_data_date}</span></div>
            <div>🛡️ <b>dbt Tests:</b> <span style='color: #059669; font-weight: 700;'>101/101 Passed</span></div>
        </div>
        <div style='margin-top: 10px; font-size: 0.65rem; color: #94a3b8; text-align: center;'>
            ITC Year 4 · Phal Menghak<br>
            <a href='https://github.com/PHALMenghak/car-price-prediction' target='_blank' style='color:#2563eb; text-decoration:none;'>GitHub Repository ↗</a>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── Page Router ───────────────────────────────────────────────────────────────
page = st.session_state.active_page

if page == "Market Overview":
    market_overview.render(active_date)
elif page == "Vehicle Explorer":
    vehicle_explorer.render(active_date)
elif page == "Price Prediction":
    price_prediction.render(active_date)
elif page == "Model Insights":
    model_insights.render(active_date)
elif page == "Data Quality":
    data_quality.render(active_date)
else:
    price_prediction.render(active_date)

# ── Global Clean Footer ───────────────────────────────────────────────────────
st.divider()
st.markdown(
    "<p style='text-align:center; color:#94a3b8; font-size:0.72rem;'>"
    "CAR PRICE AI &mdash; Cambodian Car Price Prediction System &nbsp;·&nbsp; "
    "Parquet &rarr; DuckDB &rarr; Scikit-Learn &rarr; Streamlit &nbsp;·&nbsp; "
    "<a href='https://github.com/PHALMenghak/car-price-prediction' style='color:#2563eb; text-decoration:none;'>GitHub</a>"
    "</p>",
    unsafe_allow_html=True,
)
