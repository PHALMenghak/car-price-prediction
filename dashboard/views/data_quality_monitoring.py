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
        std_cnt = impact.get("models_from_seed_alias", 0) if impact else 0
        std_pct = round(100.0 * std_cnt / total, 1) if total > 0 else 0.0
        st.markdown(
            config.kpi_card(
                title="Models Standardized",
                value=f"{std_cnt:,}",
                subtitle=f"{std_pct}% mapped to canonical forms",
                delta="dbt Uplift",
                delta_color="normal",
                accent_color="#0284c7",
                icon="🔤",
            ),
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── Transformation Rules Documentation ────────────────────────────────────
    with st.expander("📋 Documented Transformation Rules Catalog (dbt int_cars_cleaned.sql)", expanded=False):
        st.markdown("""
        Every data modification in the pipeline is governed by explicit SQL transformation rules without silent data loss:
        - `[RULE-NLP-01] Title Model Mining`: Regex pattern extraction of car model, trim, and sub-tier when structured form input was left empty by the seller.
        - `[RULE-YR-02] Chronological Year Inversion Healing`: Detects impossible future year typos (e.g. `2026` for a 2006 car) and safely inverts them.
        - `[RULE-DP-03] Down-Payment Installment Detection`: Identifies deposit pricing (e.g. `$3,500` deposit vs. full `$35,000` car value) via regex keywords (`បង់រំលស់`, `down payment`) or abnormal price/year ratios, classifying them under `SUSPICIOUS`.
        - `[RULE-SP-04] Non-Vehicle Spam Quarantine`: Excludes spare parts, tires, and motorbikes, placing them strictly into `QUARANTINED`.
        - `[RULE-IQR-05] Dynamic Statistical Outlier Fences`: Computes brand-and-vintage specific $1.5\\times\\text{IQR}$ fences, flagging extreme listings for review rather than dropping them.
        """)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

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

    color_map = config.STATUS_COLORS

    # Ensure clean numeric data
    plot_df = anomaly_sample.copy()
    plot_df["vehicle_year"] = pd.to_numeric(plot_df["vehicle_year"], errors="coerce")
    plot_df["price"] = pd.to_numeric(plot_df["price"], errors="coerce")
    plot_df = plot_df.dropna(subset=["vehicle_year", "price"])
    if use_log:
        plot_df = plot_df[plot_df["price"] > 0]

    hover_cols = [c for c in ["vehicle_brand", "vehicle_model", "province", "anomaly_group"] if c in plot_df.columns]

    try:
        fig = px.scatter(
            plot_df,
            x="vehicle_year",
            y="price",
            color="data_quality_status",
            color_discrete_map=color_map,
            hover_data=hover_cols,
            labels={"vehicle_year": "Model Year", "price": "Price (USD)", "data_quality_status": "Quality Status"},
            log_y=use_log,
            opacity=0.65,
        )
        config.apply_plot_theme(fig, height=330, show_legend=True, legend_orientation="h")
        fig.update_traces(marker=dict(size=6))
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=40))
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Could not render scatter plot: {e}")


def _render_audit_drilldown(active_date: str | None) -> None:
    """Render full side-by-side Lineage & Anomaly Audit Registry."""
    # 1. Preset filter quick buttons
    preset_choice = st.radio(
        "Audit Presets:",
        options=[
            "⚠️ Flagged (Quarantined + Invalid + Suspicious)",
            "🔴 Quarantined Spam Traps",
            "🟡 Suspicious & Price Outliers",
            "🟢 Clean & Conformed Only",
            "🌐 All Records",
        ],
        horizontal=True,
        index=0,
        help="Quickly load specific data quality scenarios.",
    )

    preset_map = {
        "⚠️ Flagged (Quarantined + Invalid + Suspicious)": ["QUARANTINED", "INVALID", "SUSPICIOUS"],
        "🔴 Quarantined Spam Traps": ["QUARANTINED"],
        "🟡 Suspicious & Price Outliers": ["SUSPICIOUS"],
        "🟢 Clean & Conformed Only": ["VALID"],
        "🌐 All Records": ["ALL"],
    }
    selected_statuses = preset_map.get(preset_choice, ["QUARANTINED", "INVALID", "SUSPICIOUS"])

    reason_options = {
        "All Reasons": "",
        "Price Outliers (All)": "OUTLIER",
        "Statistical Outlier (Low / Scam)": "STATISTICAL_OUTLIER_LOW",
        "Statistical Outlier (High)": "STATISTICAL_OUTLIER_HIGH",
        "Heuristic Outlier": "HEURISTIC_PRICE_OUTLIER",
        "Down Payment Bait": "DOWN_PAYMENT",
        "Spam Listings": "SPAM",
        "Unknown Model": "UNKNOWN_MODEL",
        "Unknown Brand": "UNKNOWN_BRAND",
        "Missing Mileage": "MISSING_MILEAGE",
        "Missing Engine": "MISSING_ENGINE",
    }

    f_col1, f_col2, f_col3 = st.columns([2, 2, 1])
    with f_col1:
        sel_reason_label = st.selectbox(
            "Filter Anomaly Reason",
            options=list(reason_options.keys()),
            index=0,
            help="Filter records by specific failure reason code.",
        )
        selected_reason = reason_options[sel_reason_label]

    with f_col2:
        search_kw = st.text_input(
            "Search Records",
            value="",
            placeholder="Search ID, Brand, Model, Title...",
            help="Filter sample by keyword in title, brand, model, or listing ID.",
        )

    with f_col3:
        max_records = st.selectbox(
            "Limit",
            options=[50, 100, 200, 500],
            index=1,
            help="Maximum records to load from data lake.",
        )

    # Load data from loader
    sample_df = load_audit_sample(
        statuses=selected_statuses,
        reason_filter=selected_reason,
        limit=max_records,
        scrape_date=active_date,
    )

    if sample_df.empty:
        st.info("No records matching the selected quality status and reason filters.")
        return

    # Apply text search filter if provided
    if search_kw.strip():
        kw = search_kw.strip().lower()
        searchable_cols = ["listing_id", "raw_title", "title_clean", "clean_brand", "clean_model", "clean_province", "reasons"]
        conditions = [
            sample_df[col].fillna("").astype(str).str.lower().str.contains(kw)
            for col in searchable_cols
            if col in sample_df.columns
        ]
        if conditions:
            mask = conditions[0]
            for cond in conditions[1:]:
                mask = mask | cond
            sample_df = sample_df[mask]

    if sample_df.empty:
        st.info(f"No records matching keyword `{search_kw}` found in current sample.")
        return

    # 2. Summary stats pills
    total_in_view = len(sample_df)
    quar_in_view = int((sample_df["status"] == "QUARANTINED").sum())
    susp_in_view = int((sample_df["status"] == "SUSPICIOUS").sum())
    healed_in_view = int((sample_df["is_year_healed"] == 1).sum()) if "is_year_healed" in sample_df.columns else 0
    nlp_in_view = int((sample_df["model_extraction_method"] == "title_extracted").sum()) if "model_extraction_method" in sample_df.columns else 0

    st.markdown(
        f"<div style='display:flex; gap:12px; margin:8px 0 14px 0; flex-wrap:wrap; font-size:0.78rem;'>"
        f"<span style='background:#f1f5f9; padding:3px 10px; border-radius:12px; border:1px solid #e2e8f0; font-weight:600; color:#334155;'>📋 Showing: <b>{total_in_view}</b> records</span>"
        f"<span style='background:#fee2e2; padding:3px 10px; border-radius:12px; border:1px solid #fecaca; font-weight:600; color:#991b1b;'>🔴 Quarantined: <b>{quar_in_view}</b></span>"
        f"<span style='background:#fef3c7; padding:3px 10px; border-radius:12px; border:1px solid #fde68a; font-weight:600; color:#92400e;'>🟡 Suspicious: <b>{susp_in_view}</b></span>"
        f"<span style='background:#eff6ff; padding:3px 10px; border-radius:12px; border:1px solid #bfdbfe; font-weight:600; color:#1e40af;'>🔄 Years Healed: <b>{healed_in_view}</b></span>"
        f"<span style='background:#ecfdf5; padding:3px 10px; border-radius:12px; border:1px solid #a7f3d0; font-weight:600; color:#065f46;'>🔤 Title NLP Models: <b>{nlp_in_view}</b></span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # 3. Formatted display DataFrame
    display_df = sample_df.copy()
    if "is_year_healed" in display_df.columns:
        display_df["year_healing"] = display_df["is_year_healed"].apply(
            lambda x: "🔄 Healed" if (pd.notna(x) and x == 1) else "✓ Original"
        )
    else:
        display_df["year_healing"] = "—"

    # Column ordering: Side-by-side raw vs clean
    table_cols = [
        "listing_id", "status", "reasons",
        "raw_title", "title_clean",
        "raw_price", "clean_price",
        "price_lower_fence", "price_upper_fence", "outlier_method",
        "raw_brand", "clean_brand",
        "raw_model", "clean_model", "model_extraction_method",
        "raw_year", "clean_year", "year_healing",
        "clean_province", "listing_url"
    ]
    present_cols = [c for c in table_cols if c in display_df.columns]

    st.dataframe(
        display_df[present_cols],
        hide_index=True,
        use_container_width=True,
        height=380,
        column_config={
            "listing_id":              st.column_config.TextColumn("ID", width="small"),
            "status":                  st.column_config.TextColumn("Quality Status", width="small"),
            "reasons":                 st.column_config.TextColumn("Anomaly Reasons", width="medium"),
            "raw_title":               st.column_config.TextColumn("Raw Scraper Title (Khmer24)", width="large"),
            "title_clean":             st.column_config.TextColumn("Cleaned Title (Silver)", width="large"),
            "raw_price":               st.column_config.TextColumn("Raw Price", width="small"),
            "clean_price":             st.column_config.NumberColumn("Clean Price ($)", format="$%,d", width="small"),
            "price_lower_fence":       st.column_config.NumberColumn("Lower Fence ($)", format="$%,d", width="small"),
            "price_upper_fence":       st.column_config.NumberColumn("Upper Fence ($)", format="$%,d", width="small"),
            "outlier_method":          st.column_config.TextColumn("Outlier Engine", width="small"),
            "raw_brand":               st.column_config.TextColumn("Raw Brand", width="small"),
            "clean_brand":             st.column_config.TextColumn("Clean Brand", width="small"),
            "raw_model":               st.column_config.TextColumn("Raw Model", width="small"),
            "clean_model":             st.column_config.TextColumn("Clean Model", width="small"),
            "model_extraction_method": st.column_config.TextColumn("Extraction Method", width="small"),
            "raw_year":                st.column_config.TextColumn("Raw Year", width="small"),
            "clean_year":              st.column_config.NumberColumn("Clean Year", format="%d", width="small"),
            "year_healing":            st.column_config.TextColumn("Year Healing", width="small"),
            "clean_province":          st.column_config.TextColumn("Province", width="small"),
            "listing_url":             st.column_config.LinkColumn("Khmer24 Link", display_text="Open ↗", width="small"),
        },
    )

    # 4. Deep-dive single record inspector
    with st.expander("🔬 Inspect Single Record Lineage (Side-by-Side Diff)", expanded=False):
        sample_df_unique = sample_df.drop_duplicates(subset=["listing_id"]).copy()
        if not sample_df_unique.empty:
            id_options = sample_df_unique["listing_id"].astype(str).tolist()

            def _safe_val(v: object, default: str = "") -> str:
                if v is None or pd.isna(v):
                    return default
                s = str(v).strip()
                return s if s else default

            # Precompute formatted labels to avoid O(N^2) DataFrame filtering during selectbox rendering
            label_map: dict[str, str] = {}
            for _, r in sample_df_unique.iterrows():
                lid = str(r["listing_id"])
                brand = _safe_val(r.get("clean_brand")) or _safe_val(r.get("raw_brand")) or ""
                model = _safe_val(r.get("clean_model")) or _safe_val(r.get("raw_model")) or ""

                clean_yr = r.get("clean_year")
                raw_yr = r.get("raw_year")
                if pd.notna(clean_yr):
                    try:
                        yr = str(int(clean_yr))
                    except (ValueError, TypeError):
                        yr = str(clean_yr).strip()
                elif pd.notna(raw_yr):
                    yr = str(raw_yr).strip()
                else:
                    yr = ""

                status = _safe_val(r.get("status"))
                label_map[lid] = f"ID {lid} — {brand} {model} {yr} [{status}]".strip()

            selected_id = st.selectbox(
                "Select Listing ID to Inspect",
                options=id_options,
                index=0,
                format_func=lambda lid: label_map.get(lid, str(lid)),
                key="audit_single_record_select",
            )
            rec = sample_df_unique[sample_df_unique["listing_id"].astype(str) == selected_id].iloc[0]

            d_col1, d_col2 = st.columns(2)
            with d_col1:
                st.markdown(
                    "<div style='background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:12px;'>"
                    "<div style='font-size:0.75rem; font-weight:800; color:#64748b; text-transform:uppercase; margin-bottom:8px;'>"
                    "📥 Bronze Layer (Raw Scraper Input)"
                    "</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(f"**Raw Title:** {_safe_val(rec.get('raw_title'), '—')}")
                st.markdown(f"**Raw Price:** `{_safe_val(rec.get('raw_price'), '—')}`")
                st.markdown(f"**Raw Brand Spec:** `{_safe_val(rec.get('raw_brand'), '—')}`")
                st.markdown(f"**Raw Model Spec:** `{_safe_val(rec.get('raw_model'), '—')}`")
                st.markdown(f"**Raw Year Spec:** `{_safe_val(rec.get('raw_year'), '—')}`")
                st.markdown(f"**Scrape Partition:** `{_safe_val(rec.get('scrape_date'), '—')}`")
                st.markdown("</div>", unsafe_allow_html=True)

            with d_col2:
                st.markdown(
                    "<div style='background:#f0fdf4; border:1px solid #bbf7d0; border-radius:6px; padding:12px;'>"
                    "<div style='font-size:0.75rem; font-weight:800; color:#166534; text-transform:uppercase; margin-bottom:8px;'>"
                    "✨ Silver Layer (Cleaned & Conformed)"
                    "</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(f"**Cleaned Title:** {_safe_val(rec.get('title_clean'), '—')}")
                clean_p_val = rec.get("clean_price")
                clean_p = f"${int(clean_p_val):,}" if pd.notnull(clean_p_val) else "—"
                st.markdown(f"**Conformed Price:** `{clean_p}`")
                st.markdown(f"**Conformed Brand:** `{_safe_val(rec.get('clean_brand'), '—')}`")
                method = _safe_val(rec.get("model_extraction_method"), "raw_spec")
                st.markdown(f"**Conformed Model:** `{_safe_val(rec.get('clean_model'), '—')}` *(method: {method})*")
                clean_y_val = rec.get("clean_year")
                clean_y = f"{int(clean_y_val)}" if pd.notnull(clean_y_val) else "—"
                is_healed = pd.notna(rec.get("is_year_healed")) and int(rec.get("is_year_healed")) == 1
                healing_note = " *(🔄 Chronologically healed from inverted title year)*" if is_healed else ""
                st.markdown(f"**Conformed Year:** `{clean_y}`{healing_note}")
                st.markdown(f"**Province:** `{_safe_val(rec.get('clean_province'), '—')}`")
                out_method = _safe_val(rec.get('outlier_method'))
                lf = rec.get('price_lower_fence')
                uf = rec.get('price_upper_fence')
                if out_method and pd.notnull(lf) and pd.notnull(uf):
                    st.markdown(f"**Market Fences ({out_method}):** `${int(lf):,}` – `${int(uf):,}`")
                st.markdown("</div>", unsafe_allow_html=True)

            # Diagnostics badge row
            st_status = _safe_val(rec.get("status"), "UNKNOWN")
            stat_color = config.STATUS_COLORS.get(st_status, "#64748b")
            reasons_str = _safe_val(rec.get("reasons"), "None (Passed)")
            listing_url_str = _safe_val(rec.get("listing_url"), "#")
            st.markdown(
                f"<div style='margin-top:10px; padding:8px 12px; background:#f8fafc; border-left:4px solid {stat_color}; border-radius:4px; font-size:0.80rem;'>"
                f"<b>Quality Status:</b> <span style='color:{stat_color}; font-weight:700;'>{st_status}</span> &nbsp;·&nbsp; "
                f"<b>Failure Reasons:</b> <code>{reasons_str}</code> &nbsp;·&nbsp; "
                f"<a href='{listing_url_str}' target='_blank' style='color:#3b82f6; font-weight:600;'>View on Khmer24 ↗</a>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # 5. CSV export
    csv_data = sample_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Audit Sample CSV",
        data=csv_data,
        file_name=f"audit_lineage_registry_{active_date or 'all'}.csv",
        mime="text/csv",
        use_container_width=True,
    )
