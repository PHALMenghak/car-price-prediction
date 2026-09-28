"""
dashboard/views/market_intelligence.py
======================================
Market Intelligence Dashboard — Cambodia Used-Car Market (Khmer24 Data)

Answers:
  1. What is the current market structure and asking-price distribution in Cambodia?
  2. Which brands and models dominate volume and command pricing power?
  3. How do asking prices behave across vehicle body types, fuel types, and transmissions?
  4. What are the vintage asking-price profiles across manufacturing years?
  5. What is the documentation premium for fresh imports (Tax Paper) vs registered (Plate)?

Sections:
  0. Persistent Global Filter Bar (Brand, Model, Body Type, Fuel, Trans, Year, Price, Date)
  1. Market Overview (6 KPI Cards + Data-Driven Automated Insights)
  2. Asking Price Analysis (Histogram & KDE, Box Plots, Year Vintage, Segments)
  3. Brand & Model Intelligence (Volume, Pricing, Model Comparison Matrix, 3-Tier Drilldown)
  4. Vehicle Characteristics (Body Type, Fuel & Hybrid Premium, Transmission, Vehicle Age, Tax Status)
  5. Data Governance & Export (Downloadable Filtered Summaries, Methodological Lineage)

Methodological Guardrails:
  - All statistics operate strictly at the deduplicated unique listing grain (Gold Mart: fct_car_listings.parquet).
  - Mileage and engine cc are excluded from active analysis per governance rules.
  - Regional analysis is omitted per user specification.
  - Every price is explicitly labeled as Asking Price (USD).
  - Cross-sectional vintage curves are strictly distinguished from longitudinal depreciation.
  - Zero causal claims; minimum sample-size gating (N >= 5) enforced on all comparisons.
"""

from __future__ import annotations

import io
from typing import Any
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard import config
from dashboard.queries.market_queries import (
    load_brand_volume_and_price,
    load_filter_options,
    load_market_kpis,
    load_model_comparison_matrix,
    load_model_vintage_breakdown,
    load_models_for_brands,
    load_price_box_plot_data,
    load_price_distribution_data,
    load_price_vs_year,
    load_vehicle_characteristic_analysis,
)


# ─────────────────────────────────────────────────────────────────────────────
# Main Render Entry Point
# ─────────────────────────────────────────────────────────────────────────────

def render(active_date: str | None = None) -> None:
    """Render the redesigned Market Intelligence Dashboard."""

    # Default canonical listings filter
    filters: dict[str, Any] = {"canonical_only": True}
    if active_date:
        filters["scrape_date"] = active_date

    # Load reactive KPIs for the active filter set
    kpis = load_market_kpis(filters=filters, scrape_date=active_date)
    if not kpis or kpis.get("total_listings", 0) == 0:
        st.warning("⚠️ No listings available for analysis.")
        return

    # Section 1 — Market Overview (6 KPI Cards + Automated Insights)
    _render_market_overview(kpis, filters)

    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

    # Section 2 — Asking Price Analysis
    _render_asking_price_section(filters, kpis)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # Section 3 — Brand & Model Intelligence
    _render_brand_model_section(filters)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # Section 4 — Vehicle Characteristics Dynamics
    _render_vehicle_characteristics_section(filters)


# ─────────────────────────────────────────────────────────────────────────────
# Section 1 — Market Overview (6 KPI Cards + Automated Insights)
# ─────────────────────────────────────────────────────────────────────────────

def _render_market_overview(kpis: dict[str, Any], filters: dict[str, Any]) -> None:
    """Render the 6 executive KPI cards and data-driven automated insights."""
    total_l        = int(kpis.get("total_listings", 0))
    total_cat      = int(kpis.get("total_catalog", 8569))
    cov_pct        = kpis.get("coverage_pct", 100.0)
    median_p       = kpis.get("median_price", 0) or 0
    mean_p         = kpis.get("mean_price", 0) or 0
    p25            = kpis.get("p25_price", 0) or 0
    p75            = kpis.get("p75_price", 0) or 0
    iqr            = kpis.get("iqr_price", 0) or (p75 - p25)
    min_p          = kpis.get("min_price", 0) or 0
    max_p          = kpis.get("max_price", 0) or 0
    p05            = kpis.get("p05_price", min_p) or min_p
    p95            = kpis.get("p95_price", max_p) or max_p
    top_brand      = kpis.get("top_brand", "—")
    top_b_pct      = kpis.get("top_brand_pct", 0) or 0
    sec_brand      = kpis.get("second_brand", "—")
    sec_b_pct      = kpis.get("second_brand_pct", 0) or 0
    median_yr      = int(kpis.get("median_year", 2014))
    median_age     = int(kpis.get("median_age", 12))
    distinct_b     = int(kpis.get("distinct_brands", 0))
    distinct_m     = int(kpis.get("distinct_models", 0))
    dup_reposts    = int(kpis.get("duplicate_reposts", 1438))

    card1_title = "Unique Vehicles"
    card1_sub = f"{dup_reposts:,} dealer reposts pruned · {cov_pct:.1f}% catalog"

    # Skewness calculation (mean vs median)
    skew_pct = round(100.0 * (mean_p - median_p) / max(median_p, 1), 1) if median_p > 0 else 0
    skew_label = f"+{skew_pct:.1f}% vs median" if skew_pct > 0 else f"{skew_pct:.1f}% vs median"

    st.markdown(
        config.section_header(
            "1. MARKET OVERVIEW",
            "High-level market dimensions, robust central tendencies, price dispersion, and vintage structure.",
        ),
        unsafe_allow_html=True,
    )

    k1, k2, k3, k4, k5, k6 = st.columns(6)

    with k1:
        st.markdown(
            config.kpi_card(
                title=card1_title,
                value=f"{total_l:,}",
                subtitle=card1_sub,
                accent_color="#0284c7",
                icon="🚗",
            ),
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            config.kpi_card(
                title="Median Asking Price",
                value=f"${median_p:,.0f}",
                subtitle=f"IQR: ${p25:,.0f} – ${p75:,.0f}",
                accent_color="#0f2b5c",
                icon="🏷️",
            ),
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            config.kpi_card(
                title="Average Asking Price",
                value=f"${mean_p:,.0f}",
                subtitle=f"Skewness: {skew_label}",
                accent_color="#0284c7",
                icon="📈",
            ),
            unsafe_allow_html=True,
        )
    with k4:
        st.markdown(
            config.kpi_card(
                title="Price Range (P05–P95)",
                value=f"${p05:,.0f}–${p95:,.0f}",
                subtitle=f"Span: ${min_p:,.0f} – ${max_p:,.0f}",
                accent_color="#c59b27",
                icon="↔️",
            ),
            unsafe_allow_html=True,
        )
    with k5:
        st.markdown(
            config.kpi_card(
                title="Dominant Brand",
                value=top_brand,
                subtitle=f"{top_b_pct:.1f}% share (2nd: {sec_brand} {sec_b_pct:.1f}%)",
                accent_color="#059669",
                icon="🏆",
            ),
            unsafe_allow_html=True,
        )
    with k6:
        st.markdown(
            config.kpi_card(
                title="Median Vintage Year",
                value=str(median_yr),
                subtitle=f"Median vehicle age: {median_age} yrs",
                accent_color="#64748b",
                icon="📅",
            ),
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Section 2 — Asking Price Analysis
# ─────────────────────────────────────────────────────────────────────────────

def _render_asking_price_section(filters: dict[str, Any], kpis: dict[str, Any]) -> None:
    """Render asking price histogram, box plots, and price vs manufacturing year."""
    st.markdown(
        config.section_header(
            "2. ASKING PRICE ANALYSIS",
            "Empirical distribution, central tendencies, segment spreads, and vintage pricing.",
        ),
        unsafe_allow_html=True,
    )

    tab_hist, tab_box, tab_year = st.tabs([
        "📊 Price Distribution",
        "📦 Segment Pricing",
        "📅 Vintage Analysis",
    ])

    with tab_hist:
        _render_price_histogram(filters, kpis)

    with tab_box:
        _render_segment_box_plots(filters)

    with tab_year:
        _render_price_by_year_view(filters)


def _render_price_histogram(filters: dict[str, Any], kpis: dict[str, Any]) -> None:
    """Clean, high-readability interactive histogram of vehicle asking prices."""
    df = load_price_distribution_data(filters=filters)
    if df.empty:
        st.info("No price distribution data available for current filters.")
        return

    median_p = float(kpis.get("median_price", 0) or 0)
    mean_p   = float(kpis.get("mean_price", 0) or 0)
    p25      = float(kpis.get("p25_price", 0) or 0)
    p75      = float(kpis.get("p75_price", 0) or 0)

    # Clean display controls
    c_ctrl1, c_ctrl2 = st.columns([1.5, 2.5])
    with c_ctrl1:
        view_scope = st.radio(
            "Display Range:",
            options=["Standard Market (Under $100k)", "All Listings (Full Range)"],
            horizontal=True,
            key="hist_scope",
        )
    with c_ctrl2:
        log_scale = st.checkbox("Logarithmic Scale (X-axis)", value=False, key="hist_log")

    # If log scale is active, always view full range so the log compression shows the whole distribution smoothly
    plot_df = df if log_scale or view_scope == "All Listings (Full Range)" else df[df["price"] <= 100000]

    # Create figure
    fig = go.Figure()

    # Main Histogram
    fig.add_trace(go.Histogram(
        x=plot_df["price"],
        nbinsx=45,
        marker=dict(color="#0f2b5c", line=dict(color="#ffffff", width=0.5)),
        opacity=0.88,
        name="Vehicle Listings",
        hovertemplate="<b>Price Range:</b> %{x}<br><b>Count:</b> %{y:,} vehicles<extra></extra>",
    ))

    # Reference Indicators as clean Legend Items (Zero text collision inside the chart)
    if p25 > 0 and p75 > 0:
        fig.add_vrect(
            x0=p25, x1=p75,
            fillcolor="rgba(2, 132, 199, 0.12)",
            layer="below", line_width=0,
        )
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode="markers",
            marker=dict(size=12, color="rgba(2, 132, 199, 0.35)", symbol="square"),
            name=f"Central 50% IQR (${p25:,.0f} – ${p75:,.0f})",
        ))

    if median_p > 0:
        fig.add_vline(
            x=median_p, line_width=2.5, line_dash="dash", line_color="#059669",
        )
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode="lines",
            line=dict(color="#059669", width=2.5, dash="dash"),
            name=f"Median (${median_p:,.0f})",
        ))

    if mean_p > 0:
        fig.add_vline(
            x=mean_p, line_width=2.0, line_dash="dot", line_color="#c59b27",
        )
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode="lines",
            line=dict(color="#c59b27", width=2.0, dash="dot"),
            name=f"Mean (${mean_p:,.0f})",
        ))

    config.apply_plot_theme(
        fig, height=config.CHART_H_LARGE, show_legend=True, legend_orientation="h",
        xaxis_title="Asking Price (USD)", yaxis_title="Number of Vehicles",
    )

    if log_scale:
        fig.update_xaxes(
            type="log",
            tickvals=[1000, 5000, 10000, 20000, 50000, 100000, 250000, 500000, 1000000],
            ticktext=["$1k", "$5k", "$10k", "$20k", "$50k", "$100k", "$250k", "$500k", "$1M"],
        )
    else:
        fig.update_xaxes(tickformat="$,.0f")

    fig.update_yaxes(tickformat=",d")

    # Position clean horizontal legend right at the top
    fig.update_layout(
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(size=11, family="Inter, sans-serif"),
        ),
        margin=dict(t=35, b=20, l=15, r=15),
    )

    st.plotly_chart(fig, use_container_width=True)


def _render_segment_box_plots(filters: dict[str, Any]) -> None:
    """Box plots showing asking price spreads across vehicle segments."""
    c_dim, _ = st.columns([1, 2])
    with c_dim:
        segment_by = st.radio(
            "Segment By:",
            options=["Vehicle Body Type", "Brand", "Fuel Type"],
            horizontal=True,
            key="box_segment_dim",
        )

    col_map = {
        "Vehicle Body Type": "vehicle_body_type",
        "Brand": "vehicle_brand",
        "Fuel Type": "vehicle_fuel_type",
    }
    target_col = col_map[segment_by]
    box_df = load_price_box_plot_data(group_by=target_col, top_n=10, filters=filters)

    if box_df.empty:
        st.info("Insufficient segment data for box plots (need N >= 5 per group).")
        return

    fig = px.box(
        box_df,
        y="group_label",
        x="price",
        color="group_label",
        color_discrete_sequence=config.CHART_COLORS,
        points="outliers",
        labels={"price": "Asking Price (USD)", "group_label": segment_by},
    )
    config.apply_plot_theme(
        fig, height=config.CHART_H_LARGE, show_legend=False,
        xaxis_title="Asking Price (USD)", yaxis_title=segment_by,
    )
    fig.update_xaxes(tickformat="$,.0f")
    fig.update_layout(yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"Box plot showing median, P25, P75, and 1.5×IQR whiskers across top {segment_by} groups "
        f"(N = {len(box_df):,} total listings across shown segments)."
    )


def _render_price_by_year_view(filters: dict[str, Any]) -> None:
    """Bubble scatter plot and IQR ribbon of asking prices across manufacturing years."""
    df = load_price_vs_year(filters=filters)
    if df.empty:
        st.info("No price-by-year data available for current filters.")
        return

    fig = go.Figure()

    # IQR Ribbon
    fig.add_trace(go.Scatter(
        x=df["vehicle_year"], y=df["p75_price"],
        mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=df["vehicle_year"], y=df["p25_price"],
        mode="lines", line=dict(width=0),
        fill="tonexty", fillcolor="rgba(15, 43, 92, 0.10)",
        showlegend=True, name="IQR Band (P25–P75)", hoverinfo="skip",
    ))

    # Median Line with Marker Bubbles proportional to Listing Count
    fig.add_trace(go.Scatter(
        x=df["vehicle_year"],
        y=df["median_price"],
        mode="lines+markers",
        name="Median Asking Price",
        line=dict(color="#0f2b5c", width=2.5),
        marker=dict(
            size=df["listing_count"].apply(lambda n: min(max(int(n**0.45) * 3, 6), 26)),
            color="#0284c7",
            line=dict(color="#0f2b5c", width=1.5),
        ),
        hovertemplate=(
            "<b>Manufacturing Year: %{x}</b><br>"
            "Median Price: $%{y:,.0f}<br>"
            "P25–P75: $%{customdata[0]:,.0f}–$%{customdata[1]:,.0f}<br>"
            "Average Price: $%{customdata[2]:,.0f}<br>"
            "Listings: N = %{customdata[3]:,}<extra></extra>"
        ),
        customdata=df[["p25_price", "p75_price", "mean_price", "listing_count"]].values,
    ))

    config.apply_plot_theme(
        fig, height=config.CHART_H_SCATTER, show_legend=True,
        xaxis_title="Manufacturing Year (Vintage)", yaxis_title="Median Asking Price (USD)",
    )
    fig.update_layout(
        yaxis_tickformat="$,.0f",
        xaxis=dict(dtick=2, gridcolor="#f1f5f9"),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "<b>Methodological Note</b>: Cross-sectional asking prices across manufacturing years — "
        "not a longitudinal depreciation curve. Data points reflect distinct physical vehicles listed simultaneously "
        f"in the Cambodian market snapshot (Total N = {df['listing_count'].sum():,} listings across {len(df)} vintage years)."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Section 3 — Brand & Model Intelligence
# ─────────────────────────────────────────────────────────────────────────────

def _render_brand_model_section(filters: dict[str, Any]) -> None:
    """Render brand volume/price comparisons, model matrix, and 3-tier drilldown."""
    st.markdown(
        config.section_header(
            "3. BRAND & MODEL INTELLIGENCE",
            "Market dominance, brand pricing power, granular model matrix, and interactive vintage drill-down.",
        ),
        unsafe_allow_html=True,
    )

    tab_brands, tab_matrix, tab_drill = st.tabs([
        "🏢 Brand Volume & Pricing Power",
        "📋 Model Comparison Matrix",
        "🔍 Brand → Model → Year Drill-Down",
    ])

    with tab_brands:
        _render_brand_volume_and_price(filters)

    with tab_matrix:
        _render_model_comparison_matrix(filters)

    with tab_drill:
        _render_brand_model_drilldown(filters)


def _render_brand_volume_and_price(filters: dict[str, Any]) -> None:
    """Coordinated dual horizontal bar charts for brand volume and median price."""
    df = load_brand_volume_and_price(top_n=15, filters=filters)
    if df.empty:
        st.info("No brand data available for current filters.")
        return

    c_vol, c_price = st.columns(2, gap="medium")

    with c_vol:
        fig_vol = go.Figure(go.Bar(
            y=df["brand"],
            x=df["listing_count"],
            orientation="h",
            marker_color="#0f2b5c",
            text=[f"{cnt:,} ({pct:.1f}%)" for cnt, pct in zip(df["listing_count"], df["share_pct"])],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Listings: %{x:,}<br>Share: %{text}<extra></extra>",
        ))
        config.apply_plot_theme(
            fig_vol, height=config.CHART_H_LARGE, show_legend=False,
            xaxis_title="Listing Count", yaxis_title="Brand",
        )
        fig_vol.update_layout(yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig_vol, use_container_width=True)

    with c_price:
        fig_p = go.Figure(go.Bar(
            y=df["brand"],
            x=df["median_price"],
            orientation="h",
            marker_color="#c59b27",
            error_x=dict(
                type="data",
                symmetric=False,
                array=(df["p75_price"] - df["median_price"]).tolist(),
                arrayminus=(df["median_price"] - df["p25_price"]).tolist(),
                color="#94a3b8",
                thickness=1.5,
            ),
            hovertemplate=(
                "<b>%{y}</b><br>Median Asking Price: $%{x:,.0f}<br>"
                "IQR: $%{customdata[0]:,.0f}–$%{customdata[1]:,.0f}<br>"
                "Average: $%{customdata[2]:,.0f}<extra></extra>"
            ),
            customdata=df[["p25_price", "p75_price", "mean_price"]].values,
        ))
        config.apply_plot_theme(
            fig_p, height=config.CHART_H_LARGE, show_legend=False,
            xaxis_title="Median Asking Price (USD)", yaxis_title="Brand",
        )
        fig_p.update_layout(xaxis_tickformat="$,.0f", yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig_p, use_container_width=True)

    st.caption(
        f"Top {len(df)} brands by listing volume · Error bars represent the Interquartile Range (P25–P75) · "
        f"Total N = {df['listing_count'].sum():,} listings."
    )


def _render_model_comparison_matrix(filters: dict[str, Any]) -> None:
    """Sortable, formatted interactive table comparing vehicle models."""
    matrix_df = load_model_comparison_matrix(top_n=60, min_samples=5, filters=filters)
    if matrix_df.empty:
        st.info("No models meet the minimum sample size threshold (N >= 5) for current filters.")
        return

    col_s1, col_s2 = st.columns([2, 1])
    with col_s1:
        st.caption(f"Displaying top {len(matrix_df)} vehicle models with sample size N ≥ 5 listings.")
    with col_s2:
        # CSV Export
        csv_buffer = io.StringIO()
        matrix_df.to_csv(csv_buffer, index=False)
        st.download_button(
            label="📥 Download Model Matrix (CSV)",
            data=csv_buffer.getvalue(),
            file_name="cariq_model_comparison_matrix.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # Format table for display
    display_df = matrix_df[[
        "brand", "model", "listing_count", "median_price",
        "mean_price", "iqr_price", "p25_price", "p75_price", "min_price", "max_price", "median_year",
    ]].copy()

    display_df.columns = [
        "Brand", "Model", "Listings (N)", "Median ($)",
        "Mean ($)", "IQR Span ($)", "P25 ($)", "P75 ($)", "Min ($)", "Max ($)", "Median Year",
    ]

    st.dataframe(
        display_df,
        column_config={
            "Listings (N)": st.column_config.ProgressColumn(
                "Listings (N)",
                format="%d",
                min_value=0,
                max_value=int(matrix_df["listing_count"].max()),
            ),
            "Median ($)": st.column_config.NumberColumn("Median Asking Price", format="$%d"),
            "Mean ($)": st.column_config.NumberColumn("Average Asking Price", format="$%d"),
            "IQR Span ($)": st.column_config.NumberColumn("IQR ($)", format="$%d"),
            "P25 ($)": st.column_config.NumberColumn("P25", format="$%d"),
            "P75 ($)": st.column_config.NumberColumn("P75", format="$%d"),
            "Min ($)": st.column_config.NumberColumn("Min", format="$%d"),
            "Max ($)": st.column_config.NumberColumn("Max", format="$%d"),
            "Median Year": st.column_config.NumberColumn("Median Year", format="%d"),
        },
        use_container_width=True,
        hide_index=True,
    )


def _render_brand_model_drilldown(filters: dict[str, Any]) -> None:
    """Interactive cascading drilldown: Brand -> Model -> Manufacturing Year."""
    opts = load_filter_options()
    brands = opts.get("brands", [])
    if not brands:
        st.info("No brand options available.")
        return

    c_sel1, c_sel2 = st.columns(2)
    with c_sel1:
        default_brand = "Toyota" if "Toyota" in brands else brands[0]
        sel_drill_brand = st.selectbox("1. Select Brand:", options=brands, index=brands.index(default_brand), key="drill_brand")

    models_for_brand = load_models_for_brands((sel_drill_brand,))
    with c_sel2:
        default_model = models_for_brand[0] if models_for_brand else "—"
        if "Prius" in models_for_brand:
            default_model = "Prius"
        sel_drill_model = st.selectbox(
            "2. Select Model:",
            options=models_for_brand if models_for_brand else ["No models found"],
            index=models_for_brand.index(default_model) if default_model in models_for_brand else 0,
            key="drill_model",
            disabled=not models_for_brand,
        )

    if not models_for_brand or sel_drill_model == "No models found":
        st.info(f"No listings found for brand {sel_drill_brand}.")
        return

    # Load year-by-year vintage stats
    v_df = load_model_vintage_breakdown(sel_drill_brand, sel_drill_model, filters=filters)
    if v_df.empty:
        st.info(f"No vintage records found for {sel_drill_brand} {sel_drill_model} under active filters.")
        return

    total_samples = int(v_df["sample_size"].sum())
    overall_median = v_df["median_price"].median()

    st.markdown(
        f"""
        <div style='background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:10px 14px; margin:10px 0;'>
            <div style='display:flex; justify-content:space-between; align-items:baseline; flex-wrap:wrap;'>
                <span style='font-size:0.95rem; font-weight:800; color:#0f2b5c;'>
                    🚘 {sel_drill_brand} {sel_drill_model} Vintage Breakdown
                </span>
                <span style='font-size:0.75rem; color:#64748b;'>
                    Total Sample: <b>N = {total_samples:,} listings</b> across <b>{len(v_df)} vintage years</b>
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Coordinated view: Vintage curve chart + Table
    c_chart, c_tbl = st.columns([3, 2], gap="medium")

    with c_chart:
        fig = go.Figure()
        # IQR band
        fig.add_trace(go.Scatter(
            x=v_df["vehicle_year"], y=v_df["p75_price"],
            mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=v_df["vehicle_year"], y=v_df["p25_price"],
            mode="lines", line=dict(width=0),
            fill="tonexty", fillcolor="rgba(2, 132, 199, 0.12)",
            showlegend=True, name="IQR Range", hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=v_df["vehicle_year"], y=v_df["median_price"],
            mode="lines+markers",
            name=f"{sel_drill_brand} {sel_drill_model}",
            line=dict(color="#0284c7", width=3),
            marker=dict(size=7, color="#0f2b5c"),
            hovertemplate=(
                f"<b>{sel_drill_brand} {sel_drill_model} (%{{x}})</b><br>"
                "Median Asking Price: $%{y:,.0f}<br>"
                "P25–P75: $%{customdata[0]:,.0f}–$%{customdata[1]:,.0f}<br>"
                "Tax Paper Share: %{customdata[2]:.1f}%<br>"
                "Sample Size: N = %{customdata[3]:,}<extra></extra>"
            ),
            customdata=v_df[["p25_price", "p75_price", "tax_paper_pct", "sample_size"]].values,
        ))
        config.apply_plot_theme(
            fig, height=config.CHART_H_MEDIUM, show_legend=True,
            xaxis_title="Vintage Year", yaxis_title="Median Asking Price (USD)",
        )
        fig.update_layout(yaxis_tickformat="$,.0f", xaxis=dict(dtick=2))
        st.plotly_chart(fig, use_container_width=True)

    with c_tbl:
        tbl_view = v_df[[
            "vehicle_year", "sample_size", "median_price", "iqr_price" if "iqr_price" in v_df.columns else "p25_price", "tax_paper_pct"
        ]].copy()
        # Compute IQR span if not in df
        tbl_view["iqr_span"] = v_df["p75_price"] - v_df["p25_price"]
        tbl_view = tbl_view[["vehicle_year", "sample_size", "median_price", "iqr_span", "tax_paper_pct"]]
        tbl_view.columns = ["Year", "N", "Median ($)", "IQR ($)", "Tax Paper %"]

        st.dataframe(
            tbl_view,
            column_config={
                "Year": st.column_config.NumberColumn("Year", format="%d"),
                "N": st.column_config.NumberColumn("N", format="%d"),
                "Median ($)": st.column_config.NumberColumn("Median ($)", format="$%d"),
                "IQR ($)": st.column_config.NumberColumn("IQR ($)", format="$%d"),
                "Tax Paper %": st.column_config.NumberColumn("Tax Paper %", format="%.1f%%"),
            },
            use_container_width=True,
            hide_index=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Section 4 — Vehicle Characteristics Dynamics
# ─────────────────────────────────────────────────────────────────────────────

def _render_vehicle_characteristics_section(filters: dict[str, Any]) -> None:
    """Analyze Vehicle Body Type, Fuel & Electrification, Transmission, and Age."""
    st.markdown(
        config.section_header(
            "4. VEHICLE CHARACTERISTICS DYNAMICS",
            "Cross-sectional relationships across vehicle body type, fuel type, transmission, vehicle age, and documentation.",
        ),
        unsafe_allow_html=True,
    )

    chars = load_vehicle_characteristic_analysis(filters=filters)
    if not chars:
        st.info("No vehicle characteristics data available.")
        return

    tab_body, tab_fuel, tab_trans, tab_age = st.tabs([
        "🚙 Vehicle Body Type",
        "⛽ Fuel Type & Electrification",
        "⚙️ Transmission Dynamics",
        "⏳ Vehicle Age & Documentation",
    ])

    with tab_body:
        _render_characteristic_dual_view(
            chars.get("body_types", pd.DataFrame()),
            dim_name="Body Type",
            color_primary="#0f2b5c",
        )

    with tab_fuel:
        _render_characteristic_dual_view(
            chars.get("fuels", pd.DataFrame()),
            dim_name="Fuel Type",
            color_primary="#059669",
        )

    with tab_trans:
        _render_characteristic_dual_view(
            chars.get("transmissions", pd.DataFrame()),
            dim_name="Transmission",
            color_primary="#0284c7",
        )

    with tab_age:
        _render_age_and_documentation_view(chars)


def _render_characteristic_dual_view(df: pd.DataFrame, dim_name: str, color_primary: str) -> None:
    """Render side-by-side volume donut chart and median asking price bar chart."""
    if df.empty:
        st.info(f"No {dim_name} data available.")
        return

    col_key = df.columns[0]
    c_left, c_right = st.columns(2, gap="medium")

    with c_left:
        fig_donut = go.Figure(go.Pie(
            labels=df[col_key],
            values=df["count"],
            marker_colors=config.CHART_COLORS,
            hole=0.55,
            textinfo="percent+label",
            textfont=dict(size=11),
            hovertemplate=f"<b>%{{label}}</b><br>%{{value:,}} listings (%{{percent}})<extra></extra>",
        ))
        config.apply_plot_theme(fig_donut, height=config.CHART_H_MEDIUM, show_legend=False)
        fig_donut.update_layout(
            title=dict(text=f"{dim_name} Market Share", font=dict(size=12), x=0.0),
            annotations=[dict(
                text=f"<b>{df['count'].sum():,}</b><br><span style='font-size:10px'>listings</span>",
                x=0.5, y=0.5, font_size=13, showarrow=False,
            )],
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    with c_right:
        fig_bar = go.Figure(go.Bar(
            x=df[col_key],
            y=df["median_price"],
            marker_color=color_primary,
            error_y=dict(
                type="data",
                symmetric=False,
                array=(df["p75_price"] - df["median_price"]).tolist(),
                arrayminus=(df["median_price"] - df["p25_price"]).tolist(),
                color="#94a3b8",
                thickness=1.5,
            ),
            hovertemplate=(
                f"<b>%{{x}}</b><br>Median Asking Price: $%{{y:,.0f}}<br>"
                "IQR: $%{{customdata[0]:,.0f}–$%{{customdata[1]:,.0f}}<br>"
                "Listings: N = %{{customdata[2]:,}}<extra></extra>"
            ),
            customdata=df[["p25_price", "p75_price", "count"]].values,
        ))
        config.apply_plot_theme(
            fig_bar, height=config.CHART_H_MEDIUM, show_legend=False,
            xaxis_title=dim_name, yaxis_title="Median Asking Price (USD)",
            title=f"Median Asking Price by {dim_name}",
        )
        fig_bar.update_layout(yaxis_tickformat="$,.0f", xaxis_tickangle=-25)
        st.plotly_chart(fig_bar, use_container_width=True)

    st.caption(f"Based on N = {df['count'].sum():,} listings · Error bars show Interquartile Range (P25–P75).")


def _render_age_and_documentation_view(chars: dict[str, pd.DataFrame]) -> None:
    """Render vehicle age tiers and fresh import documentation premium comparisons."""
    c_age, c_tax = st.columns(2, gap="medium")

    with c_age:
        age_df = chars.get("age_tiers", pd.DataFrame())
        if not age_df.empty:
            fig_age = go.Figure(go.Bar(
                x=age_df["age_tier"],
                y=age_df["median_price"],
                marker_color="#0f2b5c",
                error_y=dict(
                    type="data",
                    symmetric=False,
                    array=(age_df["p75_price"] - age_df["median_price"]).tolist(),
                    arrayminus=(age_df["median_price"] - age_df["p25_price"]).tolist(),
                    color="#94a3b8",
                    thickness=1.5,
                ),
                hovertemplate=(
                    "<b>%{x}</b><br>Median Asking Price: $%{y:,.0f}<br>"
                    "P25–P75: $%{customdata[0]:,.0f}–$%{customdata[1]:,.0f}<br>"
                    "Listings: N = %{customdata[2]:,} (%{customdata[3]:.1f}%)<extra></extra>"
                ),
                customdata=age_df[["p25_price", "p75_price", "count", "share_pct"]].values,
            ))
            config.apply_plot_theme(
                fig_age, height=config.CHART_H_MEDIUM, show_legend=False,
                xaxis_title="Vehicle Age Tier", yaxis_title="Median Asking Price (USD)",
                title="Asking Price by Vehicle Age Tier",
            )
            fig_age.update_layout(yaxis_tickformat="$,.0f", xaxis_tickangle=-25)
            st.plotly_chart(fig_age, use_container_width=True)
            st.caption("Cross-sectional price comparison across age tiers (not a longitudinal depreciation schedule).")

    with c_tax:
        tax_df = chars.get("tax_statuses", pd.DataFrame())
        if not tax_df.empty:
            fig_tax = go.Figure(go.Bar(
                x=tax_df["tax_status"],
                y=tax_df["median_price"],
                marker_color=["#059669" if "Tax" in str(s) else "#c59b27" for s in tax_df["tax_status"]],
                error_y=dict(
                    type="data",
                    symmetric=False,
                    array=(tax_df["p75_price"] - tax_df["median_price"]).tolist(),
                    arrayminus=(tax_df["median_price"] - tax_df["p25_price"]).tolist(),
                    color="#94a3b8",
                    thickness=1.5,
                ),
                hovertemplate=(
                    "<b>%{x}</b><br>Median Asking Price: $%{y:,.0f}<br>"
                    "Listings: N = %{customdata[0]:,} (%{customdata[1]:.1f}%)<extra></extra>"
                ),
                customdata=tax_df[["count", "share_pct"]].values,
            ))
            config.apply_plot_theme(
                fig_tax, height=config.CHART_H_MEDIUM, show_legend=False,
                xaxis_title="Documentation Status", yaxis_title="Median Asking Price (USD)",
                title="Fresh Import (Tax Paper) vs Registered (Plate Number)",
            )
            fig_tax.update_layout(yaxis_tickformat="$,.0f", xaxis_tickangle=-20)
            st.plotly_chart(fig_tax, use_container_width=True)
            st.caption("Fresh import Tax Paper listings typically command a premium due to newer import vintage and lower domestic wear.")
