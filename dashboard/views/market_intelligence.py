"""
dashboard/views/market_intelligence.py
======================================
Page 3 — Market Dynamics & Cross-Sectional Pricing
Answers:
  1. What is the current market pricing profile across vintage years in Cambodia?
  2. How do prices vary across provinces and administrative tiers?
  3. What is the empirical price premium for Tax Paper (Fresh Import) vs. Plate Number?
  4. What is the current market share distribution by Brand, Body Style, and Powertrain?

Methodological Guardrail:
  - All curves reflect cross-sectional snapshot listing prices, not longitudinal depreciation.
  - All models shown enforce sample size gating (N >= 30) with explicit sample counts.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard import config
from dashboard.queries.market_queries import (
    load_market_kpis,
    load_market_share_breakdown,
    load_regional_pricing,
    load_tax_type_comparison,
    load_vintage_price_curves,
)


def render(active_date: str | None = None) -> None:
    """Render the Market Dynamics & Pricing page."""
    kpis = load_market_kpis(active_date)
    curves_df = load_vintage_price_curves(min_model_samples=30, scrape_date=active_date)
    regional_df = load_regional_pricing(active_date)
    tax_df = load_tax_type_comparison(active_date)
    shares = load_market_share_breakdown(active_date)

    if not kpis or curves_df.empty:
        st.warning("⚠️ No Gold Mart data available at `data/gold/fct_car_listings.parquet`. Run `dbt run` first.")
        return

    # ── 1. Top Market Headline KPIs ───────────────────────────────────────────
    k1, k2, k3, k4, k5 = st.columns(5)

    with k1:
        st.markdown(
            config.kpi_card(
                title="Active Market Listings",
                value=f"{kpis.get('total_listings', 0):,}",
                subtitle=f"{kpis.get('distinct_models', 0)} distinct models",
                delta=f"{kpis.get('distinct_brands', 0)} Brands",
                delta_color="normal",
                accent_color="#0284c7",
                icon="📊",
            ),
            unsafe_allow_html=True,
        )

    with k2:
        st.markdown(
            config.kpi_card(
                title="Median Market Price",
                value=f"${kpis.get('median_price', 0):,.0f}",
                subtitle=f"IQR: ${kpis.get('p25_price', 0):,.0f} – ${kpis.get('p75_price', 0):,.0f}",
                delta="Median (USD)",
                delta_color="normal",
                accent_color="#1e3a8a",
                icon="🏷️",
            ),
            unsafe_allow_html=True,
        )

    with k3:
        tax_p = kpis.get("median_tax_paper", 0)
        plate_p = kpis.get("median_plate", 0)
        tax_gap = tax_p - plate_p if (tax_p and plate_p) else 0
        st.markdown(
            config.kpi_card(
                title="Tax Paper Median",
                value=f"${tax_p:,.0f}",
                subtitle="Fresh Import market",
                delta=f"+${tax_gap:,.0f} vs Plate" if tax_gap > 0 else "Baseline",
                delta_color="normal" if tax_gap > 0 else "off",
                accent_color="#10b981",
                icon="📄",
            ),
            unsafe_allow_html=True,
        )

    with k4:
        st.markdown(
            config.kpi_card(
                title="Registered (Plate) Median",
                value=f"${plate_p:,.0f}",
                subtitle="In-circulation vehicles",
                delta="Registered",
                delta_color="off",
                accent_color="#f59e0b",
                icon="🟡",
            ),
            unsafe_allow_html=True,
        )

    with k5:
        st.markdown(
            config.kpi_card(
                title="Hybrid Electrification",
                value=f"{kpis.get('hybrid_share_pct', 0):.1f}%",
                subtitle="Prius, Camry, RX400h/450h",
                delta=f"Top: {kpis.get('top_brand', 'Toyota')}",
                delta_color="normal",
                accent_color="#7c3aed",
                icon="⚡",
            ),
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── 2. Methodology & Guardrail Notice ──────────────────────────────────────
    st.info(
        "ℹ️ **Methodology & Cross-Sectional Pricing Note:** "
        "These curves illustrate **cross-sectional price variations across vintage years** within the current snapshot. "
        "They reflect current asking prices by model year across different cars, not longitudinal tracking of the same physical vehicle over time. "
        "To prevent statistical skew, vintage curves are strictly filtered to models with **sample size $N \\ge 30$**."
    )

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ── 3. Visual Row 1: Cross-Sectional Vintage Price Curves ─────────────────
    st.markdown(
        config.section_header(
            "CROSS-SECTIONAL VINTAGE PRICE PROFILES (N ≥ 30)",
            "Median asking price by Model Year with Interquartile Range (P25–P75) shaded bands.",
        ),
        unsafe_allow_html=True,
    )

    _render_vintage_curves(curves_df)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # ── 4. Visual Row 2: Regional Pricing & Documentation Premium ──────────────
    col_reg, col_tax = st.columns([1, 1], gap="medium")

    with col_reg:
        st.markdown(
            config.section_header(
                "REGIONAL PRICE & VOLUME DISPERSION",
                "Listing volume and median price by province (small provinces N < 20 pooled).",
            ),
            unsafe_allow_html=True,
        )
        _render_regional_distribution(regional_df)

    with col_tax:
        st.markdown(
            config.section_header(
                "DOCUMENTATION PREMIUM: TAX PAPER vs PLATE",
                "Median price comparison for top high-volume models by registration status.",
            ),
            unsafe_allow_html=True,
        )
        _render_tax_type_comparison(tax_df)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # ── 5. Visual Row 3: Market Inventory & Share Breakdown ───────────────────
    st.markdown(
        config.section_header(
            "MARKET STRUCTURE: BRANDS, BODY TYPES & POWERTRAINS",
            "Inventory share and median pricing across Cambodian automotive categories.",
        ),
        unsafe_allow_html=True,
    )
    _render_market_shares(shares)


# ─────────────────────────────────────────────────────────────────────────────
# Component Render Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _render_vintage_curves(curves_df: pd.DataFrame) -> None:
    """Render interactive vintage price curves with model selector and IQR error bands."""
    if curves_df.empty:
        st.info("No qualified models with sample size N >= 30 found.")
        return

    # Extract distinct models and their total sample count
    model_samples = (
        curves_df[["full_model_name", "model_total_count"]]
        .drop_duplicates()
        .sort_values("model_total_count", ascending=False)
    )

    available_models = [
        f"{row['full_model_name']} (N = {row['model_total_count']:,})"
        for _, row in model_samples.iterrows()
    ]
    model_lookup = {
        f"{row['full_model_name']} (N = {row['model_total_count']:,})": row["full_model_name"]
        for _, row in model_samples.iterrows()
    }

    # Default top 4 popular models in Cambodia: Prius, RX330, Camry, Ranger / Highlander
    default_selection = available_models[: min(4, len(available_models))]

    selected_labels = st.multiselect(
        "Select Vehicle Models to Compare:",
        options=available_models,
        default=default_selection,
        help="Choose one or more high-volume models to inspect their price-by-year curve.",
    )

    if not selected_labels:
        st.warning("Please select at least one vehicle model to view the price curve.")
        return

    selected_names = [model_lookup[lbl] for lbl in selected_labels]
    filtered_df = curves_df[curves_df["full_model_name"].isin(selected_names)]

    fig = go.Figure()
    palette = ["#1e3a8a", "#0284c7", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#f97316"]

    for i, model_name in enumerate(selected_names):
        m_df = filtered_df[filtered_df["full_model_name"] == model_name].sort_values("vehicle_year")
        if m_df.empty:
            continue

        color = palette[i % len(palette)]
        total_n = m_df["model_total_count"].iloc[0]

        # Main median price line
        fig.add_trace(go.Scatter(
            x=m_df["vehicle_year"],
            y=m_df["median_price"],
            mode="lines+markers",
            name=f"{model_name} (N={total_n})",
            line=dict(color=color, width=3),
            marker=dict(size=7, color=color),
            hovertemplate=(
                f"<b>{model_name}</b> (%{{x}})<br>"
                "Median Price: $%{y:,.0f}<br>"
                "Sample Size (Year): %{customdata[0]} listings<br>"
                "IQR Range: $%{customdata[1]:,.0f} – $%{customdata[2]:,.0f}<extra></extra>"
            ),
            customdata=m_df[["sample_size", "p25_price", "p75_price"]].values,
        ))

        # Upper IQR bound (P75)
        fig.add_trace(go.Scatter(
            x=m_df["vehicle_year"],
            y=m_df["p75_price"],
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        ))

        # Lower IQR bound (P25) with fill to P75
        fig.add_trace(go.Scatter(
            x=m_df["vehicle_year"],
            y=m_df["p25_price"],
            mode="lines",
            line=dict(width=0),
            fill="tonexty",
            fillcolor=f"rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.12)",
            showlegend=False,
            hoverinfo="skip",
        ))

    config.apply_plot_theme(fig, height=380, show_legend=True)
    fig.update_layout(
        xaxis_title="Model Year (Vintage)",
        yaxis_title="Median Asking Price (USD)",
        yaxis_tickformat="$,.0f",
        xaxis=dict(dtick=1, gridcolor="#f1f5f9"),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_regional_distribution(regional_df: pd.DataFrame) -> None:
    """Renders regional median price and listing share."""
    if regional_df.empty:
        st.info("No regional distribution data found.")
        return

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=regional_df["province"],
        y=regional_df["median_price"],
        name="Median Price (USD)",
        marker_color="#1e3a8a",
        hovertemplate="<b>%{x}</b><br>Median Price: $%{y:,.0f}<br>Sample Size: %{customdata[0]:,} listings (%{customdata[1]}%)<extra></extra>",
        customdata=regional_df[["sample_size", "share_pct"]].values,
    ))

    config.apply_plot_theme(fig, height=330, show_legend=False)
    fig.update_layout(
        yaxis_title="Median Price (USD)",
        yaxis_tickformat="$,.0f",
        xaxis_tickangle=-30,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_tax_type_comparison(tax_df: pd.DataFrame) -> None:
    """Renders side-by-side bar chart of Tax Paper vs Plate Number."""
    if tax_df.empty:
        st.info("No tax documentation comparison data found.")
        return

    fig = px.bar(
        tax_df,
        x="vehicle_model",
        y="median_price",
        color="tax_status",
        barmode="group",
        color_discrete_map={
            "Tax Paper (Fresh Import)": "#10b981",
            "Plate Number (Registered)": "#f59e0b",
        },
        labels={"median_price": "Median Price (USD)", "vehicle_model": "Model", "tax_status": "Status"},
        custom_data=["sample_size", "p25_price", "p75_price"],
    )

    fig.update_traces(
        hovertemplate="<b>%{x}</b> (%{data.name})<br>Median: $%{y:,.0f}<br>Sample: N=%{customdata[0]}<br>IQR: $%{customdata[1]:,.0f}–$%{customdata[2]:,.0f}<extra></extra>"
    )

    config.apply_plot_theme(fig, height=330, show_legend=True)
    fig.update_layout(
        yaxis_tickformat="$,.0f",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_market_shares(shares: dict[str, pd.DataFrame]) -> None:
    """Renders Brand, Body Type, and Fuel Type breakdown cards and horizontal bars."""
    if not shares:
        st.info("No market share data available.")
        return

    c_b, c_body, c_f = st.columns(3, gap="medium")

    with c_b:
        st.markdown("**Top Brands by Volume**")
        b_df = shares.get("brands", pd.DataFrame())
        if not b_df.empty:
            for _, row in b_df.head(6).iterrows():
                st.markdown(
                    f"""
                    <div style='display:flex; justify-content:space-between; align-items:center;
                                padding:6px 0; border-bottom:1px solid #f1f5f9; font-size:0.80rem;'>
                        <span style='font-weight:600; color:#1e293b;'>{row['brand']}</span>
                        <span style='color:#64748b;'>{row['count']:,} recs ({row['share_pct']}%) · <b style='color:#0f172a;'>${row['median_price']:,.0f}</b></span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with c_body:
        st.markdown("**Body Type Distribution**")
        body_df = shares.get("body_types", pd.DataFrame())
        if not body_df.empty:
            for _, row in body_df.head(6).iterrows():
                st.markdown(
                    f"""
                    <div style='display:flex; justify-content:space-between; align-items:center;
                                padding:6px 0; border-bottom:1px solid #f1f5f9; font-size:0.80rem;'>
                        <span style='font-weight:600; color:#1e293b;'>{row['body_type']}</span>
                        <span style='color:#64748b;'>{row['count']:,} recs ({row['share_pct']}%) · <b style='color:#0f172a;'>${row['median_price']:,.0f}</b></span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with c_f:
        st.markdown("**Powertrain & Fuel Types**")
        fuel_df = shares.get("fuels", pd.DataFrame())
        if not fuel_df.empty:
            for _, row in fuel_df.head(6).iterrows():
                st.markdown(
                    f"""
                    <div style='display:flex; justify-content:space-between; align-items:center;
                                padding:6px 0; border-bottom:1px solid #f1f5f9; font-size:0.80rem;'>
                        <span style='font-weight:600; color:#1e293b;'>{row['fuel_type']}</span>
                        <span style='color:#64748b;'>{row['count']:,} recs ({row['share_pct']}%) · <b style='color:#0f172a;'>${row['median_price']:,.0f}</b></span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
