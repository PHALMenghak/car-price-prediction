"""
dashboard/views/data_anomalies.py
===================================
Page 5 — Data Anomalies
Drill-down investigation of suspicious, invalid, and quarantined records.
Shows RAW → CLEAN comparison with filtering by severity, field, status, date.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard import config
from dashboard.data_loader import (
    load_audit_sample,
    load_price_violations,
    load_price_year_anomaly_sample,
    load_quality_summary,
    load_top_reasons,
)


def render(active_date: str | None = None) -> None:
    """Render the Data Anomalies page."""
    quality_df = load_quality_summary()

    st.markdown(
        config.section_header(
            "DATA ANOMALIES",
            "Drill-down into suspicious, invalid, and quarantined records. Compare RAW → CLEAN values.",
        ),
        unsafe_allow_html=True,
    )

    if quality_df.empty:
        st.warning("⚠️ No Silver data available. Run `dbt run` first.")
        return

    # Active snapshot metrics
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

    # ── Anomaly Summary KPIs ──────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        pct = round(100.0 * anomaly_total / total, 1) if total > 0 else 0.0
        st.metric("Total Anomalies", f"{anomaly_total:,}", help="SUSPICIOUS + INVALID + QUARANTINED records.")
        st.caption(f"{pct:.1f}% of Silver")
    with k2:
        st.metric("Suspicious", f"{susp_cnt:,}", help="Soft rule violations: price outliers, down-payments.")
        st.caption("Requires review")
    with k3:
        st.metric("Invalid", f"{inv_cnt:,}", help="Hard rule failures: invalid year, price < $500.")
        st.caption("Fails DQ rules")
    with k4:
        st.metric("Quarantined", f"{quar_cnt:,}", help="Schema-broken, spam, or NULL price — excluded from analytics.")
        st.caption("Excluded from Silver")

    st.divider()

    # ── Top Failure Reasons + Price Violations ────────────────────────────────
    col_l, col_r = st.columns(2, gap="large")

    with col_l:
        st.markdown(
            config.section_header("TOP FAILURE REASON CODES", "Most frequent data quality issues by occurrence."),
            unsafe_allow_html=True,
        )
        reasons_df = load_top_reasons(top_n=10, scrape_date=active_date)
        if not reasons_df.empty:
            reasons_df = reasons_df.sort_values("count", ascending=True)
            fig = go.Figure(go.Bar(
                y=reasons_df["reason"],
                x=reasons_df["count"],
                orientation="h",
                marker_color="#dc2626",
                text=reasons_df["count"].apply(lambda v: f"{v:,}"),
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>Records: %{x:,}<extra></extra>",
            ))
            config.apply_plot_theme(fig, height=320, show_legend=False)
            fig.update_layout(
                xaxis_title="Affected Records",
                yaxis=dict(autorange=True),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.success("No failure reason codes detected for this snapshot.")

    with col_r:
        st.markdown(
            config.section_header("PRICE BOUNDARY VIOLATIONS", "Breakdown of price-related data quality issues."),
            unsafe_allow_html=True,
        )
        price_df = load_price_violations(active_date)
        if not price_df.empty:
            fig = go.Figure(go.Bar(
                x=price_df["issue"],
                y=price_df["count"],
                marker_color="#d97706",
                text=price_df["count"].apply(lambda v: f"{v:,}"),
                textposition="outside",
                hovertemplate="<b>%{x}</b><br>Records: %{y:,}<extra></extra>",
            ))
            config.apply_plot_theme(fig, height=320, show_legend=False)
            fig.update_layout(xaxis_title=None, yaxis_title="Record Count")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.success("No price boundary violations detected.")

    st.divider()

    # ── Price vs Year Scatter ─────────────────────────────────────────────────
    st.markdown(
        config.section_header(
            "PRICE × YEAR ANOMALY EXPLORER",
            "Interactive scatter plot — colour-coded by anomaly type. Compare across all quality tiers.",
        ),
        unsafe_allow_html=True,
    )

    anomaly_sample = load_price_year_anomaly_sample(limit=3000, scrape_date=active_date)
    if not anomaly_sample.empty:
        ctrl_col, info_col = st.columns([2, 3])
        with ctrl_col:
            use_log = st.checkbox("Logarithmic price scale", value=True)
        with info_col:
            st.caption(f"Showing {len(anomaly_sample):,} sampled records coloured by anomaly classification.")

        color_map = {
            "Normal (Valid)":    "#16a34a",
            "Warning Spec":      "#d97706",
            "Down Payment Trap": "#f97316",
            "Price Below $500":  "#dc2626",
            "Invalid Year":      "#7c3aed",
            "Price Outlier":     "#9f1239",
        }
        fig_sc = px.scatter(
            anomaly_sample,
            x="vehicle_year",
            y="price",
            color="anomaly_group",
            color_discrete_map=color_map,
            hover_data=["listing_id", "vehicle_brand", "vehicle_model", "price", "vehicle_year", "data_quality_reasons"],
            log_y=use_log,
            labels={
                "vehicle_year":  "Model Year",
                "price":         "Asking Price (USD)",
                "anomaly_group": "Anomaly Class",
            },
        )
        config.apply_plot_theme(fig_sc, height=380, show_legend=True, legend_orientation="h")
        st.plotly_chart(fig_sc, use_container_width=True)
    else:
        st.info("No Price × Year data available.")

    st.divider()

    # ── Lineage Drill-Down Table ───────────────────────────────────────────────
    st.markdown(
        config.section_header(
            "RAW → CLEAN LINEAGE AUDIT",
            "Side-by-side comparison of Bronze raw values vs Silver conformed values for flagged records.",
        ),
        unsafe_allow_html=True,
    )

    # Filters
    f1, f2, f3, f4 = st.columns([2, 2, 1, 1])
    with f1:
        status_filter = st.multiselect(
            "Quality Status",
            options=config.STATUS_ORDER,
            default=["QUARANTINED", "INVALID", "SUSPICIOUS"],
            format_func=lambda s: f"{config.STATUS_DOT.get(s, '●')} {s}",
        )
    with f2:
        reason_search = st.text_input(
            "Filter by Reason Code",
            placeholder="e.g. MISSING_MILEAGE, DOWN_PAYMENT",
        )
    with f3:
        sample_limit = st.selectbox("Row limit", [50, 100, 200, 500], index=1)
    with f4:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)  # vertical spacer

    audit_df = load_audit_sample(
        statuses=status_filter,
        reason_filter=reason_search,
        scrape_date=active_date,
        limit=sample_limit,
    )

    if not audit_df.empty:
        st.caption(f"Showing **{len(audit_df):,}** records matching filters.")

        # Define preferred columns order; only show what's available
        preferred = [
            "listing_id", "scrape_date", "status", "reasons",
            "raw_brand", "clean_brand",
            "raw_model", "clean_model", "model_extraction_method",
            "raw_year",  "clean_year", "is_year_healed",
            "raw_price", "clean_price", "is_price_outlier", "is_down_payment",
            "clean_province", "raw_title", "title_clean", "listing_url",
        ]
        cols = [c for c in preferred if c in audit_df.columns]

        st.dataframe(
            audit_df[cols],
            hide_index=True,
            use_container_width=True,
            column_config={
                "listing_id":              st.column_config.TextColumn("Listing ID", width="small"),
                "scrape_date":             st.column_config.TextColumn("Date", width="small"),
                "status":                  st.column_config.TextColumn("Status", width="small"),
                "reasons":                 st.column_config.TextColumn("Reason Codes", width="medium"),
                "raw_brand":               st.column_config.TextColumn("Raw Brand", width="small"),
                "clean_brand":             st.column_config.TextColumn("Clean Brand", width="small"),
                "raw_model":               st.column_config.TextColumn("Raw Model", width="small"),
                "clean_model":             st.column_config.TextColumn("Clean Model", width="small"),
                "model_extraction_method": st.column_config.TextColumn("Source", width="small"),
                "raw_year":                st.column_config.TextColumn("Raw Year", width="small"),
                "clean_year":              st.column_config.NumberColumn("Clean Year", format="%d"),
                "is_year_healed":          st.column_config.CheckboxColumn("Healed?"),
                "raw_price":               st.column_config.TextColumn("Raw Price", width="small"),
                "clean_price":             st.column_config.NumberColumn("Clean Price ($)", format="$%,.0f"),
                "is_price_outlier":        st.column_config.CheckboxColumn("Outlier?"),
                "is_down_payment":         st.column_config.CheckboxColumn("Down Pmt?"),
                "clean_province":          st.column_config.TextColumn("Province", width="small"),
                "raw_title":               st.column_config.TextColumn("Raw Title", width="large"),
                "listing_url":             st.column_config.LinkColumn("URL"),
            },
        )

        csv_bytes = audit_df[cols].to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Export Anomaly Audit (CSV)",
            data=csv_bytes,
            file_name=f"anomaly_audit_{active_date or 'latest'}.csv",
            mime="text/csv",
        )
    else:
        st.success("✅ No records match the selected anomaly filters.")
