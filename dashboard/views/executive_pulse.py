"""
dashboard/views/executive_pulse.py
====================================
Merged Overview & Collection Monitoring Page
Answers:
  1. What is the pipeline health and data quality condition right now?
  2. What did the scraper collect and how fresh is the data?
  3. How does raw ingestion convert into conformed Silver records?
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
    load_dbt_test_status,
    load_duplicate_stats,
    load_manifest,
    load_pipeline_funnel,
    load_quality_summary,
    load_raw_ingestion_summary,
    load_scraper_health,
)


def render(active_date: str | None = None) -> None:
    """Render the merged Overview & Collection page."""
    manifest     = load_manifest()
    quality_df   = load_quality_summary()
    bronze_df    = load_bronze_volume()
    dbt_status   = load_dbt_test_status()
    dup_stats    = load_duplicate_stats()
    funnel_df    = load_pipeline_funnel(active_date)
    raw_summary  = load_raw_ingestion_summary()
    scraper      = load_scraper_health()

    if quality_df.empty:
        st.warning(
            "⚠️ No Silver data found at `data/silver/cars_cleaned.parquet`. "
            "Run `dbt run` first to process the Silver dataset."
        )
        return

    # ── Snapshot selection resolution ─────────────────────────────────────────
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
    snapshot_dt = str(latest["scrape_date"])

    # Silver-ready: VALID + WARNING (usable for analysis; warning only has missing optional fields like mileage)
    silver_ready_cnt = valid_cnt + warning_cnt
    silver_ready_pct = round(100.0 * silver_ready_cnt / total, 1) if total > 0 else 0.0

    # Bronze raw volume resolution
    b_total = dup_stats.get("bronze_total", int(bronze_df["raw_count"].sum()) if not bronze_df.empty else total)
    b_distinct = dup_stats.get("bronze_unique", raw_summary.get("total_distinct", total))

    # Day-over-day delta
    vol_delta_str = ""
    vol_delta_col = "normal"
    if len(quality_df) >= 2:
        prev = int(quality_df.iloc[1]["total"])
        delta = total - prev
        delta_pct = round(100.0 * delta / prev, 1) if prev > 0 else 0.0
        vol_delta_str = f"{delta:+,} ({delta_pct:+.1f}%)"
        vol_delta_col = "normal" if delta >= 0 else "amber"

    # Freshness calculation
    freshness_hrs = None
    last_scrape_str = scraper.get("last_run", "") or manifest.get("timestamp", "")
    if last_scrape_str:
        try:
            last_dt = datetime.fromisoformat(last_scrape_str.replace("Z", "+00:00"))
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            freshness_hrs = round((datetime.now(tz=timezone.utc) - last_dt).total_seconds() / 3600, 1)
        except ValueError:
            pass

    # ── 1. Pipeline Health Status Banner ──────────────────────────────────────
    _render_status_banner(dhi_score, freshness_hrs, quar_cnt, total, dbt_status, snapshot_dt)

    # ── 2. Top-Level Executive KPI Cards ──────────────────────────────────────
    fresh_badge = "Fresh" if (freshness_hrs is not None and freshness_hrs <= config.SLA_MAX_FRESHNESS_HOURS) else "Delayed"
    fresh_color = "normal" if fresh_badge == "Fresh" else "amber"
    fresh_val   = f"{freshness_hrs:.1f}h ago" if freshness_hrs is not None else "Active"

    dhi_label, dhi_delta_col = config.dhi_status(dhi_score)

    k1, k2, k3, k4, k5 = st.columns(5)

    with k1:
        st.markdown(
            config.kpi_card(
                title="Raw Ingested",
                value=f"{b_total:,}",
                subtitle=f"{b_distinct:,} distinct listings",
                accent_color="#0284c7",
                icon="📥",
            ),
            unsafe_allow_html=True,
        )

    with k2:
        st.markdown(
            config.kpi_card(
                title="Clean Conformed",
                value=f"{total:,}",
                subtitle=f"Snapshot: {snapshot_dt}",
                delta=vol_delta_str,
                delta_color=vol_delta_col,
                accent_color="#1e3a8a",
                icon="📦",
            ),
            unsafe_allow_html=True,
        )

    with k3:
        st.markdown(
            config.kpi_card(
                title="Pipeline Freshness",
                value=fresh_val,
                subtitle=f"SLA target: < {config.SLA_MAX_FRESHNESS_HOURS:.0f}h",
                delta=fresh_badge,
                delta_color=fresh_color,
                accent_color="#10b981" if fresh_badge == "Fresh" else "#f59e0b",
                icon="⏱️",
            ),
            unsafe_allow_html=True,
        )

    with k4:
        st.markdown(
            config.kpi_card(
                title="Data Health Index",
                value=f"{dhi_score:.1f}%",
                subtitle=f"Target: ≥ {config.SLA_MIN_DHI:.0f}% SLA",
                delta=dhi_label,
                delta_color=dhi_delta_col,
                accent_color="#10b981" if dhi_score >= config.SLA_MIN_DHI else "#f59e0b",
                icon="🛡️",
            ),
            unsafe_allow_html=True,
        )

    with k5:
        ready_col = "#10b981" if silver_ready_pct >= 95 else "#f59e0b"
        st.markdown(
            config.kpi_card(
                title="Ready for Analysis",
                value=f"{silver_ready_pct:.1f}%",
                subtitle=f"{silver_ready_cnt:,} VALID + WARNING",
                delta="Clean" if silver_ready_pct >= 95 else "Review",
                delta_color="normal" if silver_ready_pct >= 95 else "amber",
                accent_color=ready_col,
                icon="✅",
            ),
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── 3. Visual Row 1: Collection Trend + Quality Distribution ──────────────
    c_trend, c_pie = st.columns([3, 2], gap="medium")

    with c_trend:
        st.markdown(
            config.section_header(
                "DATA INGESTION & CONFORMANCE TREND",
                "Daily Bronze raw volume vs Silver conformed records with DHI health overlay.",
            ),
            unsafe_allow_html=True,
        )
        _render_collection_trend(bronze_df, quality_df)

    with c_pie:
        st.markdown(
            config.section_header(
                "QUALITY CLASSIFICATION BREAKDOWN",
                "Silver layer record status distribution across all 5 Medallion quality tiers.",
            ),
            unsafe_allow_html=True,
        )
        _render_quality_pie(valid_cnt, warning_cnt, susp_cnt, invalid_cnt, quar_cnt, total)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── 4. Visual Row 2: Pipeline Funnel + Ingestion Batches ───────────────────
    c_funnel, c_batches = st.columns([1, 1], gap="medium")

    with c_funnel:
        st.markdown(
            config.section_header(
                "MEDALLION PIPELINE FUNNEL",
                "Record retention from raw Khmer24 scraper to conformed Silver dataset.",
            ),
            unsafe_allow_html=True,
        )
        _render_funnel(funnel_df)

    with c_batches:
        st.markdown(
            config.section_header(
                "RECENT INGESTION BATCHES",
                "Latest raw Bronze partition files and scraper execution details.",
            ),
            unsafe_allow_html=True,
        )
        _render_batch_ledger(raw_summary, scraper)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── 5. SLA Contract Scorecard (Collapsible) ───────────────────────────────
    with st.expander("📋 SLA Contract Compliance Scorecard & Gate Details", expanded=False):
        _render_sla_scorecard(dhi_score, freshness_hrs, quar_cnt, total, dbt_status, manifest)


# ─────────────────────────────────────────────────────────────────────────────
# Component Render Helpers
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

    gates = [dbt_ok, fresh_ok, dhi_ok, quar_ok]
    gates_pass = sum(gates)

    if all(gates):
        bg, bar, fg = "#f0fdf4", "#16a34a", "#166534"
        badge = "● ALL SYSTEMS OPERATIONAL — 4/4 GATES COMPLIANT"
        msg   = (
            f"Silver layer conforming within SLA targets (DHI: {dhi_score:.1f}%). "
            f"Active conformed records: {total:,} · Zero critical test contract failures."
        )
    elif not fresh_ok or not dbt_ok:
        bg, bar, fg = "#fef2f2", "#dc2626", "#991b1b"
        badge = "● PIPELINE ATTENTION REQUIRED"
        issues = []
        if not fresh_ok and freshness_hrs is not None:
            issues.append(f"Scraper data is {freshness_hrs:.1f}h old (target < {config.SLA_MAX_FRESHNESS_HOURS:.0f}h)")
        if not dbt_ok:
            issues.append(f"{dbt_status.get('failed', '?')} dbt test contract failures")
        msg = " · ".join(issues)
    else:
        bg, bar, fg = "#fffbeb", "#d97706", "#92400e"
        badge = "● QUALITY MONITORING ALERT"
        issues = []
        if not dhi_ok:
            issues.append(f"DHI score ({dhi_score:.1f}%) below {config.SLA_MIN_DHI:.0f}% SLA target")
        if not quar_ok:
            issues.append(f"Quarantine rate ({quar_pct:.2f}%) exceeds {config.SLA_MAX_QUARANTINE_PCT}% limit")
        msg = " · ".join(issues)

    st.markdown(
        f"""
        <div style='background:{bg}; border:1px solid {bar}30; border-left:5px solid {bar};
                    border-radius:8px; padding:12px 18px; margin-bottom:16px;
                    display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;'>
            <div>
                <div style='font-size:0.85rem; font-weight:800; color:{fg}; letter-spacing:0.3px;'>
                    {badge}
                </div>
                <div style='font-size:0.78rem; color:#475569; margin-top:3px;'>
                    {msg}
                </div>
            </div>
            <div style='display:flex; gap:16px; align-items:center; flex-shrink:0;'>
                <div style='text-align:right;'>
                    <div style='font-size:1.15rem; font-weight:800; color:{fg};'>{gates_pass}/4</div>
                    <div style='font-size:0.65rem; font-weight:700; color:#64748b; text-transform:uppercase;'>SLA GATES</div>
                </div>
                <div style='text-align:right;'>
                    <div style='font-size:1.15rem; font-weight:800; color:#0f172a;'>{snapshot_date}</div>
                    <div style='font-size:0.65rem; font-weight:700; color:#64748b; text-transform:uppercase;'>SNAPSHOT</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_collection_trend(bronze_df: pd.DataFrame, quality_df: pd.DataFrame) -> None:
    if bronze_df.empty:
        st.info("No Bronze data recorded.")
        return

    df = bronze_df.copy()
    df["scrape_date"] = pd.to_datetime(df["scrape_date"])
    df = df.sort_values("scrape_date")

    if not quality_df.empty:
        q = quality_df[["scrape_date", "total", "dhi"]].copy()
        q["scrape_date"] = pd.to_datetime(q["scrape_date"])
        df = df.merge(q.rename(columns={"total": "silver_count"}), on="scrape_date", how="left")
    else:
        df["silver_count"] = None
        df["dhi"] = None

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Bronze raw volume bars
    fig.add_trace(
        go.Bar(
            x=df["scrape_date"],
            y=df["raw_count"],
            name="Raw Ingested (Bronze)",
            marker_color="#bae6fd",
            hovertemplate="<b>%{x|%d %b}</b><br>Raw Scraped: %{y:,}<extra></extra>",
        ),
        secondary_y=False,
    )

    # Silver conformed line
    if "silver_count" in df.columns and df["silver_count"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=df["scrape_date"],
                y=df["silver_count"],
                mode="lines+markers",
                name="Conformed (Silver)",
                line=dict(color="#1e3a8a", width=2.5),
                marker=dict(size=6, color="#1e3a8a"),
                hovertemplate="<b>%{x|%d %b}</b><br>Silver Conformed: %{y:,}<extra></extra>",
            ),
            secondary_y=False,
        )

    # DHI Trend Line (Secondary Y-axis)
    if "dhi" in df.columns and df["dhi"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=df["scrape_date"],
                y=df["dhi"],
                mode="lines+markers",
                name="Data Health Index (%)",
                line=dict(color="#10b981", width=2, dash="dot"),
                marker=dict(size=5, symbol="diamond", color="#10b981"),
                hovertemplate="DHI: %{y:.1f}%<extra></extra>",
            ),
            secondary_y=True,
        )
        fig.add_hline(
            y=config.SLA_MIN_DHI,
            line_dash="dash",
            line_color="rgba(16, 185, 129, 0.4)",
            line_width=1.5,
            secondary_y=True,
        )
        fig.update_yaxes(
            title_text="DHI (%)",
            secondary_y=True,
            range=[80, 102],
            showgrid=False,
            ticksuffix="%",
        )

    config.apply_plot_theme(fig, height=290, show_legend=True, legend_orientation="h")
    fig.update_layout(barmode="overlay", hovermode="x unified", margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)


def _render_quality_pie(valid: int, warn: int, susp: int, inv: int, quar: int, total: int) -> None:
    counts = [valid, warn, susp, inv, quar]
    labels = ["Valid", "Warning", "Suspicious", "Invalid", "Quarantined"]
    colors = ["#10b981", "#f59e0b", "#f97316", "#ef4444", "#64748b"]

    ready_pct = round(100.0 * (valid + warn) / total, 1) if total > 0 else 0.0
    center_c  = "#10b981" if ready_pct >= 90 else "#f59e0b"

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=counts,
            marker_colors=colors,
            hole=0.62,
            textinfo="percent",
            textfont=dict(size=11),
            hovertemplate="<b>%{label}</b><br>%{value:,} records (%{percent})<extra></extra>",
            sort=False,
        )
    )

    config.apply_plot_theme(fig, height=290, show_legend=True, legend_orientation="v")
    fig.update_layout(
        annotations=[
            dict(
                text=f"<b style='font-size:20px'>{ready_pct}%</b><br><span style='font-size:10px; color:#64748b;'>USABLE</span>",
                x=0.5,
                y=0.5,
                font_size=13,
                font_color=center_c,
                showarrow=False,
            )
        ],
        margin=dict(l=10, r=60, t=10, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_funnel(funnel_df: pd.DataFrame) -> None:
    if funnel_df.empty:
        st.info("No pipeline funnel data recorded.")
        return

    base_val = funnel_df["count"].iloc[0] if funnel_df["count"].iloc[0] > 0 else 1
    colors = ["#64748b", "#0284c7", "#6366f1", "#1e3a8a", "#10b981"]

    with st.container(border=True):
        for i, (_, row) in enumerate(funnel_df.iterrows()):
            cnt = int(row["count"])
            pct = round(100.0 * cnt / base_val, 1)
            w   = max(4, min(100, int(pct)))
            c   = colors[i % len(colors)]
            st.markdown(
                f"""
                <div style='margin-bottom:10px;'>
                    <div style='display:flex; justify-content:space-between; font-size:0.78rem; font-weight:700; color:#334155; margin-bottom:3px;'>
                        <span>{row['stage']}</span>
                        <span style='color:{c}; font-weight:800;'>{cnt:,} <span style='color:#94a3b8; font-weight:500;'>({pct:.1f}%)</span></span>
                    </div>
                    <div style='background:#f1f5f9; border-radius:4px; height:8px;'>
                        <div style='width:{w}%; background:{c}; height:8px; border-radius:4px;'></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_batch_ledger(raw_summary: dict, scraper: dict) -> None:
    batches_df = raw_summary.get("batches", pd.DataFrame())
    if not batches_df.empty:
        display_df = batches_df.head(6).copy()
        if "file_size_bytes" in display_df.columns:
            display_df["size_kb"] = (display_df["file_size_bytes"] / 1024).round(0).astype(int)
        else:
            display_df["size_kb"] = 0

        st.dataframe(
            display_df[["file_name", "records_ingested", "size_kb"]].rename(
                columns={
                    "file_name": "Parquet Batch",
                    "records_ingested": "Records",
                    "size_kb": "Size (KB)",
                }
            ),
            hide_index=True,
            use_container_width=True,
            column_config={
                "Parquet Batch": st.column_config.TextColumn("Partition File", width="medium"),
                "Records":       st.column_config.NumberColumn("Scraped", format="%,d"),
                "Size (KB)":     st.column_config.NumberColumn("Size", format="%,d KB"),
            },
        )
    else:
        st.info("No raw ingestion batch files discovered.")

    # Brief metadata strip
    duration = scraper.get("duration_seconds", 0.0)
    mode     = scraper.get("mode", "daily_incremental")
    st.caption(f"Last Scraper Run Mode: `{mode}` · Duration: `{duration:.1f}s` · Files: `{raw_summary.get('total_files', 0)}`")


def _render_sla_scorecard(dhi_score, freshness_hrs, quar_cnt, total, dbt_status, manifest) -> None:
    enrich_pct = manifest.get("quality_metrics", {}).get("detail_enrich_pct") if manifest else None
    dbt_passed = dbt_status.get("failed", 0) == 0 if dbt_status.get("available") else False
    quar_pct   = round(100.0 * quar_cnt / total, 2) if total > 0 else 0.0

    gates = [
        ("Data Health Index", f"≥ {config.SLA_MIN_DHI:.0f}%", dhi_score >= config.SLA_MIN_DHI, f"{dhi_score:.1f}%"),
        ("Daily Ingestion SLA", f"≥ {config.SLA_MIN_RECORDS_PER_DAY:,}", total >= config.SLA_MIN_RECORDS_PER_DAY, f"{total:,} recs"),
        ("Pipeline Freshness", f"< {config.SLA_MAX_FRESHNESS_HOURS:.0f}h", freshness_hrs is not None and freshness_hrs <= config.SLA_MAX_FRESHNESS_HOURS, f"{freshness_hrs:.1f}h ago" if freshness_hrs else "—"),
        ("Quarantine Ratio", f"< {config.SLA_MAX_QUARANTINE_PCT}%", quar_pct <= config.SLA_MAX_QUARANTINE_PCT, f"{quar_pct:.2f}%"),
        ("dbt Contract Tests", "All pass", dbt_passed, f"{dbt_status.get('passed', 0)}/{dbt_status.get('total', 0)}" if dbt_status.get("available") else "Not run"),
        ("Detail Enrichment", f"≥ {config.SLA_MIN_DETAIL_ENRICH_PCT:.0f}%", enrich_pct is not None and enrich_pct >= config.SLA_MIN_DETAIL_ENRICH_PCT, f"{enrich_pct:.1f}%" if enrich_pct is not None else "N/A"),
    ]

    cols = st.columns(6)
    for col, (label, target, passed, actual) in zip(cols, gates):
        bar_c = "#10b981" if passed else "#ef4444"
        bg_c  = "#f0fdf4" if passed else "#fef2f2"
        fg_c  = "#166534" if passed else "#991b1b"
        icon  = "✅" if passed else "❌"
        col.markdown(
            f"""
            <div style='background:{bg_c}; border:1px solid {bar_c}30; border-top:3px solid {bar_c};
                        border-radius:6px; padding:10px 8px; text-align:center;'>
                <div style='font-size:1.1rem; margin-bottom:2px;'>{icon}</div>
                <div style='font-size:0.68rem; font-weight:800; color:{fg_c}; line-height:1.2; margin-bottom:3px;'>{label}</div>
                <div style='font-size:0.78rem; font-weight:700; color:#0f172a;'>{actual}</div>
                <div style='font-size:0.62rem; color:#94a3b8; margin-top:2px;'>Target: {target}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
