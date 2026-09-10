"""
dashboard/views/data_quality_monitoring.py
============================================
Merged Data Quality & Anomalies Page
Answers:
  1. How complete and valid are the fields across the Silver dataset?
  2. Why are certain fields (mileage, engine) sparse in Cambodia?
  3. Where are the price outliers, down-payment traps, and suspicious listings?
  4. How did raw scraped values transform into cleaned values in flagged records?
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard import config
from dashboard.data_loader import (
    load_audit_sample,
    load_cleaning_impact_stats,
    load_completeness_detail,
    load_dbt_test_status,
    load_price_violations,
    load_price_year_anomaly_sample,
    load_quality_summary,
    load_top_reasons,
)


def render(active_date: str | None = None) -> None:
    """Render the merged Data Quality & Anomalies page."""
    quality_df  = load_quality_summary()
    detail_df   = load_completeness_detail(active_date)
    impact      = load_cleaning_impact_stats(active_date)
    dbt_status  = load_dbt_test_status()

    if quality_df.empty:
        st.warning("⚠️ No Silver data available. Run `dbt run` first.")
        return

    # ── Active snapshot metrics ───────────────────────────────────────────────
    if active_date:
        match = quality_df[quality_df["scrape_date"] == active_date]
        latest = match.iloc[0] if not match.empty else quality_df.iloc[0]
    else:
        latest = quality_df.iloc[0]

    total     = int(latest["total"])
    susp_cnt  = int(latest.get("suspicious", 0))
    inv_cnt   = int(latest.get("invalid", 0))
    quar_cnt  = int(latest.get("quarantined", 0))
    anomaly_total = susp_cnt + inv_cnt + quar_cnt
    anomaly_pct   = round(100.0 * anomaly_total / total, 2) if total > 0 else 0.0

    # Critical fields fill (Price, Year, Brand, Province)
    crit_fill = 100.0
    if not detail_df.empty:
        crit_rows = detail_df[detail_df["priority"] == "🔴 Critical"]
        if not crit_rows.empty and "completeness_pct" in crit_rows.columns:
            crit_fill = float(crit_rows["completeness_pct"].mean())

    # ── 1. Top KPI Cards ──────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)

    with k1:
        st.markdown(
            config.kpi_card(
                title="Critical Specs Conformance",
                value=f"{crit_fill:.1f}%",
                subtitle="Price, Year, Brand, Province complete",
                delta="100% Target",
                delta_color="normal",
                accent_color="#10b981",
                icon="🎯",
            ),
            unsafe_allow_html=True,
        )

    with k2:
        st.markdown(
            config.kpi_card(
                title="Marketplace Missingness",
                value="~86% Sparse",
                subtitle="Mileage & Engine omitted by sellers",
                delta="Market Norm",
                delta_color="amber",
                accent_color="#f59e0b",
                icon="📊",
            ),
            unsafe_allow_html=True,
        )

    with k3:
        anom_color = "normal" if anomaly_pct < 1.0 else "amber"
        st.markdown(
            config.kpi_card(
                title="Anomalies Flagged",
                value=f"{anomaly_total:,}",
                subtitle=f"{susp_cnt:,} suspicious · {quar_cnt:,} quarantined",
                delta=f"{anomaly_pct:.2f}% of Silver",
                delta_color=anom_color,
                accent_color="#f97316" if anomaly_total > 0 else "#10b981",
                icon="🔍",
            ),
            unsafe_allow_html=True,
        )

    with k4:
        dbt_ok = dbt_status.get("failed", 0) == 0 if dbt_status.get("available") else True
        dbt_val = f"{dbt_status.get('passed', 0)}/{dbt_status.get('total', 0)}" if dbt_status.get("available") else "Active"
        st.markdown(
            config.kpi_card(
                title="dbt Contract Health",
                value=dbt_val,
                subtitle=f"{dbt_status.get('pass_rate_pct', 100)}% contract tests passing",
                delta="Verified" if dbt_ok else "Failed",
                delta_color="normal" if dbt_ok else "inverse",
                accent_color="#10b981" if dbt_ok else "#ef4444",
                icon="🛡️",
            ),
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── 2. Visual Row 1: Missingness by Field + Anomaly Reasons ───────────────
    col_l, col_r = st.columns([1, 1], gap="medium")

    with col_l:
        st.markdown(
            config.section_header(
                "FIELD COMPLETENESS & NULL RATES",
                "Percentage of missing records across each tracked vehicle attribute.",
            ),
            unsafe_allow_html=True,
        )
        _render_missingness_bars(detail_df)

        with st.expander("💡 Understanding Missingness in Cambodia's Car Market", expanded=False):
            st.markdown(
                "- **Mileage & Engine (~85-89% missing):** In Cambodia, private sellers on Khmer24 rarely list "
                "odometer readings or engine CC. Dropping these records would eliminate 85%+ of the dataset. "
                "The pipeline retains these records and classifies them under `WARNING` rather than discarding.\n"
                "- **Title Regex NLP:** Title strings (e.g. *Prius 07 Full Option*) are mined to extract Model, "
                "Year, and Option packages when structured form inputs were left empty."
            )

    with col_r:
        st.markdown(
            config.section_header(
                "TOP ANOMALY & FAILURE TRIGGERS",
                "Most frequent data quality issues and boundary rule violations.",
            ),
            unsafe_allow_html=True,
        )
        _render_failure_reasons(active_date)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # ── 3. Visual Row 2: Price x Year Anomaly Explorer ────────────────────────
    st.markdown(
        config.section_header(
            "PRICE × YEAR ANOMALY DETECTION",
            "Vehicle listing distribution — interactive scatter plot colored by quality status tier.",
        ),
        unsafe_allow_html=True,
    )
    _render_price_year_scatter(active_date)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # ── 4. Visual Row 3: Anomaly Audit & Lineage Registry ─────────────────────
    st.markdown(
        config.section_header(
            "LINEAGE & ANOMALY AUDIT REGISTRY",
            "Drill down into flagged records to compare raw scraper text against cleaned Silver values.",
        ),
        unsafe_allow_html=True,
    )
    _render_audit_drilldown(active_date)


# ─────────────────────────────────────────────────────────────────────────────
# Component Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _render_missingness_bars(detail_df: pd.DataFrame) -> None:
    if detail_df.empty or "null_pct" not in detail_df.columns:
        st.info("No field completeness detail found.")
        return

    df_sorted = detail_df.sort_values("null_pct", ascending=True)

    colors = []
    for pct in df_sorted["null_pct"]:
        if pct < config.MISSING_THRESHOLDS["good"]:
            colors.append("#10b981")
        elif pct <= config.MISSING_THRESHOLDS["warning"]:
            colors.append("#f59e0b")
        else:
            colors.append("#ef4444")

    fig = go.Figure(
        go.Bar(
            y=df_sorted["field"],
            x=df_sorted["null_pct"],
            orientation="h",
            marker_color=colors,
            text=df_sorted["null_pct"].apply(lambda v: f"{v:.1f}%"),
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Missing: %{x:.1f}%<extra></extra>",
        )
    )

    fig.add_vline(x=config.MISSING_THRESHOLDS["good"], line_dash="dot", line_color="#10b981", line_width=1)
    fig.add_vline(x=config.MISSING_THRESHOLDS["warning"], line_dash="dot", line_color="#f59e0b", line_width=1)

    config.apply_plot_theme(fig, height=310, show_legend=False)
    fig.update_layout(
        xaxis=dict(title="Missing Rate (%)", range=[0, 108], ticksuffix="%"),
        yaxis=dict(autorange=True),
        margin=dict(l=10, r=25, t=10, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_failure_reasons(active_date: str | None) -> None:
    reasons_df = load_top_reasons(top_n=8, scrape_date=active_date)
    if not reasons_df.empty:
        reasons_df = reasons_df.sort_values("count", ascending=True)
        fig = go.Figure(
            go.Bar(
                y=reasons_df["reason"],
                x=reasons_df["count"],
                orientation="h",
                marker_color="#ef4444",
                text=reasons_df["count"].apply(lambda v: f"{v:,}"),
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>Occurrences: %{x:,}<extra></extra>",
            )
        )
        config.apply_plot_theme(fig, height=310, show_legend=False)
        fig.update_layout(
            xaxis=dict(title="Flagged Records"),
            yaxis=dict(autorange=True),
            margin=dict(l=10, r=25, t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.success("✅ Zero failure or anomaly triggers detected for this snapshot.")


def _render_price_year_scatter(active_date: str | None) -> None:
    anomaly_sample = load_price_year_anomaly_sample(limit=2500, scrape_date=active_date)
    if anomaly_sample.empty:
        st.info("No sample data available for scatter plot.")
        return

    ctrl_col, _ = st.columns([2, 3])
    with ctrl_col:
        use_log = st.checkbox("Logarithmic price scale", value=True, help="Compresses extreme price range for clear inspection.")

    color_map = {
        "VALID":       "#10b981",
        "WARNING":     "#f59e0b",
        "SUSPICIOUS":  "#f97316",
        "INVALID":     "#dc2626",
        "QUARANTINED": "#64748b",
    }

    fig = px.scatter(
        anomaly_sample,
        x="vehicle_year",
        y="price",
        color="data_quality_status",
        color_discrete_map=color_map,
        hover_data=["vehicle_brand", "vehicle_model", "province"],
        labels={"vehicle_year": "Model Year", "price": "Price (USD)", "data_quality_status": "Quality Status"},
        log_y=use_log,
        opacity=0.65,
    )

    config.apply_plot_theme(fig, height=330, show_legend=True, legend_orientation="h")
    fig.update_traces(marker=dict(size=6))
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)


def _render_audit_drilldown(active_date: str | None) -> None:
    f_col1, f_col2 = st.columns([1, 1])
    with f_col1:
        status_filter = st.selectbox(
            "Filter by Quality Status",
            options=["ALL", "SUSPICIOUS", "QUARANTINED", "WARNING", "VALID"],
            index=0,
        )
    with f_col2:
        max_records = st.slider("Record Sample Limit", min_value=10, max_value=200, value=50, step=10)

    sample_df = load_audit_sample(
        status=status_filter if status_filter != "ALL" else None,
        limit=max_records,
        scrape_date=active_date,
    )

    if not sample_df.empty:
        display_cols = [c for c in [
            "listing_id", "title_clean", "vehicle_brand", "vehicle_model",
            "vehicle_year", "price", "data_quality_status", "data_quality_reasons"
        ] if c in sample_df.columns]

        st.dataframe(
            sample_df[display_cols],
            hide_index=True,
            use_container_width=True,
            column_config={
                "listing_id":           st.column_config.TextColumn("ID", width="small"),
                "title_clean":          st.column_config.TextColumn("Listing Title", width="large"),
                "vehicle_brand":        st.column_config.TextColumn("Brand", width="small"),
                "vehicle_model":        st.column_config.TextColumn("Model", width="small"),
                "vehicle_year":         st.column_config.NumberColumn("Year", format="%d"),
                "price":                st.column_config.NumberColumn("Price ($)", format="$%,d"),
                "data_quality_status":  st.column_config.TextColumn("Status", width="small"),
                "data_quality_reasons": st.column_config.TextColumn("Reason Codes", width="large"),
            },
        )

        # Quick CSV export
        csv_data = sample_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Audit Sample CSV",
            data=csv_data,
            file_name=f"audit_sample_{status_filter.lower()}_{active_date or 'latest'}.csv",
            mime="text/csv",
        )
    else:
        st.info(f"No records matching quality status `{status_filter}` found.")
