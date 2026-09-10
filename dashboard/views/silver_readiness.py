"""
dashboard/views/silver_readiness.py
=====================================
Page 7 — Silver Readiness
Answers: Is the Silver dataset trustworthy enough for the next project phase?

This is NOT ML. It is a downstream data-readiness assessment only.
No model training, prediction, encoding, or SHAP values.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard import config
from dashboard.data_loader import (
    load_cleaning_impact_stats,
    load_completeness_detail,
    load_dbt_test_status,
    load_duplicate_stats,
    load_quality_summary,
    load_scraper_health,
)


def render(active_date: str | None = None) -> None:
    """Render the Silver Readiness page."""
    quality_df  = load_quality_summary()
    dup_stats   = load_duplicate_stats()
    dbt_status  = load_dbt_test_status()
    impact      = load_cleaning_impact_stats(active_date)
    complete_df = load_completeness_detail(active_date)
    scraper     = load_scraper_health()

    st.markdown(
        config.section_header(
            "SILVER READINESS",
            "Is the Silver dataset trustworthy enough for downstream analytics? "
            "No ML — readiness assessment only.",
        ),
        unsafe_allow_html=True,
    )

    if quality_df.empty:
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

    # Silver-ready = VALID + WARNING (has data, just optional fields missing)
    silver_ready = valid_cnt + warn_cnt
    silver_ready_pct = round(100.0 * silver_ready / total, 1) if total > 0 else 0.0
    silver_unique = dup_stats.get("silver_unique", 0)

    # ── Overall Readiness Verdict ─────────────────────────────────────────────
    _render_verdict(dhi_score, silver_ready_pct, dbt_status, scraper, total)

    st.divider()

    # ── Readiness Checklist ───────────────────────────────────────────────────
    st.markdown(
        config.section_header("READINESS CHECKLIST", "Row-level criteria for downstream analytics suitability."),
        unsafe_allow_html=True,
    )

    # Build checklist from real data
    price_completeness = 0.0
    year_completeness  = 0.0
    brand_completeness = 0.0

    if not complete_df.empty:
        for _, row in complete_df.iterrows():
            f = row["field"]
            if f == "price":
                price_completeness = float(row["completeness_pct"])
            elif f == "vehicle_year":
                year_completeness = float(row["completeness_pct"])
            elif f == "vehicle_brand":
                brand_completeness = float(row["completeness_pct"])

    # How many have valid price
    valid_price_count = int(round(total * price_completeness / 100)) if total > 0 else 0
    valid_year_count  = int(round(total * year_completeness  / 100)) if total > 0 else 0

    checks = [
        (
            "Valid Listing ID",
            silver_unique,
            total,
            "Records with a non-null, unique listing_id per scrape date.",
            silver_unique / total >= 0.99 if total > 0 else False,
        ),
        (
            "Valid Price (USD > 0)",
            valid_price_count,
            total,
            "Records with a confirmed non-null, positive USD price.",
            price_completeness >= 99.0,
        ),
        (
            "Valid Model Year",
            valid_year_count,
            total,
            "Records with a year in the valid automotive range [1990 – current year + 1].",
            year_completeness >= 95.0,
        ),
        (
            "Classified as Vehicle Listing",
            total - quar_cnt,
            total,
            "Non-quarantined records — spam and non-vehicle listings excluded.",
            quar_cnt / total < 0.02 if total > 0 else True,
        ),
        (
            "No Critical DQ Errors",
            valid_cnt + warn_cnt,
            total,
            "Records classified VALID or WARNING — no INVALID or QUARANTINED status.",
            silver_ready_pct >= 90.0,
        ),
        (
            "Available for Downstream Analytics",
            silver_ready,
            total,
            "Final count of Silver records suitable for analytics, dashboards, or future ML feature engineering.",
            silver_ready_pct >= 85.0,
        ),
    ]

    for check_name, count, base, desc, passed in checks:
        pct   = round(100.0 * count / base, 1) if base > 0 else 0.0
        icon  = "✅" if passed else "⚠️"
        color = "#166534" if passed else "#92400e"
        bg    = "#f0fdf4" if passed else "#fffbeb"
        bar_color = "#16a34a" if passed else "#d97706"

        st.markdown(
            f"""
            <div style='background:{bg}; border:1px solid {color}20; border-left:4px solid {bar_color};
                        border-radius:6px; padding:12px 16px; margin-bottom:8px;
                        display:flex; justify-content:space-between; align-items:center; gap:16px; flex-wrap:wrap;'>
                <div style='flex:1; min-width:260px;'>
                    <div style='font-size:0.85rem; font-weight:700; color:{color};'>
                        {icon} {check_name}
                    </div>
                    <div style='font-size:0.76rem; color:#64748b; margin-top:3px;'>{desc}</div>
                </div>
                <div style='text-align:right; font-size:0.88rem; font-weight:700; color:{color}; white-space:nowrap;'>
                    {count:,} / {base:,}
                    <div style='font-size:0.78rem; font-weight:600;'>{pct:.1f}%</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Quality Breakdown Bar ──────────────────────────────────────────────────
    st.markdown(
        config.section_header("QUALITY TIER BREAKDOWN", "Distribution of all Silver records by quality status."),
        unsafe_allow_html=True,
    )

    _render_quality_breakdown(valid_cnt, warn_cnt, susp_cnt, inv_cnt, quar_cnt, total)

    st.divider()

    # ── Transformation Uplift Summary ─────────────────────────────────────────
    st.markdown(
        config.section_header("CLEANING UPLIFT SUMMARY", "Value added by the dbt transformation pipeline."),
        unsafe_allow_html=True,
    )

    _render_uplift_summary(impact, dbt_status)

    st.divider()

    # ── Remaining Blockers ────────────────────────────────────────────────────
    _render_blockers(complete_df, impact, dbt_status, silver_ready_pct)


# ─────────────────────────────────────────────────────────────────────────────

def _render_verdict(
    dhi_score: float,
    silver_ready_pct: float,
    dbt_status: dict,
    scraper: dict,
    total: int,
) -> None:
    """Overall readiness verdict banner."""
    dbt_ok   = dbt_status.get("failed", 0) == 0 if dbt_status.get("available") else True
    data_ok  = total >= config.SLA_MIN_RECORDS_PER_DAY
    dhi_ok   = dhi_score >= config.SLA_MIN_DHI
    ready_ok = silver_ready_pct >= 85.0

    gates = [dbt_ok, data_ok, dhi_ok, ready_ok]
    passing = sum(gates)

    if all(gates):
        verdict = "✅ SILVER DATASET READY FOR DOWNSTREAM ANALYTICS"
        bg, border = "#f0fdf4", "#16a34a"
        detail = (
            f"All readiness gates pass. {total:,} total records, "
            f"{silver_ready_pct:.1f}% classified as analytics-ready, "
            f"DHI = {dhi_score:.1f}%, dbt contracts passing."
        )
    elif passing >= 3:
        verdict = "⚠️ SILVER DATASET CONDITIONALLY READY"
        bg, border = "#fffbeb", "#d97706"
        issues = []
        if not dbt_ok:     issues.append(f"dbt tests failing ({dbt_status.get('failed', '?')} failures)")
        if not data_ok:    issues.append(f"Low record volume ({total:,} < {config.SLA_MIN_RECORDS_PER_DAY:,} SLA)")
        if not dhi_ok:     issues.append(f"DHI {dhi_score:.1f}% below {config.SLA_MIN_DHI:.0f}%")
        if not ready_ok:   issues.append(f"Silver ready rate {silver_ready_pct:.1f}% below 85% threshold")
        detail = "Minor issues detected: " + " · ".join(issues) + ". Review before proceeding."
    else:
        verdict = "🚫 SILVER DATASET BLOCKED — DATA QUALITY ISSUES"
        bg, border = "#fef2f2", "#dc2626"
        detail = (
            f"Multiple gates failing: {passing}/4 passing. "
            f"DHI = {dhi_score:.1f}%, Silver Ready = {silver_ready_pct:.1f}%. "
            "Resolve critical DQ issues before downstream use."
        )

    st.markdown(
        f"""
        <div style='background:{bg}; border-left:5px solid {border}; border-radius:6px;
                    padding:16px 20px; margin-bottom:18px;'>
            <div style='font-size:1.0rem; font-weight:800; color:{border}; margin-bottom:6px;'>
                {verdict}
            </div>
            <div style='font-size:0.85rem; color:#475569;'>{detail}</div>
            <div style='margin-top:12px; display:flex; gap:16px; flex-wrap:wrap;'>
                <span style='font-size:0.78rem; font-weight:700; color:{border};'>
                    SLA Gates: {passing}/4 passing
                </span>
                <span style='font-size:0.78rem; color:#64748b;'>
                    DHI: <b>{dhi_score:.1f}%</b>
                </span>
                <span style='font-size:0.78rem; color:#64748b;'>
                    Silver Ready: <b>{silver_ready_pct:.1f}%</b>
                </span>
                <span style='font-size:0.78rem; color:#64748b;'>
                    Records: <b>{total:,}</b>
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_quality_breakdown(
    valid_cnt: int, warn_cnt: int, susp_cnt: int,
    inv_cnt: int, quar_cnt: int, total: int,
) -> None:
    """Stacked horizontal bar showing quality tier distribution."""
    if total == 0:
        st.info("No data available.")
        return

    tiers = [
        ("VALID",       valid_cnt, "#16a34a"),
        ("WARNING",     warn_cnt,  "#d97706"),
        ("SUSPICIOUS",  susp_cnt,  "#c2410c"),
        ("INVALID",     inv_cnt,   "#dc2626"),
        ("QUARANTINED", quar_cnt,  "#374151"),
    ]

    # Stacked horizontal bar
    fig = go.Figure()
    for label, cnt, color in tiers:
        pct = round(100.0 * cnt / total, 1) if total > 0 else 0.0
        fig.add_trace(go.Bar(
            y=["Quality Distribution"],
            x=[cnt],
            name=f"{config.STATUS_DOT.get(label, '●')} {label}",
            orientation="h",
            marker_color=color,
            hovertemplate=f"<b>{label}</b><br>{cnt:,} records ({pct:.1f}%)<extra></extra>",
        ))

    config.apply_plot_theme(fig, height=120, show_legend=True, legend_orientation="h")
    fig.update_layout(
        barmode="stack",
        xaxis=dict(title="Record Count", tickformat=","),
        yaxis=dict(showticklabels=False),
        margin=dict(l=10, r=10, t=10, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Legend table
    cols = st.columns(5)
    for col, (label, cnt, color) in zip(cols, tiers):
        pct = round(100.0 * cnt / total, 1) if total > 0 else 0.0
        col.markdown(
            f"""
            <div style='text-align:center; padding:8px 4px; background:#f8fafc;
                        border-radius:5px; border-top:3px solid {color};'>
                <div style='font-size:0.72rem; font-weight:700; color:{color}; text-transform:uppercase;'>{label}</div>
                <div style='font-size:1.15rem; font-weight:800; color:#1e293b;'>{cnt:,}</div>
                <div style='font-size:0.72rem; color:#64748b;'>{pct:.1f}%</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_uplift_summary(impact: dict, dbt_status: dict) -> None:
    """Show transformation uplift facts."""
    if not impact:
        st.info("No transformation impact data available.")
        return

    items = [
        ("NLP Models Recovered", impact.get("models_from_nlp_title", 0),
         "Vehicle models extracted from Khmer/English title text when seller left form blank."),
        ("Year Inversions Healed", impact.get("years_healed", 0),
         "Chronologically impossible years corrected (e.g., 2026→2006 for legacy models)."),
        ("Down-Payment Traps Flagged", impact.get("down_payment_flagged", 0),
         "Listings misrepresenting financing down-payments as vehicle sale prices."),
        ("Spam Listings Quarantined", impact.get("spam_flagged", 0),
         "Non-vehicle listings removed from the analytics dataset."),
    ]

    c1, c2, c3, c4 = st.columns(4)
    for col, (label, count, desc) in zip([c1, c2, c3, c4], items):
        col.metric(label, f"{count:,}")
        col.caption(desc)

    # dbt test status
    if dbt_status.get("available"):
        passed = dbt_status.get("passed", 0)
        total_t = dbt_status.get("total", 0)
        ok = dbt_status.get("failed", 0) == 0
        icon = "✅" if ok else "❌"
        color = "#166534" if ok else "#991b1b"
        st.markdown(
            f"""
            <div style='margin-top:12px; padding:10px 16px; background:#f8fafc; border-radius:6px;
                        border-left:4px solid {color}; font-size:0.82rem;'>
                <b>{icon} dbt Schema Contract Tests:</b> {passed}/{total_t} passing
                &nbsp;·&nbsp; Pass rate: <b>{dbt_status.get('pass_rate_pct', 0)}%</b>
                &nbsp;·&nbsp; Elapsed: {dbt_status.get('elapsed_seconds', 0)}s
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_blockers(
    complete_df: pd.DataFrame,
    impact: dict,
    dbt_status: dict,
    silver_ready_pct: float,
) -> None:
    """Remaining limitations and blockers for this pipeline phase."""
    st.markdown(
        config.section_header(
            "REMAINING LIMITATIONS",
            "Known data gaps that cannot be resolved at the current pipeline phase.",
        ),
        unsafe_allow_html=True,
    )

    blockers = []

    # Mileage missingness
    if not complete_df.empty:
        m_row = complete_df[complete_df["field"] == "vehicle_mileage_km"]
        if not m_row.empty:
            mp = float(m_row.iloc[0]["null_pct"])
            if mp > 10:
                blockers.append({
                    "Issue": "High mileage missingness",
                    "Impact": f"{mp:.0f}% of Silver records have no odometer data",
                    "Severity": "🟡 Accepted",
                    "Resolution": "Binary missingness flag (`is_mileage_missing`) planned for downstream. "
                                  "Cambodia market norm — not a pipeline failure.",
                })

        # Engine CC missingness
        e_row = complete_df[complete_df["field"] == "vehicle_engine_cc"]
        if not e_row.empty:
            ep = float(e_row.iloc[0]["null_pct"])
            if ep > 10:
                blockers.append({
                    "Issue": "Engine CC missingness",
                    "Impact": f"{ep:.0f}% of records missing engine displacement",
                    "Severity": "🟡 Accepted",
                    "Resolution": "NLP parsing from title/description partially resolves. EVs correctly coded 0 cc.",
                })

    # Gold layer not built
    blockers.append({
        "Issue": "Gold analytics layer not yet built",
        "Impact": "Downstream analytics marts (Gold) are not yet available",
        "Severity": "🔵 Planned",
        "Resolution": "Gold layer (fct_car_listings) scheduled for next development phase. "
                      "Silver is the current terminus.",
    })

    # ML not built
    blockers.append({
        "Issue": "ML pipeline not yet implemented",
        "Impact": "No predictive model exists yet",
        "Severity": "🔵 Planned",
        "Resolution": "Silver Readiness assessment only. ML feature engineering and training are the next project phase.",
    })

    if not blockers:
        st.success("No known blockers. Silver dataset is fully ready.")
        return

    for b in blockers:
        sev = b["Severity"]
        sev_color = "#1d4ed8" if "Planned" in sev else "#92400e" if "Accepted" in sev else "#dc2626"
        st.markdown(
            f"""
            <div style='padding:10px 14px; margin-bottom:8px; background:#f8fafc;
                        border-radius:6px; border-left:4px solid {sev_color};'>
                <div style='display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap;'>
                    <div style='font-size:0.83rem; font-weight:700; color:#1e293b;'>{b['Issue']}</div>
                    <span style='font-size:0.72rem; font-weight:700; color:{sev_color};'>{sev}</span>
                </div>
                <div style='font-size:0.78rem; color:#dc2626; margin-top:3px;'>Impact: {b['Impact']}</div>
                <div style='font-size:0.76rem; color:#64748b; margin-top:3px;'>Resolution: {b['Resolution']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
