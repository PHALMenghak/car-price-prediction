"""
dashboard/views/collection_monitoring.py
=========================================
Page 2 — Collection Monitoring
Answers: What did the scraper collect?
Monitors raw data collection, ingestion health, freshness, and batch ledger.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard import config
from dashboard.data_loader import (
    load_bronze_volume,
    load_duplicate_stats,
    load_manifest,
    load_raw_ingestion_summary,
    load_scraper_health,
)


def render(active_date: str | None = None) -> None:
    """Render the Collection Monitoring page."""
    manifest     = load_manifest()
    scraper      = load_scraper_health()
    raw_summary  = load_raw_ingestion_summary()
    dup_stats    = load_duplicate_stats()
    bronze_df    = load_bronze_volume()

    st.markdown(
        config.section_header(
            "COLLECTION MONITORING",
            "What did the scraper collect? Raw data ingestion, freshness, and deduplication.",
        ),
        unsafe_allow_html=True,
    )

    # ── Freshness ─────────────────────────────────────────────────────────────
    freshness_hrs = None
    last_scrape_str = scraper.get("last_run", "")
    ts_raw = manifest.get("timestamp", "")
    if ts_raw:
        try:
            last_dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            freshness_hrs = round((datetime.now(tz=timezone.utc) - last_dt).total_seconds() / 3600, 1)
        except ValueError:
            pass

    # Freshness classification
    if freshness_hrs is None:
        fresh_label, fresh_color, fresh_bg = "Unknown", "#64748b", "#f1f5f9"
    elif freshness_hrs <= config.SLA_MAX_FRESHNESS_HOURS:
        fresh_label, fresh_color, fresh_bg = "Fresh", "#166534", "#dcfce7"
    elif freshness_hrs <= 24:
        fresh_label, fresh_color, fresh_bg = "Delayed", "#92400e", "#fef9c3"
    elif freshness_hrs <= 72:
        fresh_label, fresh_color, fresh_bg = "Stale", "#c2410c", "#ffedd5"
    else:
        fresh_label, fresh_color, fresh_bg = "Missing", "#991b1b", "#fee2e2"

    # ── KPI Cards ─────────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5 = st.columns(5)

    with k1:
        latest_run = scraper.get("last_run", "—")
        st.metric(
            "Latest Scrape",
            latest_run[:10] if latest_run and len(latest_run) >= 10 else latest_run or "—",
            help="Date of the most recent scrape run from ingestion_manifest.json.",
        )
        st.markdown(
            f"<span style='background:{fresh_bg}; color:{fresh_color}; padding:2px 7px; "
            f"border-radius:3px; font-size:0.72rem; font-weight:700;'>● {fresh_label}</span>",
            unsafe_allow_html=True,
        )

    with k2:
        b_total = raw_summary.get("total_records", 0)
        st.metric(
            "Raw Records (All-time)",
            f"{b_total:,}",
            help="Total raw records in all Bronze parquet files.",
        )
        st.caption(f"{raw_summary.get('total_files', 0)} parquet files")

    with k3:
        b_distinct = raw_summary.get("total_distinct", 0)
        st.metric(
            "Unique Listings",
            f"{b_distinct:,}",
            help="Distinct listing_id values across all Bronze files.",
        )
        st.caption("Distinct listing IDs")

    with k4:
        new_ids = scraper.get("new_ids", 0)
        recur   = scraper.get("recurring_ids", 0)
        st.metric(
            "New Listings (Last Run)",
            f"{new_ids:,}",
            delta=f"{recur:,} recurring",
            delta_color="off",
            help="New listing IDs discovered in the most recent scrape run.",
        )
        st.caption(f"Batch total: {scraper.get('batch_total', 0):,}")

    with k5:
        duration = scraper.get("duration_seconds", 0.0)
        st.metric(
            "Scrape Duration",
            f"{duration:.0f}s" if duration else "—",
            help="Runtime of the most recent scrape job.",
        )
        mode = scraper.get("mode", "—")
        st.caption(f"Mode: {mode}")

    st.divider()

    # ── Freshness & Collection Health Banner ──────────────────────────────────
    st.markdown(
        config.section_header("INGESTION HEALTH", "Freshness and pipeline connectivity status."),
        unsafe_allow_html=True,
    )

    c_fresh, c_schema = st.columns(2, gap="large")

    with c_fresh:
        with st.container(border=True):
            st.markdown("**Data Freshness**")
            if freshness_hrs is not None:
                st.markdown(
                    f"<div style='font-size:2rem; font-weight:700; color:{fresh_color};'>"
                    f"{freshness_hrs:.1f}h ago</div>",
                    unsafe_allow_html=True,
                )
                st.caption(f"Last scrape: {last_scrape_str}")
                sla_pct = min(100, int(100 * config.SLA_MAX_FRESHNESS_HOURS / max(freshness_hrs, 0.1)))
                bar_color = fresh_color
                st.markdown(
                    f"""
                    <div style='margin-top:8px; font-size:0.78rem; color:#64748b;'>
                        SLA: &lt; {config.SLA_MAX_FRESHNESS_HOURS:.0f}h
                    </div>
                    <div style='background:#e2e8f0; border-radius:3px; height:6px; margin-top:4px;'>
                        <div style='width:{min(sla_pct,100)}%; background:{bar_color}; height:6px; border-radius:3px;'></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.warning("No ingestion manifest found. Run the scraper.")

    with c_schema:
        with st.container(border=True):
            st.markdown("**Schema Integrity**")
            schema_ok = scraper.get("schema_ok", True)
            if schema_ok:
                st.success("✅ All required Bronze columns present. Zero schema drift.")
            else:
                st.error("🚨 Schema drift detected!")
            st.caption(scraper.get("schema_details", ""))
            st.markdown(
                "Required columns: `listing_id` · `raw_title` · `raw_price` · "
                "`raw_spec_brand` · `raw_spec_model` · `raw_spec_year`"
            )

    st.divider()

    # ── Daily Collection Trend ────────────────────────────────────────────────
    st.markdown(
        config.section_header("DAILY COLLECTION TREND", "Raw records, unique listings, and deduplication per day."),
        unsafe_allow_html=True,
    )

    bronze_daily = dup_stats.get("bronze_daily", pd.DataFrame())

    if not bronze_daily.empty:
        bronze_daily = bronze_daily.copy()
        bronze_daily["scrape_date"] = pd.to_datetime(bronze_daily["scrape_date"].astype(str))
        bronze_daily = bronze_daily.sort_values("scrape_date")

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=bronze_daily["scrape_date"],
            y=bronze_daily["raw_records"],
            name="Raw Records",
            marker_color="#93c5fd",
            hovertemplate="<b>%{x|%d %b}</b><br>Raw: <b>%{y:,}</b><extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=bronze_daily["scrape_date"],
            y=bronze_daily["unique_listings"],
            name="Unique Listings",
            marker_color="#1e3a8a",
            hovertemplate="<b>%{x|%d %b}</b><br>Unique: <b>%{y:,}</b><extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=bronze_daily["scrape_date"],
            y=bronze_daily["intra_day_duplicates"],
            name="Intra-Day Duplicates",
            mode="lines+markers",
            line=dict(color="#dc2626", width=1.8, dash="dot"),
            marker=dict(size=5),
            hovertemplate="<b>%{x|%d %b}</b><br>Duplicates: <b>%{y:,}</b><extra></extra>",
        ))

        config.apply_plot_theme(fig, height=300, show_legend=True, legend_orientation="h")
        fig.update_layout(
            barmode="group",
            xaxis_title="Scrape Date",
            yaxis_title="Record Count",
            hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Summary caption
        total_dups = int(bronze_daily["intra_day_duplicates"].sum())
        if total_dups > 0:
            st.caption(
                f"ℹ️ {total_dups:,} intra-day duplicate records were absorbed by the dbt staging layer "
                f"(`ROW_NUMBER() OVER (PARTITION BY listing_id, scrape_date ORDER BY scraped_at DESC) = 1`). "
                "Zero downstream double-counting."
            )
    else:
        st.info("No Bronze parquet files found. Run the scraper to collect data.")

    st.divider()

    # ── Manifest Details ──────────────────────────────────────────────────────
    st.markdown(
        config.section_header("INGESTION MANIFEST", "Latest run metadata from `ingestion_manifest.json`."),
        unsafe_allow_html=True,
    )

    if manifest:
        qm = manifest.get("quality_metrics", {})
        m_c1, m_c2, m_c3 = st.columns(3, gap="medium")

        with m_c1:
            with st.container(border=True):
                st.markdown("**Run Summary**")
                st.markdown(
                    f"- **Timestamp:** {manifest.get('timestamp', '—')[:16].replace('T', ' ')} UTC\n"
                    f"- **Duration:** {manifest.get('duration_seconds', 0):.1f}s\n"
                    f"- **Mode:** `{manifest.get('scrape_mode', '—')}`\n"
                    f"- **Max Pages:** {manifest.get('max_pages', '—')}\n"
                    f"- **Detail Enrichment:** {'✅ On' if manifest.get('enrich_details') else '❌ Off'}"
                )

        with m_c2:
            with st.container(border=True):
                st.markdown("**Listing Counts**")
                st.markdown(
                    f"- **Batch Total:** {manifest.get('batch_total', 0):,}\n"
                    f"- **New Listings:** +{manifest.get('new_ids_count', 0):,}\n"
                    f"- **Recurring Listings:** {manifest.get('recurring_ids_count', 0):,}\n"
                    f"- **Cumulative Unique:** {manifest.get('cumulative_unique_ids', 0):,}"
                )

        with m_c3:
            with st.container(border=True):
                st.markdown("**Field Coverage (Last Run)**")
                coverage_fields = [
                    ("Price", "price_coverage_pct"),
                    ("Year", "year_coverage_pct"),
                    ("Brand", "brand_coverage_pct"),
                    ("Model", "model_coverage_pct"),
                    ("Province", "province_coverage_pct"),
                    ("Mileage", "mileage_coverage_pct"),
                    ("Fuel Type", "fuel_coverage_pct"),
                    ("Transmission", "transmission_coverage_pct"),
                ]
                for label, key in coverage_fields:
                    pct = qm.get(key, None)
                    if pct is not None:
                        dot = "🟢" if pct >= 90 else "🟡" if pct >= 60 else "🔴"
                        st.markdown(f"- {dot} **{label}:** {pct:.1f}%")
    else:
        st.info("No ingestion manifest found at `data/bronze/ingestion_manifest.json`.")

    st.divider()

    # ── Batch Ledger ──────────────────────────────────────────────────────────
    st.markdown(
        config.section_header("BRONZE BATCH LEDGER", "All raw Parquet files with size and record counts."),
        unsafe_allow_html=True,
    )

    if raw_summary.get("available") and not raw_summary["batches"].empty:
        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Parquet Files", f"{raw_summary['total_files']}")
        b2.metric("Total Records", f"{raw_summary['total_records']:,}")
        b3.metric("Distinct Listings", f"{raw_summary['total_distinct']:,}")
        b4.metric("Storage", f"{raw_summary['total_size_mb']:.2f} MB")

        st.dataframe(
            raw_summary["batches"],
            hide_index=True,
            use_container_width=True,
            column_config={
                "file_name":         st.column_config.TextColumn("File", width="medium"),
                "scrape_date":       st.column_config.TextColumn("Date", width="small"),
                "records_ingested":  st.column_config.NumberColumn("Records", format="%d"),
                "distinct_listings": st.column_config.NumberColumn("Unique Listings", format="%d"),
                "intra_day_dups":    st.column_config.NumberColumn("Intra-Day Dups", format="%d"),
                "size_kb":           st.column_config.NumberColumn("Size (KB)", format="%.1f"),
                "size_mb":           st.column_config.NumberColumn("Size (MB)", format="%.2f"),
            },
        )
    else:
        st.info("No Bronze parquet files found.")
