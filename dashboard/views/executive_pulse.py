"""
dashboard/views/executive_pulse.py
====================================
Page 1 — Overview
Executive summary of the Bronze → Silver pipeline.
KPIs, collection trend, quality distribution, cleaning funnel, missing rates.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from dashboard import config
from dashboard.data_loader import (
    load_bronze_volume,
    load_cleaning_impact_stats,
    load_completeness_detail,
    load_dbt_test_status,
    load_duplicate_stats,
    load_manifest,
    load_pipeline_funnel,
    load_quality_summary,
)


def render(active_date: str | None = None) -> None:
    """Render the Overview page."""
    manifest     = load_manifest()
    quality_df   = load_quality_summary()
    bronze_df    = load_bronze_volume()
    dbt_status   = load_dbt_test_status()
    dup_stats    = load_duplicate_stats()
    funnel_df    = load_pipeline_funnel(active_date)
    impact       = load_cleaning_impact_stats(active_date)
    complete_df  = load_completeness_detail(active_date)

    if quality_df.empty:
        st.warning(
            "⚠️ No Silver data found at `data/silver/cars_cleaned.parquet`. "
            "Run `dbt run` first to generate the Silver layer."
        )
        return

    # ── Active snapshot row ───────────────────────────────────────────────────
    if active_date:
        match = quality_df[quality_df["scrape_date"] == active_date]
        latest = match.iloc[0] if not match.empty else quality_df.iloc[0]
    else:
        latest = quality_df.iloc[0]

    total       = int(latest["total"])
    valid_cnt   = int(latest["valid"])
    warning_cnt = int(latest.get("warning", 0))
    susp_cnt    = int(latest.get("suspicious", 0))
    invalid_cnt = int(latest.get("invalid", 0))
    quar_cnt    = int(latest.get("quarantined", 0))
    dhi_score   = float(latest["dhi"])

    # Silver-ready = VALID + WARNING (has data, just optional fields missing)
    silver_ready_cnt = valid_cnt + warning_cnt
    silver_ready_pct = round(100.0 * silver_ready_cnt / total, 1) if total > 0 else 0.0
    valid_pct        = round(100.0 * valid_cnt / total, 1) if total > 0 else 0.0

    # Overall missing rate (average across all tracked fields)
    overall_missing_pct = 0.0
    if not complete_df.empty and "null_pct" in complete_df.columns:
        overall_missing_pct = round(float(complete_df["null_pct"].mean()), 1)

    # Invalid rate
    invalid_pct = round(100.0 * (invalid_cnt + quar_cnt) / total, 1) if total > 0 else 0.0

    # Day-over-day delta
    vol_delta_str = "Baseline day"
    if len(quality_df) >= 2:
        prev = int(quality_df.iloc[1]["total"])
        delta = total - prev
        delta_pct = round(100.0 * delta / prev, 1) if prev > 0 else 0.0
        vol_delta_str = f"{delta:+,} ({delta_pct:+.1f}% vs prev)"

    # Freshness
    freshness_hrs = None
    last_scrape_str = manifest.get("timestamp", "")
    if last_scrape_str:
        try:
            last_dt = datetime.fromisoformat(last_scrape_str.replace("Z", "+00:00"))
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            freshness_hrs = round((datetime.now(tz=timezone.utc) - last_dt).total_seconds() / 3600, 1)
        except ValueError:
            pass

    # ── Status banner ─────────────────────────────────────────────────────────
    _render_status_banner(dhi_score, freshness_hrs, quar_cnt, total, dbt_status, latest["scrape_date"])

    # ── KPI Cards ─────────────────────────────────────────────────────────────
    st.markdown(config.section_header("KEY PIPELINE METRICS", "Snapshot-level summary of the Bronze → Silver pipeline."), unsafe_allow_html=True)

    k1, k2, k3, k4, k5 = st.columns(5)

    with k1:
        b_total = dup_stats.get("bronze_total", 0)
        st.metric(
            "Raw Records",
            f"{b_total:,}",
            help="Total raw records scraped across all Bronze parquet files.",
        )
        st.caption("Bronze layer")

    with k2:
        st.metric(
            "Silver Records",
            f"{total:,}",
            delta=vol_delta_str,
            delta_color="normal" if "+" in vol_delta_str or vol_delta_str == "Baseline day" else "off",
            help="Records in the Silver conformed layer (all quality tiers).",
        )
        st.caption(f"Date: {latest['scrape_date']}")

    with k3:
        missing_color = "#dc2626" if overall_missing_pct > 20 else "#d97706" if overall_missing_pct > 5 else "#16a34a"
        st.metric(
            "Avg Missing Rate",
            f"{overall_missing_pct:.1f}%",
            help="Average missing rate across all tracked Silver fields.",
        )
        st.caption("Across all monitored fields")

    with k4:
        inv_color = "inverse" if invalid_pct > 5 else "off"
        st.metric(
            "Invalid Rate",
            f"{invalid_pct:.1f}%",
            help="Percentage of records classified INVALID or QUARANTINED.",
        )
        st.caption(f"{invalid_cnt + quar_cnt:,} records")

    with k5:
        ready_color = "normal" if silver_ready_pct >= 90 else "inverse"
        st.metric(
            "Silver Ready Rate",
            f"{silver_ready_pct:.1f}%",
            help="Records classified VALID or WARNING — suitable for downstream analytics.",
        )
        st.caption(f"{silver_ready_cnt:,} records")

    st.divider()

    # ── Trend + Quality Distribution ──────────────────────────────────────────
    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        _render_collection_trend(bronze_df, quality_df)

    with col_right:
        _render_quality_distribution(latest, total)

    st.divider()

    # ── Cleaning Funnel + Missing by Field ────────────────────────────────────
    col_funnel, col_missing = st.columns([2, 3], gap="large")

    with col_funnel:
        _render_pipeline_funnel(funnel_df)

    with col_missing:
        _render_missing_by_field(complete_df)

    st.divider()

    # ── Active Issues Table ───────────────────────────────────────────────────
    _render_active_issues(latest, total, complete_df, impact)


# ─────────────────────────────────────────────────────────────────────────────
# Sub-sections
# ─────────────────────────────────────────────────────────────────────────────

def _render_status_banner(
    dhi_score: float,
    freshness_hrs: float | None,
    quar_cnt: int,
    total: int,
    dbt_status: dict,
    snapshot_date: str,
) -> None:
    dbt_ok   = dbt_status.get("failed", 0) == 0 if dbt_status.get("available") else True
    fresh_ok = freshness_hrs is not None and freshness_hrs <= config.SLA_MAX_FRESHNESS_HOURS
    dhi_ok   = dhi_score >= config.SLA_MIN_DHI
    quar_pct = round(100.0 * quar_cnt / total, 2) if total > 0 else 0.0
    quar_ok  = quar_pct <= config.SLA_MAX_QUARANTINE_PCT

    gates_pass = sum([dbt_ok, fresh_ok, dhi_ok, quar_ok])

    if gates_pass == 4:
        bg, border = "#f0fdf4", "#16a34a"
        badge = "● ALL SYSTEMS OPERATIONAL"
        msg   = "All pipeline gates are within SLA bounds. No action required."
    elif not fresh_ok or not dbt_ok:
        bg, border = "#fef2f2", "#dc2626"
        badge = "● PIPELINE ATTENTION REQUIRED"
        issues = []
        if not fresh_ok:
            issues.append(f"Freshness SLA breached ({freshness_hrs:.1f}h, target < {config.SLA_MAX_FRESHNESS_HOURS:.0f}h)")
        if not dbt_ok:
            issues.append(f"dbt tests failing ({dbt_status.get('failed', '?')} failures)")
        msg = " · ".join(issues) + ". Downstream consumers may be receiving stale data."
    else:
        bg, border = "#fffbeb", "#d97706"
        badge = "● QUALITY DEGRADED — REVIEW RECOMMENDED"
        issues = []
        if not dhi_ok:
            issues.append(f"DHI {dhi_score:.1f}% below {config.SLA_MIN_DHI:.0f}% target")
        if not quar_ok:
            issues.append(f"Quarantine rate {quar_pct:.2f}% exceeds {config.SLA_MAX_QUARANTINE_PCT}% limit")
        msg = "Pipeline succeeded but data integrity is impaired: " + " · ".join(issues) + "."

    st.markdown(
        f"""
        <div style='background:{bg}; border-left:5px solid {border}; border-radius:6px;
                    padding:12px 16px; margin-bottom:18px;'>
            <div style='display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:8px;'>
                <div>
                    <span style='font-size:0.85rem; font-weight:700; color:{border}; letter-spacing:0.3px;'>{badge}</span>
                    <div style='font-size:0.82rem; color:#475569; margin-top:4px;'>{msg}</div>
                </div>
                <div style='text-align:right; font-size:0.75rem; color:#64748b;'>
                    <div><b>{gates_pass}/4</b> SLA gates passing</div>
                    <div>Snapshot: <b>{snapshot_date}</b></div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_collection_trend(bronze_df: pd.DataFrame, quality_df: pd.DataFrame) -> None:
    st.markdown(config.section_header("DATA COLLECTION TREND", "Daily raw vs Silver records collected."), unsafe_allow_html=True)

    if bronze_df.empty:
        st.info("No Bronze data available. Run the scraper first.")
        return

    df = bronze_df.copy()
    df["scrape_date"] = pd.to_datetime(df["scrape_date"])
    df = df.sort_values("scrape_date")

    # Merge Silver counts if available
    if not quality_df.empty:
        q = quality_df[["scrape_date", "total"]].copy()
        q["scrape_date"] = pd.to_datetime(q["scrape_date"])
        df = df.merge(q.rename(columns={"total": "silver_count"}), on="scrape_date", how="left")
    else:
        df["silver_count"] = None

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["scrape_date"],
        y=df["raw_count"],
        mode="lines+markers",
        name="Raw Records (Bronze)",
        line=dict(color="#0284c7", width=2.5),
        marker=dict(size=5),
        hovertemplate="<b>%{x|%d %b %Y}</b><br>Raw: <b>%{y:,}</b><extra></extra>",
    ))

    if df["silver_count"].notna().any():
        fig.add_trace(go.Scatter(
            x=df["scrape_date"],
            y=df["silver_count"],
            mode="lines+markers",
            name="Silver Records",
            line=dict(color="#16a34a", width=2.5, dash="dash"),
            marker=dict(size=5, symbol="diamond"),
            hovertemplate="<b>%{x|%d %b %Y}</b><br>Silver: <b>%{y:,}</b><extra></extra>",
        ))

    config.apply_plot_theme(fig, height=280, show_legend=True, legend_orientation="h")
    fig.update_layout(
        xaxis_title="Scrape Date",
        yaxis_title="Records",
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_quality_distribution(latest: pd.Series, total: int) -> None:
    st.markdown(config.section_header("DATA QUALITY DISTRIBUTION", "5-tier quality classification."), unsafe_allow_html=True)

    counts = {s: int(latest.get(s.lower(), 0)) for s in config.STATUS_ORDER}
    if sum(counts.values()) == 0:
        st.info("No quality status data available.")
        return

    labels = [f"{config.STATUS_DOT[s]} {s}" for s in config.STATUS_ORDER]
    values = [counts[s] for s in config.STATUS_ORDER]
    plot_colors = [
        "#16a34a", "#d97706", "#c2410c", "#dc2626", "#374151"
    ]

    valid_pct = round(100.0 * counts["VALID"] / total, 1) if total > 0 else 0.0
    center_color = "#16a34a" if valid_pct >= 90 else "#d97706" if valid_pct >= 75 else "#dc2626"

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        marker_colors=plot_colors,
        hole=0.6,
        textinfo="percent",
        textfont=dict(size=11),
        hovertemplate="<b>%{label}</b><br>Records: <b>%{value:,}</b><br>Share: %{percent}<extra></extra>",
        sort=False,
        pull=[0.04 if s == "VALID" else 0 for s in config.STATUS_ORDER],
    ))

    config.apply_plot_theme(fig, height=280, show_legend=True, legend_orientation="v")
    fig.update_layout(
        annotations=[dict(
            text=f"<b>{valid_pct}%</b><br><span style='font-size:10px'>VALID</span>",
            x=0.5, y=0.5, font_size=14, font_color=center_color,
            showarrow=False, align="center",
        )],
        margin=dict(l=0, r=60, t=10, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_pipeline_funnel(funnel_df: pd.DataFrame) -> None:
    st.markdown(config.section_header("PIPELINE FUNNEL", "Records through each transformation stage."), unsafe_allow_html=True)

    if funnel_df.empty:
        st.info("No pipeline funnel data available.")
        return

    # Filter to only Bronze→Silver stages (no Gold)
    silver_stages = [r for _, r in funnel_df.iterrows() if "Gold" not in r["stage"] and "ML" not in r["stage"]]

    if not silver_stages:
        silver_stages = [r for _, r in funnel_df.iterrows()]

    for row in silver_stages:
        count = int(row["count"])
        pct   = float(row["retention_pct"])
        stage = row["stage"].split(". ", 1)[-1]   # strip leading "1. "
        bar_w = max(10, int(pct))
        bar_color = "#1e3a8a" if pct >= 95 else "#d97706" if pct >= 85 else "#dc2626"
        st.markdown(
            f"""
            <div style='margin-bottom:10px;'>
                <div style='display:flex; justify-content:space-between; font-size:0.80rem;
                            font-weight:600; color:#334155; margin-bottom:3px;'>
                    <span>{stage}</span>
                    <span style='color:{bar_color};'>{count:,} &nbsp;·&nbsp; {pct:.1f}%</span>
                </div>
                <div style='background:#e2e8f0; border-radius:3px; height:8px;'>
                    <div style='width:{bar_w}%; background:{bar_color}; height:8px; border-radius:3px;'></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_missing_by_field(complete_df: pd.DataFrame) -> None:
    st.markdown(
        config.section_header("MISSING VALUES BY FIELD", "Missing rate per Silver field — sorted descending."),
        unsafe_allow_html=True,
    )

    if complete_df.empty:
        st.info("No completeness data available.")
        return

    # Sort descending by null_pct, take top 12
    df = complete_df.sort_values("null_pct", ascending=False).head(12).copy()

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
    df["field_label"] = df["field"].map(lambda f: field_labels.get(f, f))

    fig = go.Figure()
    bar_colors = [config.missing_color(p) for p in df["null_pct"]]

    fig.add_trace(go.Bar(
        y=df["field_label"],
        x=df["null_pct"],
        orientation="h",
        marker_color=bar_colors,
        text=[f"{p:.1f}%" for p in df["null_pct"]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Missing: %{x:.1f}%<extra></extra>",
    ))

    # Threshold reference lines
    fig.add_vline(x=5,  line_dash="dot", line_color="#16a34a", line_width=1.5,
                  annotation_text="5% (Good)", annotation_position="top right",
                  annotation_font=dict(size=9, color="#16a34a"))
    fig.add_vline(x=20, line_dash="dot", line_color="#d97706", line_width=1.5,
                  annotation_text="20% (Warning)", annotation_position="top right",
                  annotation_font=dict(size=9, color="#d97706"))

    config.apply_plot_theme(fig, height=320, show_legend=False)
    fig.update_layout(
        xaxis=dict(title="Missing Rate (%)", range=[0, max(105, df["null_pct"].max() + 8)]),
        yaxis=dict(autorange="reversed"),
        margin=dict(l=10, r=60, t=20, b=12),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_active_issues(
    latest: pd.Series,
    total: int,
    complete_df: pd.DataFrame,
    impact: dict,
) -> None:
    st.markdown(
        config.section_header("ACTIVE DATA ISSUES", "Known data quality issues detected from Silver DQ rules."),
        unsafe_allow_html=True,
    )

    issues = []
    issue_id = 1

    # Issue: Mileage missingness
    if not complete_df.empty:
        mileage_row = complete_df[complete_df["field"] == "vehicle_mileage_km"]
        if not mileage_row.empty:
            mp = float(mileage_row.iloc[0]["null_pct"])
            if mp > 0:
                severity = "CRITICAL" if mp > 80 else "HIGH" if mp > 20 else "MEDIUM"
                issues.append({
                    "Issue ID": f"DQ-{issue_id:03d}",
                    "Field": "vehicle_mileage_km",
                    "Issue": "Missing odometer mileage",
                    "Severity": severity,
                    "Affected Records": f"{int(mileage_row.iloc[0]['null_count']):,}",
                    "Missing %": f"{mp:.1f}%",
                    "Status": "Open",
                    "Note": "Cambodia sellers rarely disclose mileage in forms; NLP extraction in progress.",
                })
                issue_id += 1

        # Issue: Engine CC missingness
        eng_row = complete_df[complete_df["field"] == "vehicle_engine_cc"]
        if not eng_row.empty:
            ep = float(eng_row.iloc[0]["null_pct"])
            if ep > 0:
                severity = "HIGH" if ep > 50 else "MEDIUM" if ep > 10 else "LOW"
                issues.append({
                    "Issue ID": f"DQ-{issue_id:03d}",
                    "Field": "vehicle_engine_cc",
                    "Issue": "Missing engine displacement (cc)",
                    "Severity": severity,
                    "Affected Records": f"{int(eng_row.iloc[0]['null_count']):,}",
                    "Missing %": f"{ep:.1f}%",
                    "Status": "Open",
                    "Note": "Parsed from spec field and description; EVs correctly coded as 0 cc.",
                })
                issue_id += 1

        # Color missingness
        col_row = complete_df[complete_df["field"] == "vehicle_color"]
        if not col_row.empty:
            cp = float(col_row.iloc[0]["null_pct"])
            if cp > 5:
                issues.append({
                    "Issue ID": f"DQ-{issue_id:03d}",
                    "Field": "vehicle_color",
                    "Issue": "High color missingness",
                    "Severity": "MEDIUM" if cp < 20 else "HIGH",
                    "Affected Records": f"{int(col_row.iloc[0]['null_count']):,}",
                    "Missing %": f"{cp:.1f}%",
                    "Status": "In Progress",
                    "Note": "Seed color mapping covers main values; long tail unmapped.",
                })
                issue_id += 1

    # Issue: Down-payment traps
    dp_count = impact.get("down_payment_flagged", 0)
    if dp_count > 0:
        issues.append({
            "Issue ID": f"DQ-{issue_id:03d}",
            "Field": "price",
            "Issue": "Down-payment loan traps",
            "Severity": "HIGH",
            "Affected Records": f"{dp_count:,}",
            "Missing %": "—",
            "Status": "Flagged (SUSPICIOUS)",
            "Note": "Listings priced $500–$3,000 showing financing traps; classified SUSPICIOUS.",
        })
        issue_id += 1

    # Issue: Price outliers
    outlier_count = impact.get("outliers_flagged", 0)
    if outlier_count > 0:
        issues.append({
            "Issue ID": f"DQ-{issue_id:03d}",
            "Field": "price",
            "Issue": "Statistical price outliers",
            "Severity": "MEDIUM",
            "Affected Records": f"{outlier_count:,}",
            "Missing %": "—",
            "Status": "Flagged (SUSPICIOUS)",
            "Note": "Domain-grounded outlier detection; may be genuine luxury vehicles.",
        })
        issue_id += 1

    # Issue: Quarantined spam
    spam_count = impact.get("spam_flagged", 0)
    if spam_count > 0:
        issues.append({
            "Issue ID": f"DQ-{issue_id:03d}",
            "Field": "title_clean",
            "Issue": "Non-vehicle spam listings",
            "Severity": "HIGH",
            "Affected Records": f"{spam_count:,}",
            "Missing %": "—",
            "Status": "Quarantined",
            "Note": "Parts, accessories, and non-car listings detected by NLP spam classifier.",
        })
        issue_id += 1

    if not issues:
        st.success("No active data quality issues detected for the selected snapshot.")
        return

    issues_df = pd.DataFrame(issues)

    # Color-code Severity column
    severity_map = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢", "INFO": "🔵"}
    issues_df["Severity"] = issues_df["Severity"].map(lambda s: f"{severity_map.get(s,'●')} {s}")

    st.dataframe(
        issues_df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Issue ID":        st.column_config.TextColumn("Issue ID", width="small"),
            "Field":           st.column_config.TextColumn("Field", width="small"),
            "Issue":           st.column_config.TextColumn("Issue Description", width="medium"),
            "Severity":        st.column_config.TextColumn("Severity", width="small"),
            "Affected Records":st.column_config.TextColumn("Affected", width="small"),
            "Missing %":       st.column_config.TextColumn("Missing %", width="small"),
            "Status":          st.column_config.TextColumn("Status", width="small"),
            "Note":            st.column_config.TextColumn("Note / Action", width="large"),
        },
    )
