"""
dashboard/views/cleaning_transformation.py
============================================
Page 3 — Cleaning & Transformation
Answers: What happened to the raw data?
Shows transformation steps, before/after comparisons, and cleaning impact.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard import config
from dashboard.data_loader import (
    load_cleaning_impact_stats,
    load_cleaning_rules_summary,
    load_pipeline_funnel,
    load_quality_summary,
    load_raw_vs_conformed_comparison,
)


def render(active_date: str | None = None) -> None:
    """Render the Cleaning & Transformation page."""
    impact     = load_cleaning_impact_stats(active_date)
    funnel_df  = load_pipeline_funnel(active_date)
    rules_df   = load_cleaning_rules_summary()
    comp_df    = load_raw_vs_conformed_comparison()
    quality_df = load_quality_summary()

    st.markdown(
        config.section_header(
            "CLEANING & TRANSFORMATION",
            "What happened to the raw data? Impact of the dbt cleaning pipeline.",
        ),
        unsafe_allow_html=True,
    )

    if not impact:
        st.warning("⚠️ No Silver data available. Run `dbt run` first.")
        return

    total = impact.get("total_silver", 0)

    # ── Transformation Summary KPIs ───────────────────────────────────────────
    k1, k2, k3, k4, k5 = st.columns(5)

    with k1:
        st.metric(
            "Models from NLP Title",
            f"{impact.get('models_from_nlp_title', 0):,}",
            help="Vehicle models recovered from Khmer/English titles via regex NLP when sellers left form blank.",
        )
        st.caption("Title extraction uplift")

    with k2:
        st.metric(
            "Model Years Healed",
            f"{impact.get('years_healed', 0):,}",
            help="Chronological inversions corrected (e.g., 2026→2006 for legacy models like Prius, RX330).",
        )
        st.caption("Year inversion repair")

    with k3:
        st.metric(
            "Down-Payment Traps",
            f"{impact.get('down_payment_flagged', 0):,}",
            help="Listings flagged as financing down-payments rather than full vehicle prices.",
        )
        st.caption("Flagged SUSPICIOUS")

    with k4:
        st.metric(
            "Price Outliers Flagged",
            f"{impact.get('outliers_flagged', 0):,}",
            help="Listings with domain-grounded price anomalies — verified against brand/model/year distribution.",
        )
        st.caption("Flagged SUSPICIOUS")

    with k5:
        st.metric(
            "Spam Listings Quarantined",
            f"{impact.get('spam_flagged', 0):,}",
            help="Non-vehicle listings (parts, accessories, services) detected by NLP spam classifier.",
        )
        st.caption("Quarantined from Silver")

    st.divider()

    # ── Transformation Flow ───────────────────────────────────────────────────
    st.markdown(
        config.section_header(
            "TRANSFORMATION PIPELINE FLOW",
            "Records processed at each dbt transformation step.",
        ),
        unsafe_allow_html=True,
    )

    _render_transformation_flow(impact, funnel_df, total)

    st.divider()

    # ── Before vs After: Raw vs Conformed ─────────────────────────────────────
    st.markdown(
        config.section_header(
            "RAW vs CONFORMED ATTRIBUTE COVERAGE",
            "Measurable uplift from Bronze → Silver dbt transformations.",
        ),
        unsafe_allow_html=True,
    )

    _render_before_after(comp_df)

    st.divider()

    # ── Transformation Rules Catalog ──────────────────────────────────────────
    st.markdown(
        config.section_header(
            "DBT TRANSFORMATION RULES CATALOG",
            "Documentation of cleaning rules applied in int_cars_cleaned.sql.",
        ),
        unsafe_allow_html=True,
    )

    _render_rules_catalog(rules_df)

    st.divider()

    # ── Model Extraction Breakdown ────────────────────────────────────────────
    _render_model_source_breakdown(impact, total)


# ─────────────────────────────────────────────────────────────────────────────

def _render_transformation_flow(impact: dict, funnel_df: pd.DataFrame, total: int) -> None:
    """Shows the transformation stages as an annotated flow."""

    # Define the logical stages
    stages = []

    # Stage 1: Bronze raw
    if not funnel_df.empty:
        bronze_row = funnel_df[funnel_df["stage"].str.contains("Bronze", na=False)]
        bronze_cnt = int(bronze_row["count"].iloc[0]) if not bronze_row.empty else 0
        stages.append(("RAW (Bronze)", bronze_cnt, "Raw scraped HTTP JSON payloads", "#0284c7"))
    else:
        stages.append(("RAW (Bronze)", 0, "Bronze data not available", "#94a3b8"))

    # Stage 2: Staging (rename + cast)
    stages.append(("Staging Layer", total, "Renamed, cast, intra-day deduplication applied", "#0284c7"))

    # Stage 3: Brand / Model / Location standardized
    stages.append(("Standardized", total, "Brand, model, province mapped to canonical forms", "#7c3aed"))

    # Stage 4: Spec parsing
    stages.append(("Spec Parsing", total, "Mileage, engine CC parsed from text; year healed", "#d97706"))

    # Stage 5: Quality classification
    stages.append(("Quality Classified", total, "5-tier DQ status assigned (VALID/WARNING/SUSPICIOUS/INVALID/QUARANTINED)", "#dc2626"))

    # Stage 6: Silver output
    silver_valid = impact.get("preserved_count", 0)
    stages.append(("Silver (preserved)", silver_valid, "Non-quarantined records available for analytics", "#16a34a"))

    base = stages[0][1] if stages[0][1] > 0 else 1

    for stage_name, count, desc, color in stages:
        pct = round(100.0 * count / base, 1) if base > 0 else 0.0
        bar_w = max(4, min(100, int(pct)))
        st.markdown(
            f"""
            <div style='display:flex; align-items:flex-start; gap:12px; margin-bottom:10px;'>
                <div style='min-width:200px; font-size:0.82rem; font-weight:700; color:#1e293b;
                            padding-top:3px; text-align:right;'>
                    {stage_name}
                </div>
                <div style='flex:1;'>
                    <div style='display:flex; align-items:center; gap:8px;'>
                        <div style='background:#e2e8f0; border-radius:3px; height:18px; flex:1; overflow:hidden;'>
                            <div style='width:{bar_w}%; background:{color}; height:18px; border-radius:3px;
                                        display:flex; align-items:center; justify-content:flex-end; padding-right:6px;'>
                                <span style='font-size:0.70rem; font-weight:700; color:white; white-space:nowrap;'>
                                    {count:,} &nbsp; {pct:.1f}%
                                </span>
                            </div>
                        </div>
                    </div>
                    <div style='font-size:0.74rem; color:#64748b; margin-top:2px;'>{desc}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_before_after(comp_df: pd.DataFrame) -> None:
    """Before/after comparison of Bronze raw fill vs Silver conformed fill."""
    if comp_df.empty:
        st.info("No Bronze/Silver comparison data available. Requires both Bronze and Silver layers.")
        return

    col_chart, col_detail = st.columns([3, 2], gap="large")

    with col_chart:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=comp_df["attribute"],
            y=comp_df["raw_bronze_fill_pct"],
            name="Raw Bronze Fill (%)",
            marker_color="#cbd5e1",
            hovertemplate="Raw: %{y:.1f}%<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=comp_df["attribute"],
            y=comp_df["conformed_silver_fill_pct"],
            name="Conformed Silver Fill (%)",
            marker_color="#1e3a8a",
            hovertemplate="Silver: %{y:.1f}%<extra></extra>",
        ))
        config.apply_plot_theme(fig, height=300, show_legend=True, legend_orientation="h")
        fig.update_layout(
            barmode="group",
            yaxis=dict(title="Fill Rate (%)", range=[0, 106]),
            xaxis_title=None,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_detail:
        st.markdown("**Uplift by Attribute**")
        for _, row in comp_df.iterrows():
            uplift = float(row.get("uplift_pct", 0))
            arrow  = "↑" if uplift > 0 else "→"
            color  = "#16a34a" if uplift > 0 else "#64748b"
            st.markdown(
                f"""
                <div style='display:flex; justify-content:space-between; align-items:center;
                            padding:6px 0; border-bottom:1px solid #f1f5f9; font-size:0.82rem;'>
                    <span style='font-weight:600; color:#334155;'>{row['attribute']}</span>
                    <span style='color:{color}; font-weight:700;'>
                        {row['raw_bronze_fill_pct']:.1f}% {arrow} {row['conformed_silver_fill_pct']:.1f}%
                        &nbsp;
                        <span style='font-size:0.75rem;'>(+{uplift:.1f}pp)</span>
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("""
        <div style='margin-top:12px; padding:10px; background:#f8fafc; border-radius:6px;
                    border-left:3px solid #0284c7; font-size:0.78rem; color:#475569;'>
            <b>How uplift is achieved:</b><br>
            Brand: Seed dictionary + Khmer/English title regex<br>
            Model: 137+ model aliases + NLP title extraction<br>
            Year: Chronological inversion healing<br>
            Fuel / Transmission: Multilingual seed mapping
        </div>
        """, unsafe_allow_html=True)


def _render_rules_catalog(rules_df: pd.DataFrame) -> None:
    """Show the dbt transformation rules catalog table."""
    if rules_df.empty:
        st.info("No transformation rules data available.")
        return

    st.dataframe(
        rules_df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "attribute":         st.column_config.TextColumn("Field", width="small"),
            "transformation":    st.column_config.TextColumn("Transformation", width="medium"),
            "logic":             st.column_config.TextColumn("Logic & Recovery", width="large"),
            "conformance_rule":  st.column_config.TextColumn("Conformance Rule", width="large"),
        },
    )


def _render_model_source_breakdown(impact: dict, total: int) -> None:
    """Show how vehicle models were resolved."""
    st.markdown(
        config.section_header(
            "MODEL RESOLUTION SOURCES",
            "How vehicle models were resolved across all Silver records.",
        ),
        unsafe_allow_html=True,
    )

    seed_n   = impact.get("models_from_seed_alias", 0)
    nlp_n    = impact.get("models_from_nlp_title", 0)
    raw_n    = impact.get("models_from_raw_spec", 0)
    other_n  = max(0, total - seed_n - nlp_n - raw_n)

    labels = ["Seed Alias Dictionary", "NLP Title Extraction", "Raw Spec Dropdown", "Unknown / NULL"]
    values = [seed_n, nlp_n, raw_n, other_n]
    colors = ["#1e3a8a", "#0284c7", "#16a34a", "#e2e8f0"]

    non_zero = [(l, v, c) for l, v, c in zip(labels, values, colors) if v > 0]
    if not non_zero:
        st.info("No model source data available.")
        return

    labels  = [x[0] for x in non_zero]
    values  = [x[1] for x in non_zero]
    colors  = [x[2] for x in non_zero]

    col_pie, col_text = st.columns([2, 3], gap="large")

    with col_pie:
        fig = go.Figure(go.Pie(
            labels=labels,
            values=values,
            marker_colors=colors,
            hole=0.5,
            textinfo="percent",
            hovertemplate="<b>%{label}</b><br>%{value:,} records (%{percent})<extra></extra>",
            sort=False,
        ))
        config.apply_plot_theme(fig, height=260, show_legend=True, legend_orientation="h")
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with col_text:
        st.markdown("**Model Resolution Strategy**")
        descs = {
            "Seed Alias Dictionary": "Canonical model names from a curated seed CSV mapping 417 standardized models to common raw aliases.",
            "NLP Title Extraction":  "Regex patterns extract model names from Khmer/English free-text listing titles when sellers leave dropdowns blank.",
            "Raw Spec Dropdown":     "Seller-entered dropdown selection directly used (after whitespace/character cleaning).",
            "Unknown / NULL":        "Model could not be resolved from any source. Retained as NULL — no silent imputation.",
        }
        for label, desc in descs.items():
            cnt = dict(zip(labels, values)).get(label, 0)
            if cnt > 0:
                pct = round(100.0 * cnt / max(total, 1), 1)
                st.markdown(
                    f"""
                    <div style='margin-bottom:10px; padding:8px 12px; background:#f8fafc;
                                border-radius:5px; border-left:3px solid #0284c7;'>
                        <div style='font-size:0.82rem; font-weight:700; color:#1e293b;'>
                            {label} — {cnt:,} ({pct:.1f}%)
                        </div>
                        <div style='font-size:0.76rem; color:#64748b; margin-top:3px;'>{desc}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
