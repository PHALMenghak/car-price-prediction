"""
dashboard/views/market_overview.py
==================================
Page 1 — Used Car Market Overview
Answers:
  1. What does the Cambodian used-car market look like in aggregate?
  2. What is the asking price distribution and where are prices concentrated?
  3. Which brands command the highest prices and volumes?
  4. How do vehicle prices behave across manufacturing vintages and body types?
"""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st

from dashboard import config
from dashboard.services import duckdb_service


def render(active_date: str | None = None) -> None:
    """Render the Used Car Market Overview page."""
    st.markdown(
        config.section_header(
            "USED CAR MARKET OVERVIEW",
            "Market intelligence from Cambodian used-car marketplace listings",
        ),
        unsafe_allow_html=True,
    )

    # ── 1. Top 6 KPI Cards Row ────────────────────────────────────────────────
    kpis = duckdb_service.get_market_kpis(active_date)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.markdown(
            config.kpi_card(
                title="Total Listings",
                value=config.format_number(kpis["total_listings"]),
                subtitle="Verified listings",
                accent_color="#2563eb",
                icon="🚗",
            ),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            config.kpi_card(
                title="Average Price",
                value=config.format_currency(kpis["avg_price"]),
                subtitle="Mean dealer asking",
                accent_color="#0f2b5c",
                icon="💵",
            ),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            config.kpi_card(
                title="Median Price",
                value=config.format_currency(kpis["median_price"]),
                subtitle="Market 50th percentile",
                accent_color="#10b981",
                icon="🎯",
            ),
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            config.kpi_card(
                title="Brands",
                value=config.format_number(kpis["unique_brands"]),
                subtitle="Active marques",
                accent_color="#6366f1",
                icon="🏷️",
            ),
            unsafe_allow_html=True,
        )
    with c5:
        st.markdown(
            config.kpi_card(
                title="Models",
                value=config.format_number(kpis["unique_models"]),
                subtitle="Vehicle variants",
                accent_color="#f59e0b",
                icon="🚙",
            ),
            unsafe_allow_html=True,
        )
    with c6:
        st.markdown(
            config.kpi_card(
                title="Average Age",
                value=f"{kpis['avg_age']:.1f} yrs",
                subtitle="Mean vehicle age",
                accent_color="#64748b",
                icon="📅",
            ),
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

    # ── 2. Row 1: Price Distribution & Average Price by Brand ─────────────────
    ch_col1, ch_col2 = st.columns([1.1, 1.3], gap="medium")

    with ch_col1:
        st.markdown(
            config.section_header(
                "PRICE DISTRIBUTION",
                "Histogram of asking prices (USD) across active marketplace inventory",
            ),
            unsafe_allow_html=True,
        )
        dist_df = duckdb_service.get_price_distribution(active_date)

        fig_dist = px.histogram(
            dist_df,
            x="price",
            nbins=35,
            color_discrete_sequence=["#2563eb"],
            labels={"price": "Asking Price (USD)"},
        )
        config.apply_plot_theme(fig_dist, height=330, show_legend=False, xaxis_title="Price (USD)", yaxis_title="Listings Count")
        fig_dist.update_layout(bargap=0.08)
        fig_dist.update_xaxes(tickprefix="$", tickformat=",.0f")
        fig_dist.add_vline(
            x=kpis["median_price"],
            line_dash="dash",
            line_color="#10b981",
            line_width=2,
            annotation_text=f"Median: ${kpis['median_price']:,.0f}",
            annotation_position="top right",
            annotation_font=dict(size=11, color="#10b981"),
        )
        st.plotly_chart(fig_dist, use_container_width=True)

    with ch_col2:
        h_left, h_right = st.columns([1.4, 1.3])
        with h_left:
            st.markdown(
                config.section_header(
                    "BRAND MARKET SHARE & VALUATION",
                    "Dominant volume leaders and high-valuation marques in Cambodia",
                ),
                unsafe_allow_html=True,
            )
        with h_right:
            c_b1, c_b2 = st.columns([1.3, 1.0])
            with c_b1:
                brand_mode = st.selectbox(
                    "Rank By:",
                    options=["Volume Leaders", "Highest Price"],
                    index=0,
                    key="sel_brand_mode",
                )
            with c_b2:
                top_n = st.selectbox("Top N:", options=[5, 10, 15, 20], index=1, key="sel_brand_top_n")

        sort_by = "volume" if brand_mode == "Volume Leaders" else "price"
        brand_df = duckdb_service.get_top_brands(sort_by=sort_by, top_n=top_n, active_date=active_date)

        if not brand_df.empty:
            if sort_by == "volume":
                if "listings" in brand_df.columns:
                    sort_col = "listings"
                elif "count" in brand_df.columns:
                    sort_col = "count"
                elif len(brand_df.columns) > 1:
                    sort_col = brand_df.columns[1]
                else:
                    sort_col = brand_df.columns[0]
            else:
                if "avg_price" in brand_df.columns:
                    sort_col = "avg_price"
                elif len(brand_df.columns) > 2:
                    sort_col = brand_df.columns[2]
                else:
                    sort_col = brand_df.columns[0]

            brand_df_sorted = brand_df.sort_values(sort_col, ascending=True)

            if sort_by == "volume":
                cnt_col = "listings" if "listings" in brand_df_sorted.columns else ("count" if "count" in brand_df_sorted.columns else sort_col)
                avg_col = "avg_price" if "avg_price" in brand_df_sorted.columns else None
                sh_col = "share_pct" if "share_pct" in brand_df_sorted.columns else None

                labels = []
                for _, r in brand_df_sorted.iterrows():
                    val = r[cnt_col]
                    sh_str = f" ({r[sh_col]:.1f}%)" if (sh_col and pd.notnull(r.get(sh_col))) else ""
                    avg_str = f" · ${r[avg_col]:,.0f} avg" if (avg_col and pd.notnull(r.get(avg_col))) else ""
                    labels.append(f"{int(val):,}{sh_str}{avg_str}")

                fig_brand = go.Figure(
                    go.Bar(
                        y=brand_df_sorted["vehicle_brand"],
                        x=brand_df_sorted[cnt_col],
                        orientation="h",
                        marker_color="#0f2b5c",
                        text=labels,
                        textposition="outside",
                        cliponaxis=False,
                    )
                )
                config.apply_plot_theme(fig_brand, height=330, show_legend=False, xaxis_title="Verified Listings Count")
                fig_brand.update_xaxes(tickformat=",.0f")
            else:
                avg_col = "avg_price" if "avg_price" in brand_df_sorted.columns else sort_col
                cnt_col = "listings" if "listings" in brand_df_sorted.columns else ("count" if "count" in brand_df_sorted.columns else None)

                labels = []
                for _, r in brand_df_sorted.iterrows():
                    val = r[avg_col]
                    cnt_str = f" ({int(r[cnt_col])} cars)" if (cnt_col and pd.notnull(r.get(cnt_col))) else ""
                    labels.append(f"${val:,.0f}{cnt_str}")

                fig_brand = go.Figure(
                    go.Bar(
                        y=brand_df_sorted["vehicle_brand"],
                        x=brand_df_sorted[avg_col],
                        orientation="h",
                        marker_color="#2563eb",
                        text=labels,
                        textposition="outside",
                        cliponaxis=False,
                    )
                )
                config.apply_plot_theme(fig_brand, height=330, show_legend=False, xaxis_title="Average Asking Price (USD)")
                fig_brand.update_xaxes(tickprefix="$", tickformat=",.0f")

            st.plotly_chart(fig_brand, use_container_width=True)

    st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

    # ── 3. Row 2: Price vs Year Scatter & Vehicle Type Donut ──────────────────
    ch_col3, ch_col4 = st.columns([1.4, 1.0], gap="medium")

    with ch_col3:
        st.markdown(
            config.section_header(
                "PRICE VS. MANUFACTURING YEAR",
                "Cross-sectional vintage asking prices showing depreciation patterns",
            ),
            unsafe_allow_html=True,
        )
        scatter_df = duckdb_service.get_price_vs_year_sample(limit=2500, active_date=active_date)

        fig_scatter = px.scatter(
            scatter_df,
            x="vehicle_year",
            y="price",
            color="vehicle_tax_type",
            color_discrete_map={"Tax Paper": "#c59b27", "Plate Number": "#2563eb"},
            hover_data=["vehicle_brand", "vehicle_model", "vehicle_body_type"],
            opacity=0.45,
            labels={"vehicle_year": "Manufacturing Year", "price": "Asking Price (USD)", "vehicle_tax_type": "Documentation"},
        )
        config.apply_plot_theme(fig_scatter, height=330, legend_orientation="h", xaxis_title="Manufacturing Year", yaxis_title="Price (USD)")
        fig_scatter.update_yaxes(tickprefix="$", tickformat=",.0f")
        st.plotly_chart(fig_scatter, use_container_width=True)

    with ch_col4:
        st.markdown(
            config.section_header(
                "VEHICLE TYPE BREAKDOWN",
                "Proportion of listings by vehicle body type",
            ),
            unsafe_allow_html=True,
        )
        type_df = duckdb_service.get_vehicle_type_distribution(active_date)

        fig_donut = go.Figure(
            go.Pie(
                labels=type_df["vehicle_body_type"],
                values=type_df["listings"],
                hole=0.55,
                marker=dict(colors=["#0f2b5c", "#2563eb", "#10b981", "#f59e0b", "#6366f1", "#64748b"]),
                textinfo="label+percent",
                hoverinfo="label+value+percent",
            )
        )
        config.apply_plot_theme(fig_donut, height=330, show_legend=False)
        st.plotly_chart(fig_donut, use_container_width=True)

    st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

    # ── Executive Automated Market Narrative ──────────────────────────────────
    seg_df = duckdb_service.get_price_segments(active_date)
    top_volume_brands = duckdb_service.get_top_brands(sort_by="volume", top_n=2, active_date=active_date)

    if not seg_df.empty:
        top_seg = seg_df.sort_values("count", ascending=False).iloc[0]
        seg_narrative = f"<b>{top_seg['price_segment']}</b> constitutes the largest transaction tier (<b>{top_seg['count']:,} vehicles, {top_seg['share']:.1f}%</b>)"
    else:
        seg_narrative = "Economy inventory constitutes the primary tier"

    if not top_volume_brands.empty:
        b1 = top_volume_brands.iloc[0]
        cnt1 = b1.get("listings", b1.get("count", 0))
        sh1 = b1.get("share_pct", 0)
        brand_narrative = f"<b>{b1['vehicle_brand']}</b> commanding the deepest market liquidity (<b>{int(cnt1):,} listings, {sh1:.1f}% share</b>)"
        if len(top_volume_brands) > 1:
            b2 = top_volume_brands.iloc[1]
            cnt2 = b2.get("listings", b2.get("count", 0))
            sh2 = b2.get("share_pct", 0)
            brand_narrative += f", followed by <b>{b2['vehicle_brand']}</b> (<b>{int(cnt2):,} listings, {sh2:.1f}% share</b>)"
    else:
        brand_narrative = "leading brands driving transaction volume"

    st.markdown(
        f"""
        <div style='background: #f8fafc; border: 1px solid #e2e8f0; border-left: 4px solid #0f2b5c;
                    border-radius: 6px; padding: 12px 16px; margin-bottom: 14px; font-size: 0.80rem; color: #334155; line-height: 1.6;'>
            <b>📊 Executive Market Summary:</b> The verified marketplace currently tracks <b>{config.format_number(kpis['total_listings'])}</b>
            active unique listings with a median asking price of <b>{config.format_currency(kpis['median_price'])}</b> (mean: <b>{config.format_currency(kpis['avg_price'])}</b>).
            The fleet has an average vintage age of <b>{kpis['avg_age']:.1f} years</b> across <b>{kpis['unique_brands']}</b> brands.
            {seg_narrative}, with {brand_narrative}.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

    # ── 4. Row 3: Market Intelligence Tabs ───────────────────────────────────
    tab_trends, tab_segments, tab_fuel, tab_cambodia = st.tabs([
        "📈 Inventory Volume & Price Movement",
        "🏷️ Asking Price Segmentation",
        "⚡ Fuel & Powertrain Dynamics",
        "🇰🇭 Tax Status & Regional Dynamics",
    ])

    with tab_trends:
        t_left, t_right = st.columns([2, 1])
        with t_left:
            st.markdown(
                config.section_header(
                    "MARKET LISTING TRENDS & PRICE DYNAMICS",
                    "Daily marketplace inventory volume and average price movement",
                ),
                unsafe_allow_html=True,
            )
        with t_right:
            range_preset = st.radio(
                "Time Range:",
                options=["7 Days", "30 Days", "90 Days", "1 Year", "All"],
                index=4,
                horizontal=True,
                key="radio_market_range",
            )

        trend_df = duckdb_service.get_market_trend(date_range_preset=range_preset)

        if not trend_df.empty:
            fig_trend = go.Figure()
            fig_trend.add_trace(
                go.Bar(
                    x=trend_df["date"],
                    y=trend_df["listings"],
                    name="Listings Volume",
                    marker_color="rgba(37, 99, 235, 0.3)",
                    yaxis="y",
                )
            )
            fig_trend.add_trace(
                go.Scatter(
                    x=trend_df["date"],
                    y=trend_df["avg_price"],
                    name="Avg Price (USD)",
                    line=dict(color="#0f2b5c", width=2.5),
                    mode="lines+markers",
                    yaxis="y2",
                )
            )

            fig_trend.update_layout(
                yaxis=dict(title="Daily Listings Volume", showgrid=True, gridcolor="rgba(0,0,0,0.05)"),
                yaxis2=dict(
                    title="Average Price (USD)",
                    overlaying="y",
                    side="right",
                    showgrid=False,
                    tickprefix="$",
                    tickformat=",.0f",
                ),
            )
            config.apply_plot_theme(fig_trend, height=300, legend_orientation="h")
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info("No time-series listing records available for the selected date window.")

    with tab_segments:
        st.markdown(
            config.section_header(
                "ASKING PRICE SEGMENTATION TIERS",
                "Distribution of vehicle inventory across commercial transaction price tiers",
            ),
            unsafe_allow_html=True,
        )
        c_seg_ch, c_seg_tb = st.columns([1.3, 1.0], gap="medium")

        with c_seg_ch:
            if not seg_df.empty:
                fig_seg = go.Figure(
                    go.Bar(
                        y=seg_df["price_segment"],
                        x=seg_df["count"],
                        orientation="h",
                        marker_color=["#10b981", "#2563eb", "#0f2b5c", "#c59b27"],
                        text=[f"{cnt:,} ({sh:.1f}%)" for cnt, sh in zip(seg_df["count"], seg_df["share"])],
                        textposition="outside",
                        cliponaxis=False,
                    )
                )
                config.apply_plot_theme(fig_seg, height=270, show_legend=False, xaxis_title="Vehicles Count")
                st.plotly_chart(fig_seg, use_container_width=True)

        with c_seg_tb:
            if not seg_df.empty:
                seg_display = seg_df.rename(columns={
                    "price_segment": "Segment",
                    "count": "Listings",
                    "avg_price": "Mean Price",
                    "median_price": "Median Price",
                    "share": "Share (%)",
                })
                seg_display["Mean Price"] = seg_display["Mean Price"].apply(config.format_currency)
                seg_display["Median Price"] = seg_display["Median Price"].apply(config.format_currency)
                seg_display["Share (%)"] = seg_display["Share (%)"].apply(lambda v: f"{v:.1f}%")
                st.dataframe(seg_display, hide_index=True, use_container_width=True)

    with tab_fuel:
        st.markdown(
            config.section_header(
                "FUEL & POWERTRAIN PRICE PREMIUM ANALYSIS",
                "Comparing marketplace volume, mean, and median asking prices across vehicle powertrains",
            ),
            unsafe_allow_html=True,
        )
        fuel_df = duckdb_service.get_fuel_premium_comparison(active_date)
        if not fuel_df.empty:
            f_col_l, f_col_r = st.columns([1.3, 1.0], gap="medium")
            with f_col_l:
                fig_fuel = go.Figure()
                fig_fuel.add_trace(
                    go.Bar(
                        x=fuel_df["fuel_type"],
                        y=fuel_df["median_price"],
                        name="Median Asking",
                        marker_color="#2563eb",
                    )
                )
                fig_fuel.add_trace(
                    go.Bar(
                        x=fuel_df["fuel_type"],
                        y=fuel_df["avg_price"],
                        name="Mean Asking",
                        marker_color="#0f2b5c",
                    )
                )
                config.apply_plot_theme(fig_fuel, height=270, legend_orientation="h", yaxis_title="Price (USD)")
                fig_fuel.update_yaxes(tickprefix="$", tickformat=",.0f")
                st.plotly_chart(fig_fuel, use_container_width=True)

            with f_col_r:
                fuel_disp = fuel_df.rename(columns={
                    "fuel_type": "Powertrain",
                    "count": "Volume",
                    "avg_price": "Mean Price",
                    "median_price": "Median Price",
                })
                fuel_disp["Mean Price"] = fuel_disp["Mean Price"].apply(config.format_currency)
                fuel_disp["Median Price"] = fuel_disp["Median Price"].apply(config.format_currency)
                st.dataframe(fuel_disp, hide_index=True, use_container_width=True)

    with tab_cambodia:
        st.markdown(
            config.section_header(
                "CAMBODIA MARKET DYNAMICS: TAX PAPER VS. PLATE & REGIONAL SPREAD",
                "Analyzing documentation pricing premiums and geographical inventory concentration",
            ),
            unsafe_allow_html=True,
        )
        c_cam_l, c_cam_r = st.columns([1.1, 1.3], gap="medium")

        with c_cam_l:
            st.markdown("##### 📄 Vehicle Documentation Status")
            tax_df = duckdb_service.get_tax_document_premium(active_date)
            if not tax_df.empty:
                fig_tax = go.Figure(
                    go.Bar(
                        x=tax_df["tax_status"],
                        y=tax_df["median_price"],
                        marker_color=["#2563eb", "#c59b27"],
                        text=[f"${m:,.0f}<br>({cnt:,} cars · {sh:.1f}%)" for m, cnt, sh in zip(tax_df["median_price"], tax_df["listings"], tax_df["share_pct"])],
                        textposition="outside",
                        cliponaxis=False,
                    )
                )
                config.apply_plot_theme(fig_tax, height=270, show_legend=False, yaxis_title="Median Price (USD)")
                fig_tax.update_yaxes(tickprefix="$", tickformat=",.0f")
                st.plotly_chart(fig_tax, use_container_width=True)

                st.caption(
                    "💡 **Market Reality:** Tax Paper (fresh imports) command a substantial price premium and represent newer inventory (avg 8.8 yrs vs 14.1 yrs for Plate Number)."
                )

        with c_cam_r:
            st.markdown("##### 📍 Geographic Inventory Distribution")
            reg_df = duckdb_service.get_regional_price_distribution(top_n=6, active_date=active_date)
            if not reg_df.empty:
                reg_disp = reg_df.rename(columns={
                    "province": "Province / Hub",
                    "listings": "Listings",
                    "share_pct": "Share (%)",
                    "median_price": "Median Price",
                    "avg_price": "Average Price",
                })
                reg_disp["Share (%)"] = reg_disp["Share (%)"].apply(lambda v: f"{v:.1f}%")
                reg_disp["Median Price"] = reg_disp["Median Price"].apply(config.format_currency)
                reg_disp["Average Price"] = reg_disp["Average Price"].apply(config.format_currency)
                st.dataframe(reg_disp, hide_index=True, use_container_width=True)

                st.caption(
                    "💡 **Phnom Penh Primacy:** Over 88% of all verified used-car listings in Cambodia are concentrated in the capital city."
                )

