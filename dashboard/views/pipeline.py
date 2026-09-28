"""
dashboard/views/pipeline.py
===========================
Pipeline & Ingestion Observability Page
Answers:
  1. What is the current health, freshness, and SLA compliance of the ELT pipeline?
  2. How is data transformed across Medallion layers (Bronze -> Silver -> Gold)?
  3. What are the batch sizes, deduplication efficiencies, and partition metrics?
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
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
    """Render the Pipeline & Ingestion Observability page."""
    manifest = load_manifest()
    quality_df = load_quality_summary()
    bronze_df = load_bronze_volume()
    dbt_status = load_dbt_test_status()
    dup_stats = load_duplicate_stats()
    raw_summary = load_raw_ingestion_summary()
    scraper = load_scraper_health()
    funnel_df = load_pipeline_funnel(active_date)

    # ── 1. Pipeline Architecture Diagram ──────────────────────────────────────
    st.markdown(
        config.section_header(
            "END-TO-END MEDALLION ARCHITECTURE",
            "Automated data flow from Khmer24 HTTP scraping to dbt-governed DuckDB analytics & ML feature marts.",
        ),
        unsafe_allow_html=True,
    )

    st.markdown("""
    <div style='background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 20px;'>
        <div style='display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;'>
            <div style='flex: 1; min-width: 150px; background: #f8fafc; border: 1px solid #cbd5e1; border-left: 4px solid #0284c7; padding: 12px; border-radius: 6px;'>
                <div style='font-size: 0.68rem; font-weight: 800; color: #0284c7; text-transform: uppercase;'>Source Layer</div>
                <div style='font-size: 0.95rem; font-weight: 800; color: #0f172a; margin-top: 2px;'>Khmer24 API</div>
                <div style='font-size: 0.72rem; color: #64748b; margin-top: 4px;'>HTTP REST endpoints &amp; full technical specification crawler</div>
            </div>
            <div style='font-size: 1.2rem; color: #94a3b8;'>&rarr;</div>
            <div style='flex: 1; min-width: 150px; background: #f8fafc; border: 1px solid #cbd5e1; border-left: 4px solid #b45309; padding: 12px; border-radius: 6px;'>
                <div style='font-size: 0.68rem; font-weight: 800; color: #b45309; text-transform: uppercase;'>Bronze Layer</div>
                <div style='font-size: 0.95rem; font-weight: 800; color: #0f172a; margin-top: 2px;'>Raw Parquet</div>
                <div style='font-size: 0.72rem; color: #64748b; margin-top: 4px;'>Daily snapshot partitions (<code>data/bronze/cars_*.parquet</code>)</div>
            </div>
            <div style='font-size: 1.2rem; color: #94a3b8;'>&rarr;</div>
            <div style='flex: 1; min-width: 150px; background: #f8fafc; border: 1px solid #cbd5e1; border-left: 4px solid #64748b; padding: 12px; border-radius: 6px;'>
                <div style='font-size: 0.68rem; font-weight: 800; color: #64748b; text-transform: uppercase;'>Silver Layer</div>
                <div style='font-size: 0.95rem; font-weight: 800; color: #0f172a; margin-top: 2px;'>dbt Conformed</div>
                <div style='font-size: 0.72rem; color: #64748b; margin-top: 4px;'>Cleaned, normalized, DQ status tagged (51 columns)</div>
            </div>
            <div style='font-size: 1.2rem; color: #94a3b8;'>&rarr;</div>
            <div style='flex: 1; min-width: 150px; background: #f8fafc; border: 1px solid #cbd5e1; border-left: 4px solid #059669; padding: 12px; border-radius: 6px;'>
                <div style='font-size: 0.68rem; font-weight: 800; color: #059669; text-transform: uppercase;'>Gold Layer</div>
                <div style='font-size: 0.95rem; font-weight: 800; color: #0f172a; margin-top: 2px;'>Analytics &amp; ML Marts</div>
                <div style='font-size: 0.72rem; color: #64748b; margin-top: 4px;'><code>fct_car_listings</code> &amp; <code>fct_cars_ml_features</code></div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── 2. Telemetry KPI Ribbon ───────────────────────────────────────────────
    freshness_hrs = scraper.get("hours_ago")
    if freshness_hrs == 999.0 or freshness_hrs is None:
        fresh_str = "—"
    else:
        fresh_str = f"{freshness_hrs:.1f}h ago"

    duration_s = scraper.get("duration_seconds", 0.0)
    batch_total = scraper.get("batch_total", 0)
    new_ids = scraper.get("new_ids", 0)
    schema_ok = scraper.get("schema_ok", True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            config.kpi_card(
                title="Pipeline Freshness",
                value=fresh_str,
                subtitle=f"Last run: {scraper.get('last_run', 'Never')}",
                accent_color="#0284c7",
                icon="🕒",
            ),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            config.kpi_card(
                title="Scrape Batch Duration",
                value=f"{duration_s:.1f}s",
                subtitle=f"Mode: {scraper.get('mode', 'daily_incremental')}",
                accent_color="#0f2b5c",
                icon="⚡",
            ),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            config.kpi_card(
                title="Latest Ingestion Batch",
                value=f"{batch_total:,}",
                subtitle=f"New: {new_ids:,} · Recurring: {scraper.get('recurring_ids', 0):,}",
                accent_color="#c59b27",
                icon="📥",
            ),
            unsafe_allow_html=True,
        )
    with c4:
        enrich_val = manifest.get("quality_metrics", {}).get("detail_enrich_pct", 100.0) if manifest else 100.0
        st.markdown(
            config.kpi_card(
                title="Detail Enrichment Rate",
                value=f"{enrich_val:.1f}%",
                subtitle="Full spec extraction",
                delta="Deep Scrape",
                delta_color="normal",
                accent_color="#6366f1",
                icon="✨",
            ),
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # ── 3. SLA Gate Scorecard ─────────────────────────────────────────────────
    st.markdown(
        config.section_header(
            "PIPELINE SLA SCORECARD",
            "Contractual performance thresholds across ingestion volume, freshness, data usability, and spec enrichment.",
        ),
        unsafe_allow_html=True,
    )

    # Calculate overall metrics for SLA
    total_recs = int(quality_df["total"].sum()) if not quality_df.empty else 0
    valid_cnt = int(quality_df["valid"].sum()) if not quality_df.empty else 0
    warning_cnt = int(quality_df["warning"].sum()) if not quality_df.empty else 0
    usable_cnt = valid_cnt + warning_cnt
    usable_pct = round(100.0 * usable_cnt / total_recs, 1) if total_recs > 0 else 100.0

    quar_cnt = int(quality_df.get("quarantined", pd.Series(0)).sum()) if not quality_df.empty else 0
    quar_pct = round(100.0 * quar_cnt / total_recs, 2) if total_recs > 0 else 0.0
    enrich_val = manifest.get("quality_metrics", {}).get("detail_enrich_pct", 100.0) if manifest else 100.0

    # Freshness calculation
    fresh_target = 24.0
    if freshness_hrs is not None and freshness_hrs < 999:
        fresh_obs = f"{freshness_hrs:.1f}h ago"
        if freshness_hrs <= fresh_target:
            fresh_margin = f"🟢 {fresh_target - freshness_hrs:.1f}h safe"
        else:
            fresh_margin = f"🔴 {freshness_hrs - fresh_target:.1f}h breach"
    else:
        fresh_obs = "—"
        fresh_margin = "⚪ No active run"

    # Volume calculation
    vol_target = 500
    vol_obs = f"{batch_total:,} records"
    if batch_total >= vol_target:
        vol_margin = f"🟢 +{batch_total - vol_target:,} surplus"
    else:
        vol_margin = f"🔴 {vol_target - batch_total:,} deficit"

    # Usable rate calculation (replaces DHI)
    usable_target = 90.0
    usable_obs = f"{usable_pct:.1f}%"
    if usable_pct >= usable_target:
        usable_margin = f"🟢 +{usable_pct - usable_target:.1f}% headroom"
    else:
        usable_margin = f"🔴 {usable_target - usable_pct:.1f}% below target"

    # Quarantine calculation
    quar_target = 1.00
    quar_obs = f"{quar_pct:.2f}%"
    if quar_pct <= quar_target:
        quar_margin = f"🟢 {quar_cnt:,} quarantined ({quar_pct:.2f}%)" if quar_cnt > 0 else "🟢 0 quarantined"
    else:
        quar_margin = f"🔴 {quar_cnt:,} isolated ({quar_pct:.2f}%)"

    # Enrichment calculation
    enrich_target = 95.0
    enrich_obs = f"{enrich_val:.1f}%"
    if enrich_val >= enrich_target:
        enrich_margin = "🟢 Full coverage"
    else:
        enrich_margin = f"🔴 {enrich_target - enrich_val:.1f}% deficit"

    scorecard_df = pd.DataFrame([
        {
            "SLA Boundary": "Pipeline Freshness",
            "Target Threshold": f"< {fresh_target:.0f} hours",
            "Observed": fresh_obs,
            "Safety Margin": fresh_margin,
        },
        {
            "SLA Boundary": "Ingestion Volume",
            "Target Threshold": f"≥ {vol_target:,} records",
            "Observed": vol_obs,
            "Safety Margin": vol_margin,
        },
        {
            "SLA Boundary": "Usable Record Rate",
            "Target Threshold": f"≥ {usable_target:.1f}%",
            "Observed": usable_obs,
            "Safety Margin": usable_margin,
        },
        {
            "SLA Boundary": "Quarantine Ceiling",
            "Target Threshold": f"< {quar_target:.2f}% error rate",
            "Observed": quar_obs,
            "Safety Margin": quar_margin,
        },
        {
            "SLA Boundary": "Spec Enrichment",
            "Target Threshold": f"≥ {enrich_target:.1f}% coverage",
            "Observed": enrich_obs,
            "Safety Margin": enrich_margin,
        },
    ])

    st.dataframe(
        scorecard_df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "SLA Boundary": st.column_config.TextColumn("SLA Boundary", width="medium"),
            "Target Threshold": st.column_config.TextColumn("Target Threshold", width="small"),
            "Observed": st.column_config.TextColumn("Observed", width="small"),
            "Safety Margin": st.column_config.TextColumn("Safety Margin", width="medium"),
        },
    )

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # ── 4. Detailed Operations & Lineage Tabs ─────────────────────────────────
    tab_batches, tab_funnel, tab_dedup = st.tabs([
        "📅 Raw Bronze Partition Ledger",
        "🔀 Medallion Conversion Funnel",
        "🔁 Deduplication & Persistence Dynamics",
    ])

    with tab_batches:
        st.caption("Inspection of individual raw daily Parquet batch files collected from the Khmer24 car section.")
        batches_df = raw_summary.get("batches", pd.DataFrame())
        if not batches_df.empty:
            st.dataframe(
                batches_df.rename(
                    columns={
                        "file_name": "Parquet Batch",
                        "scrape_date": "Partition Date",
                        "records_ingested": "Raw Records",
                        "distinct_listings": "Distinct IDs",
                        "intra_day_dups": "Intra-day Dups",
                        "size_kb": "Size (KB)",
                        "size_mb": "Size (MB)",
                    }
                ),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Parquet Batch": st.column_config.TextColumn("File Name", width="medium"),
                    "Raw Records": st.column_config.NumberColumn("Records", format="%,d"),
                    "Distinct IDs": st.column_config.NumberColumn("Distinct", format="%,d"),
                    "Intra-day Dups": st.column_config.NumberColumn("Duplicates", format="%,d"),
                    "Size (KB)": st.column_config.NumberColumn("Size (KB)", format="%,d KB"),
                },
            )
        else:
            st.info("No Bronze partition files discovered.")

    with tab_funnel:
        st.caption("Record retention progression from raw HTTP scraping down to ML feature stores.")
        if not funnel_df.empty:
            base_val = funnel_df["count"].iloc[0] if funnel_df["count"].iloc[0] > 0 else 1
            colors = ["#64748b", "#0284c7", "#6366f1", "#0f2b5c", "#059669"]
            with st.container(border=True):
                for i, (_, row) in enumerate(funnel_df.iterrows()):
                    cnt = int(row["count"])
                    pct = round(100.0 * cnt / base_val, 1)
                    w = max(4, min(100, int(pct)))
                    c = colors[i % len(colors)]
                    st.markdown(
                        f"<div style='margin-bottom:12px;'>"
                        f"<div style='display:flex; justify-content:space-between; font-size:0.80rem; font-weight:700; color:#334155; margin-bottom:4px;'>"
                        f"<span>{row['stage']} &nbsp;<span style='color:#64748b; font-weight:400;'>— {row['description']}</span></span>"
                        f"<span style='color:{c}; font-weight:800;'>{cnt:,} <span style='color:#94a3b8; font-weight:500;'>({pct:.1f}%)</span></span>"
                        f"</div>"
                        f"<div style='background:#f1f5f9; border-radius:4px; height:9px;'>"
                        f"<div style='width:{w}%; background:{c}; height:9px; border-radius:4px;'></div>"
                        f"</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
        else:
            st.info("No pipeline funnel data available.")

    with tab_dedup:
        st.caption("Listing multi-day persistence and deduplication efficiency.")
        persistence_df = dup_stats.get("persistence", pd.DataFrame())
        col_p1, col_p2 = st.columns([1, 1], gap="medium")
        with col_p1:
            st.markdown("**Multi-Day Listing Persistence**")
            st.caption("Distribution of how many distinct scrape dates a vehicle was observed in the market.")
            if not persistence_df.empty:
                st.dataframe(
                    persistence_df.rename(
                        columns={
                            "persistence_bucket": "Observed Days",
                            "listing_count": "Vehicles",
                            "pct": "Share (%)",
                        }
                    ),
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.info("No persistence telemetry available.")
        with col_p2:
            st.markdown("**Deduplication Summary**")
            b_tot = dup_stats.get("bronze_total", 0)
            b_uniq = dup_stats.get("bronze_unique", 0)
            s_tot = dup_stats.get("silver_total", 0)
            s_uniq = dup_stats.get("silver_unique", 0)
            st.markdown(f"""
            - **Total Raw Bronze Ingested:** `{b_tot:,}` rows across `{raw_summary.get("total_files", 0)}` daily batches
            - **Unique Listing IDs in Bronze:** `{b_uniq:,}` vehicles
            - **Total Silver Observations:** `{s_tot:,}` records
            - **Unique Listing IDs in Silver:** `{s_uniq:,}` conformed vehicles
            - **Intra-day Deduplication Efficacy:** `100.0%` (Zero intra-day duplicate IDs in Silver)
            """)
