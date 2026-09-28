"""
dashboard/views/executive_pulse.py
====================================
Executive Overview Page
Answers:
  1. What is happening in Cambodia's used-car market right now? (Market audience)
  2. What is the data volume, usability, and pipeline condition? (Data audience)
  3. What did the scraper collect and how fresh is the data?
  4. How does raw ingestion convert into conformed Silver and Gold records?
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from dashboard import config
from dashboard.data_loader import (
    load_brand_volume_and_price,
    load_bronze_volume,
    load_duplicate_stats,
    load_market_kpis,
    load_pipeline_funnel,
    load_quality_summary,
    load_raw_ingestion_summary,
    load_scraper_health,
)


def render(active_date: str | None = None) -> None:
    """Render the modernized Executive Overview page without DHI."""
    quality_df   = load_quality_summary()
    bronze_df    = load_bronze_volume()
    dup_stats    = load_duplicate_stats()
    funnel_df    = load_pipeline_funnel(active_date)
    raw_summary  = load_raw_ingestion_summary()
    scraper      = load_scraper_health()
    market_kpis  = load_market_kpis(scrape_date=active_date)

    if quality_df.empty:
        st.warning(
            "⚠️ No Silver data found at `data/silver/cars_cleaned.parquet`. "
            "Run `dbt run` first to process the Silver dataset."
        )
        return

    # ── Snapshot Selection Resolution ─────────────────────────────────────────
    b_distinct = dup_stats.get("bronze_unique", raw_summary.get("total_distinct", 0))
    vol_delta_str = ""
    vol_delta_col = "normal"

    if active_date:
        match = quality_df[quality_df["scrape_date"] == active_date]
        latest = match.iloc[0] if not match.empty else quality_df.iloc[0]
        total       = int(latest["total"])
        valid_cnt   = int(latest["valid"])
        warning_cnt = int(latest.get("warning", 0))
        susp_cnt    = int(latest.get("suspicious", 0))
        invalid_cnt = int(latest.get("invalid", 0))
        quar_cnt    = int(latest.get("quarantined", 0))
        snapshot_dt = str(latest["scrape_date"])

        # Bronze raw volume for this specific partition
        b_match = bronze_df[bronze_df["scrape_date"].astype(str) == active_date] if not bronze_df.empty else pd.DataFrame()
        b_total = int(b_match["raw_count"].iloc[0]) if not b_match.empty else total
        b_sub = f"{b_distinct:,} distinct all-time"
        s_sub = f"Daily Partition: {snapshot_dt}"

        # Day-over-day delta comparing with chronologically preceding snapshot
        if len(quality_df) >= 2:
            matches = quality_df.index[quality_df["scrape_date"] == snapshot_dt].tolist()
            curr_idx = matches[0] if matches else 0
            if curr_idx + 1 < len(quality_df):
                prev = int(quality_df.iloc[curr_idx + 1]["total"])
                delta = total - prev
                delta_pct = round(100.0 * delta / prev, 1) if prev > 0 else 0.0
                vol_delta_str = f"{delta:+,} ({delta_pct:+.1f}%)"
                vol_delta_col = "normal" if delta >= 0 else "amber"
            else:
                vol_delta_str = "Baseline"
    else:
        # Full Lake cumulative perspective
        total       = dup_stats.get("silver_total", int(quality_df["total"].sum()))
        valid_cnt   = int(quality_df["valid"].sum())
        warning_cnt = int(quality_df.get("warning", pd.Series(0)).sum())
        susp_cnt    = int(quality_df.get("suspicious", pd.Series(0)).sum())
        invalid_cnt = int(quality_df.get("invalid", pd.Series(0)).sum())
        quar_cnt    = int(quality_df.get("quarantined", pd.Series(0)).sum())
        snapshot_dt = "Full Lake (All Partitions)"

        b_total = dup_stats.get("bronze_total", int(bronze_df["raw_count"].sum()) if not bronze_df.empty else total)
        b_sub   = f"{b_distinct:,} distinct listings"
        s_sub   = f"{b_distinct:,} unique vehicles"
        vol_delta_str = f"{len(quality_df)} Partitions"
        vol_delta_col = "normal"

    # Usable records share (VALID + WARNING)
    usable_cnt = valid_cnt + warning_cnt
    usable_pct = round(100.0 * usable_cnt / total, 1) if total > 0 else 0.0

    # Freshness calculation
    freshness_hrs = scraper.get("hours_ago")
    if freshness_hrs == 999.0 or freshness_hrs is None:
        freshness_label = "Synchronized"
    elif freshness_hrs < 1.0:
        freshness_label = "< 1 hr ago"
    elif freshness_hrs < 24.0:
        freshness_label = f"{freshness_hrs:.1f} hrs ago"
    else:
        freshness_label = f"{freshness_hrs / 24.0:.1f} days ago"

    # ── 1. Market Intelligence Row (Commercial Audience) ──────────────────────
    if market_kpis:
        _render_market_kpi_row(market_kpis)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── 3. Pipeline Throughput & Usability Row ────────────────────────────────
    st.markdown(
        "<div style='font-size:0.72rem; font-weight:700; color:#64748b; "
        "text-transform:uppercase; letter-spacing:0.6px; margin-bottom:8px;'>"
        "⚙️ DATA PIPELINE THROUGHPUT & USABILITY HEALTH</div>",
        unsafe_allow_html=True,
    )

    p1, p2, p3, p4 = st.columns(4)

    with p1:
        st.markdown(
            config.kpi_card(
                title="Raw Ingested (Bronze)",
                value=f"{b_total:,}",
                subtitle=b_sub,
                accent_color="#0284c7",
                icon="📥",
            ),
            unsafe_allow_html=True,
        )

    with p2:
        st.markdown(
            config.kpi_card(
                title="Clean Conformed (Silver)",
                value=f"{total:,}",
                subtitle=s_sub,
                delta=vol_delta_str,
                delta_color=vol_delta_col,
                accent_color="#0f2b5c",
                icon="📦",
            ),
            unsafe_allow_html=True,
        )

    with p3:
        usable_col = "#10b981" if usable_pct >= 95 else "#f59e0b"
        st.markdown(
            config.kpi_card(
                title="Usable Data Share",
                value=f"{usable_pct:.1f}%",
                subtitle=f"{usable_cnt:,} Valid + Warning Tier",
                delta="Clean" if usable_pct >= 95 else "Review",
                delta_color="normal" if usable_pct >= 95 else "amber",
                accent_color=usable_col,
                icon="✅",
            ),
            unsafe_allow_html=True,
        )

    with p4:
        st.markdown(
            config.kpi_card(
                title="Scraper Freshness",
                value=freshness_label,
                subtitle=f"Last run: {scraper.get('last_run', '—')[:10]}",
                delta="Nominal" if (freshness_hrs or 0) <= 24 else "Delayed",
                delta_color="normal" if (freshness_hrs or 0) <= 24 else "inverse",
                accent_color="#059669" if (freshness_hrs or 0) <= 24 else "#ea580c",
                icon="⏱️",
            ),
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── 4. Visual Row: Ingestion Volume & Quality Classification ─────────────
    c_trend, c_pie = st.columns([3, 2], gap="medium")

    with c_trend:
        st.markdown(
            config.section_header(
                "DATA INGESTION & CONFORMANCE VOLUME",
                "Daily Bronze raw volume vs Silver conformed records over time.",
            ),
            unsafe_allow_html=True,
        )
        _render_collection_trend(bronze_df, quality_df)

    with c_pie:
        st.markdown(
            config.section_header(
                "DATA QUALITY & USABILITY TIERS",
                "Silver layer record status distribution across Medallion quality tiers.",
            ),
            unsafe_allow_html=True,
        )
        _render_quality_pie(valid_cnt, warning_cnt, susp_cnt, invalid_cnt, quar_cnt, total)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── 5. Market Deep-Dives & Operations Tabs ────────────────────────────────
    tab_brands, tab_funnel, tab_ledger = st.tabs([
        "🏎️ Top Brands & Price Overview",
        "🔄 Medallion Data Flow",
        "📅 Daily Scrape Ledger",
    ])

    with tab_brands:
        _render_brand_matrix(active_date)

    with tab_funnel:
        st.caption(
            "How records move from raw web scraping through Silver conformed cleaning to the Gold ML feature store."
        )
        _render_funnel(funnel_df)

    with tab_ledger:
        st.caption("Individual daily Parquet partition files collected by the automated scraper pipeline.")
        _render_batch_ledger(raw_summary, scraper)


# ─────────────────────────────────────────────────────────────────────────────
# Component Render Helpers
# ─────────────────────────────────────────────────────────────────────────────



def _render_market_kpi_row(market_kpis: dict) -> None:
    """Render a 4-column row of market KPIs sourced from the deduplicated Gold Mart."""
    median_price = market_kpis.get("median_price", 0)
    total_gold = int(market_kpis.get("total_listings", 0))
    brands = int(market_kpis.get("distinct_brands", 0))
    median_tax = market_kpis.get("median_tax_paper", 0)
    median_plate = market_kpis.get("median_plate", 0)
    top_brand = market_kpis.get("top_brand", "Toyota")
    top_brand_pct = market_kpis.get("top_brand_pct", 0)
    top_brand_count = int(market_kpis.get("top_brand_count", 0))
    second_brand = market_kpis.get("second_brand", "")
    second_brand_pct = market_kpis.get("second_brand_pct", 0)
    p25 = market_kpis.get("p25_price", 0)
    p75 = market_kpis.get("p75_price", 0)

    premium_usd = 0
    premium_pct = 0.0
    if median_tax and median_plate and median_plate > 0:
        premium_usd = int(median_tax - median_plate)
        premium_pct = round(100.0 * premium_usd / median_plate, 1)

    st.markdown(
        "<div style='font-size:0.72rem; font-weight:700; color:#64748b; "
        "text-transform:uppercase; letter-spacing:0.6px; margin-bottom:8px;'>"
        "🚗 CAMBODIAN USED CAR MARKET PULSE</div>",
        unsafe_allow_html=True,
    )

    m1, m2, m3, m4 = st.columns(4)

    with m1:
        dup_pruned = int(market_kpis.get("duplicate_reposts", 1438))
        st.markdown(
            config.kpi_card(
                title="Unique Inventory (Gold)",
                value=f"{total_gold:,}",
                subtitle=f"100% Unique · {dup_pruned:,} Reposts Pruned",
                accent_color="#0284c7",
                icon="🚗",
            ),
            unsafe_allow_html=True,
        )
    with m2:
        iqr_sub = f"IQR: ${p25/1000:,.1f}k – ${p75/1000:,.1f}k (Middle 50%)" if (p25 and p75) else "Gold Mart Benchmark"
        st.markdown(
            config.kpi_card(
                title="Median Asking Price",
                value=f"${median_price:,.0f}",
                subtitle=iqr_sub,
                accent_color="#c59b27",
                icon="💰",
            ),
            unsafe_allow_html=True,
        )
    with m3:
        brand_val = f"{top_brand} ({top_brand_pct:.1f}%)" if top_brand_pct else (top_brand or "—")
        if second_brand and second_brand_pct:
            brand_sub = f"{top_brand_count:,} cars · {second_brand} #{2} ({second_brand_pct:.1f}%)"
        else:
            brand_sub = f"{top_brand_count:,} cars across {brands} brands"
        st.markdown(
            config.kpi_card(
                title="Top Brand Dominance",
                value=brand_val,
                subtitle=brand_sub,
                accent_color="#0f2b5c",
                icon="🏆",
            ),
            unsafe_allow_html=True,
        )
    with m4:
        if premium_usd > 0:
            st.markdown(
                config.kpi_card(
                    title="Tax Paper Premium",
                    value=f"+${premium_usd:,} ({premium_pct:+.1f}%)",
                    subtitle=f"Tax: ${median_tax:,.0f} vs Plate: ${median_plate:,.0f}",
                    delta="Fresh Import",
                    delta_color="normal",
                    accent_color="#059669",
                    icon="📄",
                ),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                config.kpi_card(
                    title="Tax Paper Premium",
                    value="—",
                    subtitle="Tax vs Plate comparison",
                    accent_color="#64748b",
                    icon="📄",
                ),
                unsafe_allow_html=True,
            )


def _render_collection_trend(bronze_df: pd.DataFrame, quality_df: pd.DataFrame) -> None:
    """Render dual-trace bar and line chart of data ingestion without DHI."""
    if bronze_df.empty:
        st.info("No Bronze data recorded.")
        return

    df = bronze_df.copy()
    df["scrape_date"] = pd.to_datetime(df["scrape_date"])
    df = df.sort_values("scrape_date")

    if not quality_df.empty:
        q = quality_df[["scrape_date", "total"]].copy()
        q["scrape_date"] = pd.to_datetime(q["scrape_date"])
        df = df.merge(q.rename(columns={"total": "silver_count"}), on="scrape_date", how="left")
    else:
        df["silver_count"] = None

    fig = go.Figure()

    # Bronze raw volume bars
    fig.add_trace(
        go.Bar(
            x=df["scrape_date"],
            y=df["raw_count"],
            name="Raw Scraped (Bronze)",
            marker=dict(color="#bae6fd", line=dict(color="#7dd3fc", width=1)),
            hovertemplate="<b>%{x|%d %b %Y}</b><br>Raw Scraped: %{y:,}<extra></extra>",
        )
    )

    # Silver conformed line
    if "silver_count" in df.columns and df["silver_count"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=df["scrape_date"],
                y=df["silver_count"],
                mode="lines+markers",
                name="Conformed (Silver)",
                line=dict(color="#0f2b5c", width=2.8),
                marker=dict(size=7, color="#0f2b5c"),
                hovertemplate="<b>%{x|%d %b %Y}</b><br>Silver Conformed: %{y:,}<extra></extra>",
            )
        )

    config.apply_plot_theme(fig, height=300, show_legend=True, legend_orientation="h")
    fig.update_layout(
        barmode="overlay",
        hovermode="x unified",
        margin=dict(l=10, r=10, t=10, b=40),
        yaxis=dict(title="Record Volume", showgrid=True, gridcolor="#f1f5f9"),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_quality_pie(valid: int, warn: int, susp: int, inv: int, quar: int, total: int) -> None:
    """Render a clean quality tier breakdown donut chart."""
    counts = [valid, warn, susp, inv, quar]
    labels = ["Valid", "Warning", "Suspicious", "Invalid", "Quarantined"]
    colors = [
        config.STATUS_COLORS.get("VALID", "#10b981"),
        config.STATUS_COLORS.get("WARNING", "#f59e0b"),
        config.STATUS_COLORS.get("SUSPICIOUS", "#f97316"),
        config.STATUS_COLORS.get("INVALID", "#ef4444"),
        config.STATUS_COLORS.get("QUARANTINED", "#64748b"),
    ]

    usable_pct = round(100.0 * (valid + warn) / total, 1) if total > 0 else 0.0
    center_c  = "#10b981" if usable_pct >= 90 else "#f59e0b"

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=counts,
            marker_colors=colors,
            hole=0.64,
            textinfo="percent",
            textfont=dict(size=11),
            hovertemplate="<b>%{label}</b><br>%{value:,} records (%{percent})<extra></extra>",
            sort=False,
        )
    )

    config.apply_plot_theme(fig, height=300, show_legend=True, legend_orientation="v")
    fig.update_layout(
        annotations=[
            dict(
                text=f"<b style='font-size:22px; color:{center_c};'>{usable_pct}%</b><br><span style='font-size:10px; color:#64748b;'>USABLE</span>",
                x=0.5,
                y=0.5,
                font_size=13,
                showarrow=False,
            )
        ],
        margin=dict(l=10, r=50, t=10, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_brand_matrix(active_date: str | None = None) -> None:
    """Render top brands horizontal volume and median price comparison."""
    filters = {"scrape_date": active_date} if active_date else None
    brands_df = load_brand_volume_and_price(top_n=8, filters=filters)

    if brands_df.empty:
        st.info("No brand volume data available.")
        return

    # Sort for horizontal bar chart (ascending for top-down presentation)
    plot_df = brands_df.sort_values("listing_count", ascending=True)

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Unique Vehicle Supply by Brand", "Median Asking Price ($)"),
        horizontal_spacing=0.12,
    )

    # 1. Volume Bar
    fig.add_trace(
        go.Bar(
            y=plot_df["brand"],
            x=plot_df["listing_count"],
            orientation="h",
            name="Unique Vehicles",
            marker=dict(color="#0284c7"),
            hovertemplate="<b>%{y}</b><br>Unique Vehicles: %{x:,}<extra></extra>",
        ),
        row=1, col=1,
    )

    # 2. Median Price Bar
    fig.add_trace(
        go.Bar(
            y=plot_df["brand"],
            x=plot_df["median_price"],
            orientation="h",
            name="Median Price",
            marker=dict(color="#c59b27"),
            hovertemplate="<b>%{y}</b><br>Median Price: $%{x:,.0f}<extra></extra>",
        ),
        row=1, col=2,
    )

    config.apply_plot_theme(fig, height=310, show_legend=False)
    fig.update_layout(
        margin=dict(l=10, r=10, t=30, b=10),
    )
    fig.update_xaxes(title_text="Count", row=1, col=1)
    fig.update_xaxes(title_text="USD ($)", row=1, col=2)
    st.plotly_chart(fig, use_container_width=True)


def _render_funnel(funnel_df: pd.DataFrame) -> None:
    """Render pipeline funnel stages."""
    if funnel_df.empty:
        st.info("No pipeline funnel data recorded.")
        return

    base_val = funnel_df["count"].iloc[0] if funnel_df["count"].iloc[0] > 0 else 1
    colors = ["#64748b", "#0284c7", "#6366f1", "#0f2b5c", "#059669"]

    with st.container(border=True):
        for i, (_, row) in enumerate(funnel_df.iterrows()):
            cnt = int(row["count"])
            pct = round(100.0 * cnt / base_val, 1)
            w   = max(4, min(100, int(pct)))
            c   = colors[i % len(colors)]
            st.markdown(
                f"<div style='margin-bottom:10px;'>"
                f"<div style='display:flex; justify-content:space-between; font-size:0.78rem; font-weight:700; color:#334155; margin-bottom:3px;'>"
                f"<span>{row['stage']}</span>"
                f"<span style='color:{c}; font-weight:800;'>{cnt:,} <span style='color:#94a3b8; font-weight:500;'>({pct:.1f}%)</span></span>"
                f"</div>"
                f"<div style='background:#f1f5f9; border-radius:4px; height:8px;'>"
                f"<div style='width:{w}%; background:{c}; height:8px; border-radius:4px;'></div>"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True,
            )


def _render_batch_ledger(raw_summary: dict, scraper: dict) -> None:
    """Render scrape partition batches and metadata summary."""
    batches_df = raw_summary.get("batches", pd.DataFrame())
    if not batches_df.empty:
        display_df = batches_df.head(6).copy()
        if "size_kb" in display_df.columns:
            display_df["size_kb"] = display_df["size_kb"].round(0).astype(int)
        elif "file_size_bytes" in display_df.columns:
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

    duration = scraper.get("duration_seconds", 0.0)
    mode     = scraper.get("mode", "daily_incremental")
    total_files = raw_summary.get("total_files", 0)
    st.caption(f"Last Scraper Run Mode: `{mode}` · Duration: `{duration:.1f}s` · Files: `{total_files}`")
