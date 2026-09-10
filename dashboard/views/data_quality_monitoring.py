"""
dashboard/views/data_quality_monitoring.py
============================================
Page 4 — Data Quality
Detailed field-level quality monitoring across 5 dimensions:
Completeness, Validity, Consistency, Uniqueness, Trends.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard import config
from dashboard.data_loader import (
    load_cleaning_impact_stats,
    load_completeness_detail,
    load_daily_missingness_trend,
    load_duplicate_stats,
    load_quality_summary,
    load_reason_brand_matrix,
    load_top_reasons,
)


def render(active_date: str | None = None) -> None:
    """Render the Data Quality page."""
    quality_df  = load_quality_summary()
    detail_df   = load_completeness_detail(active_date)
    impact      = load_cleaning_impact_stats(active_date)
    trend_df    = load_daily_missingness_trend()
    dup_stats   = load_duplicate_stats()

    st.markdown(
        config.section_header(
            "DATA QUALITY",
            "Detailed field-level quality monitoring: Completeness · Validity · Consistency · Uniqueness.",
        ),
        unsafe_allow_html=True,
    )

    if detail_df.empty or quality_df.empty:
        st.warning("⚠️ No Silver data available. Run `dbt run` first.")
        return

    if active_date:
        match = quality_df[quality_df["scrape_date"] == active_date]
        latest = match.iloc[0] if not match.empty else quality_df.iloc[0]
    else:
        latest = quality_df.iloc[0]

    total     = int(latest["total"])
    valid_cnt = int(latest["valid"])
    warn_cnt  = int(latest.get("warning", 0))
    susp_cnt  = int(latest.get("suspicious", 0))
    inv_cnt   = int(latest.get("invalid", 0))
    quar_cnt  = int(latest.get("quarantined", 0))
    dhi_score = float(latest["dhi"])

    # ── Top KPIs ──────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)

    with k1:
        crit_df = detail_df[detail_df["priority"] == "🔴 Critical"]
        crit_fill = float(crit_df["completeness_pct"].mean()) if not crit_df.empty else 100.0
        color = "normal" if crit_fill >= 99.9 else "inverse"
        st.metric(
            "Critical Fields Fill Rate",
            f"{crit_fill:.1f}%",
            delta="100% target met" if crit_fill >= 99.9 else f"{100 - crit_fill:.1f}% gap",
            delta_color=color,
            help="Mandatory fields: Price, Scrape Date. Zero missing allowed.",
        )
        st.caption("Price · Scrape Date")

    with k2:
        high_df = detail_df[detail_df["priority"] == "🟠 High"]
        high_fill = float(high_df["completeness_pct"].mean()) if not high_df.empty else 100.0
        st.metric(
            "Core Vehicle Specs Fill",
            f"{high_fill:.1f}%",
            delta="High conformance" if high_fill >= 95 else "Review needed",
            delta_color="normal" if high_fill >= 95 else "off",
            help="Brand, Model, Year, Province — primary vehicle identity fields.",
        )
        st.caption("Brand · Model · Year · Province")

    with k3:
        anomalies = (
            impact.get("down_payment_flagged", 0)
            + impact.get("outliers_flagged", 0)
            + impact.get("spam_flagged", 0)
        ) if impact else 0
        st.metric(
            "Anomalies Detected",
            f"{anomalies:,}",
            delta=f"{impact.get('spam_flagged', 0):,} spam quarantined" if impact else "",
            delta_color="off",
            help="Down-payment traps + price outliers + spam listings.",
        )
        st.caption("SUSPICIOUS + QUARANTINED")

    with k4:
        dhi_label, _ = config.dhi_status(dhi_score)
        st.metric(
            "Data Health Index",
            f"{dhi_score:.1f}%",
            delta=dhi_label,
            delta_color="normal" if dhi_score >= config.SLA_MIN_DHI else "inverse",
            help="Composite quality score. Penalises QUARANTINED (×1.0), INVALID (×0.7), SUSPICIOUS (×0.3), WARNING (×0.03).",
        )
        st.caption(f"SLA target: ≥ {config.SLA_MIN_DHI:.0f}%")

    st.divider()

    # ── 1. Completeness ───────────────────────────────────────────────────────
    st.markdown(
        config.section_header("1 · COMPLETENESS", "Missing value rates and priority tier across all monitored fields."),
        unsafe_allow_html=True,
    )

    with st.expander("💡 Understanding Missingness in Cambodia's Used Car Market", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(
                "**Why is mileage missing in ~86% of listings?**\n"
                "Private sellers on Khmer24 rarely fill structured odometer fields. "
                "Dropping these records would eliminate 86% of the market. "
                "The pipeline retains all records and uses a missingness indicator flag instead."
            )
        with c2:
            st.markdown(
                "**Why are Brand and Model near 100% despite empty dropdowns?**\n"
                "Sellers frequently write free-text titles like *ឡានលក់ Prius 07* or *Lexus RX300 Full Option*. "
                "dbt regex + seed dictionaries extract and normalize 137+ models from Khmer/English/Chinese titles."
            )

    priority_filter = st.multiselect(
        "Filter by Priority Tier:",
        options=config.PRIORITY_ORDER,
        default=config.PRIORITY_ORDER,
    )
    df_filtered = detail_df[detail_df["priority"].isin(priority_filter)].copy()

    # Friendly field names
    field_labels = {
        "price": "Price (USD)", "scrape_date": "Scrape Date",
        "vehicle_brand": "Brand", "vehicle_model": "Model",
        "vehicle_year": "Year", "province": "Province",
        "vehicle_mileage_km": "Mileage (km)", "vehicle_engine_cc": "Engine Size (cc)",
        "vehicle_fuel_type": "Fuel Type", "vehicle_transmission": "Transmission",
        "vehicle_body_type": "Body Type", "vehicle_tax_type": "Tax Type",
        "vehicle_color": "Color", "vehicle_condition": "Condition",
        "description_clean": "Description",
    }
    df_filtered["Field Label"] = df_filtered["field"].map(lambda f: field_labels.get(f, f))

    # Status column
    df_filtered["Status"] = df_filtered["null_pct"].map(
        lambda p: f"{'🟢 Good' if p < config.MISSING_THRESHOLDS['good'] else '🟡 Warning' if p < config.MISSING_THRESHOLDS['warning'] else '🔴 Critical'}"
    )

    display_cols = ["priority", "Field Label", "completeness_pct", "null_pct",
                    "non_null_count", "null_count", "total_records", "Status"]
    available = [c for c in display_cols if c in df_filtered.columns]

    st.dataframe(
        df_filtered[available].rename(columns={"priority": "Priority", "Field Label": "Field",
                                               "completeness_pct": "Complete %", "null_pct": "Missing %",
                                               "non_null_count": "Populated", "null_count": "Missing",
                                               "total_records": "Total"}),
        hide_index=True,
        use_container_width=True,
        column_config={
            "Priority":   st.column_config.TextColumn("Priority", width="small"),
            "Field":      st.column_config.TextColumn("Field", width="medium"),
            "Complete %": st.column_config.ProgressColumn("Complete %", format="%.1f%%", min_value=0, max_value=100),
            "Missing %":  st.column_config.NumberColumn("Missing %", format="%.1f%%"),
            "Populated":  st.column_config.NumberColumn("Populated", format="%d"),
            "Missing":    st.column_config.NumberColumn("Missing", format="%d"),
            "Total":      st.column_config.NumberColumn("Total", format="%d"),
            "Status":     st.column_config.TextColumn("Status", width="small"),
        },
    )

    st.divider()

    # ── 2. Validity & Consistency ─────────────────────────────────────────────
    st.markdown(
        config.section_header("2 · VALIDITY & CONSISTENCY", "Rule violations, quality failure distribution, and brand × issue heatmap."),
        unsafe_allow_html=True,
    )

    col_reasons, col_trend_small = st.columns([3, 2], gap="large")

    with col_reasons:
        reasons_df = load_top_reasons(top_n=10, scrape_date=active_date)
        if not reasons_df.empty:
            reasons_df = reasons_df.sort_values("count", ascending=True)
            fig_r = go.Figure(go.Bar(
                y=reasons_df["reason"],
                x=reasons_df["count"],
                orientation="h",
                marker_color="#dc2626",
                text=reasons_df["count"].apply(lambda v: f"{v:,}"),
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>Records: %{x:,}<extra></extra>",
            ))
            config.apply_plot_theme(fig_r, height=300, show_legend=False)
            fig_r.update_layout(
                xaxis_title="Affected Records",
                title=dict(text="Top Quality Failure Reason Codes", font=dict(size=12)),
            )
            st.plotly_chart(fig_r, use_container_width=True)
        else:
            st.success("No quality failure codes detected for this snapshot.")

    with col_trend_small:
        # Quality tier mini summary
        st.markdown("**Quality Status Distribution**")
        tiers = [
            ("VALID",       valid_cnt, "#16a34a"),
            ("WARNING",     warn_cnt,  "#d97706"),
            ("SUSPICIOUS",  susp_cnt,  "#c2410c"),
            ("INVALID",     inv_cnt,   "#dc2626"),
            ("QUARANTINED", quar_cnt,  "#374151"),
        ]
        for label, cnt, color in tiers:
            pct = round(100.0 * cnt / total, 1) if total > 0 else 0.0
            bar_w = max(2, min(100, int(pct)))
            dot = config.STATUS_DOT.get(label, "●")
            st.markdown(
                f"""
                <div style='margin-bottom:8px;'>
                    <div style='display:flex; justify-content:space-between; font-size:0.78rem;
                                font-weight:600; color:#334155; margin-bottom:2px;'>
                        <span>{dot} {label}</span>
                        <span style='color:{color};'>{cnt:,} ({pct:.1f}%)</span>
                    </div>
                    <div style='background:#e2e8f0; border-radius:2px; height:6px;'>
                        <div style='width:{bar_w}%; background:{color}; height:6px; border-radius:2px;'></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Brand × Failure Heatmap
    matrix_df = load_reason_brand_matrix(top_n_brands=8, top_n_reasons=6)
    if not matrix_df.empty:
        st.markdown("**Vehicle Brand × Quality Failure Heatmap**")
        fig_hm = px.imshow(
            matrix_df,
            labels=dict(x="Failure Code", y="Vehicle Brand", color="Incidents"),
            color_continuous_scale="Reds",
            aspect="auto",
            text_auto=True,
        )
        config.apply_plot_theme(fig_hm, height=280, show_legend=False)
        st.plotly_chart(fig_hm, use_container_width=True)

    st.divider()

    # ── 3. Uniqueness ─────────────────────────────────────────────────────────
    st.markdown(
        config.section_header("3 · UNIQUENESS", "Duplicate observations and listing persistence across scrape dates."),
        unsafe_allow_html=True,
    )

    silver_daily = dup_stats.get("silver_daily", pd.DataFrame())
    persistence  = dup_stats.get("persistence", pd.DataFrame())

    col_uniq, col_persist = st.columns([3, 2], gap="large")

    with col_uniq:
        if not silver_daily.empty:
            silver_daily = silver_daily.copy()
            silver_daily["scrape_date"] = pd.to_datetime(silver_daily["scrape_date"].astype(str))
            silver_daily = silver_daily.sort_values("scrape_date")

            fig_u = go.Figure()
            fig_u.add_trace(go.Bar(
                x=silver_daily["scrape_date"],
                y=silver_daily["total_records"],
                name="Total Records",
                marker_color="#93c5fd",
                hovertemplate="%{x|%d %b}: %{y:,} total<extra></extra>",
            ))
            fig_u.add_trace(go.Bar(
                x=silver_daily["scrape_date"],
                y=silver_daily["unique_listings"],
                name="Unique Listings",
                marker_color="#1e3a8a",
                hovertemplate="%{x|%d %b}: %{y:,} unique<extra></extra>",
            ))
            config.apply_plot_theme(fig_u, height=260, show_legend=True, legend_orientation="h")
            fig_u.update_layout(barmode="group", xaxis_title="Date", yaxis_title="Records")
            st.plotly_chart(fig_u, use_container_width=True)
            st.caption(
                "ℹ️ The same `listing_id` may appear on multiple scrape dates (listing still active). "
                "This is correct behaviour — each row represents one listing observed on one date."
            )
        else:
            st.info("No Silver daily data available.")

    with col_persist:
        if not persistence.empty:
            st.markdown("**Listing Persistence (Days Active)**")
            fig_p = go.Figure(go.Bar(
                x=persistence["persistence_bucket"],
                y=persistence["listing_count"],
                marker_color=config.CHART_COLORS,
                text=[f"{c:,}" for c in persistence["listing_count"]],
                textposition="outside",
                hovertemplate="<b>%{x}</b><br>%{y:,} listings<extra></extra>",
            ))
            config.apply_plot_theme(fig_p, height=260, show_legend=False)
            fig_p.update_layout(xaxis_title="Days Seen Active", yaxis_title="Unique Listings")
            st.plotly_chart(fig_p, use_container_width=True)
        else:
            st.info("No persistence data available.")

    st.divider()

    # ── 4. Daily Missingness Trend ─────────────────────────────────────────────
    st.markdown(
        config.section_header("4 · DAILY QUALITY TREND", "Missing rate per field over time — detects pipeline drift."),
        unsafe_allow_html=True,
    )

    if not trend_df.empty:
        feature_cols = [c for c in trend_df.columns if c != "scrape_date"]
        colors = config.CHART_COLORS

        fig_trend = go.Figure()
        for col, color in zip(feature_cols, colors):
            fig_trend.add_trace(go.Scatter(
                x=trend_df["scrape_date"],
                y=trend_df[col],
                mode="lines+markers",
                name=col,
                line=dict(width=2.0, color=color),
                marker=dict(size=5),
                hovertemplate=f"<b>{col}</b><br>Date: %{{x}}<br>Missing: %{{y:.1f}}%<extra></extra>",
            ))

        # Threshold reference lines
        fig_trend.add_hline(y=5,  line_dash="dot", line_color="#16a34a", line_width=1,
                             annotation_text="5% Good", annotation_position="top right",
                             annotation_font=dict(size=9, color="#16a34a"))
        fig_trend.add_hline(y=20, line_dash="dot", line_color="#d97706", line_width=1,
                             annotation_text="20% Warning", annotation_position="top right",
                             annotation_font=dict(size=9, color="#d97706"))

        config.apply_plot_theme(fig_trend, height=300, show_legend=True, legend_orientation="h")
        fig_trend.update_layout(
            xaxis_title="Scrape Date",
            yaxis=dict(title="Missing Rate (%)", range=[-2, 105]),
            hovermode="x unified",
        )
        st.plotly_chart(fig_trend, use_container_width=True)
        st.caption(
            "Stable lines indicate a healthy, consistent pipeline. "
            "Sudden spikes suggest scraper changes or source-side data quality degradation."
        )
    else:
        st.info("Not enough historical data to render a trend chart (need ≥ 2 scrape dates).")
