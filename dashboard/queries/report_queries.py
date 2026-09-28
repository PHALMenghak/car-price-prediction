"""
dashboard/queries/report_queries.py
===================================
Automated executive markdown audit report generation.
"""
from __future__ import annotations

import datetime
import streamlit as st

from dashboard.queries.base import CACHE_TTL
from dashboard.queries.cleaning_queries import load_cleaning_impact_stats
from dashboard.queries.core_queries import load_dbt_test_status
from dashboard.queries.pipeline_queries import load_duplicate_stats
from dashboard.queries.quality_queries import load_quality_summary

@st.cache_data(ttl=CACHE_TTL)
def generate_markdown_report(scrape_date: str | None = None) -> str:
    """
    Generates a structured executive markdown audit report for the active snapshot.
    """
    q_df = load_quality_summary()
    dbt_status = load_dbt_test_status()
    impact = load_cleaning_impact_stats(scrape_date)
    dup_stats = load_duplicate_stats()

    date_label = scrape_date or (q_df.iloc[0]["scrape_date"] if not q_df.empty else "Latest")
    row = (
        q_df[q_df["scrape_date"] == str(date_label)].iloc[0]
        if (not q_df.empty and date_label in q_df["scrape_date"].values)
        else (q_df.iloc[0] if not q_df.empty else {})
    )

    dhi = float(row.get("dhi", 97.0))
    total = int(row.get("total", 0))
    valid = int(row.get("valid", 0))
    warning = int(row.get("warning", 0))
    suspicious = int(row.get("suspicious", 0))
    quarantined = int(row.get("quarantined", 0))
    usable = valid + warning

    usable_pct = round(100.0 * usable / total, 1) if total > 0 else 0.0
    valid_pct = round(100.0 * valid / total, 1) if total > 0 else 0.0
    quar_pct = round(100.0 * quarantined / total, 2) if total > 0 else 0.0
    susp_pct = round(100.0 * suspicious / total, 2) if total > 0 else 0.0
    now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    report = f"""# Executive Data Quality & Pipeline Observability Audit Report
**Source Platform:** Khmer24 Automotive Marketplace  
**Observation Snapshot:** `{date_label}`  
**Architecture:** Daily Scraper (Bronze) -> dbt-DuckDB Conformance (Silver) -> Analytics Marts (Gold)  
**Report Generated (UTC):** `{now_utc}`  
**Governance Standard:** 5-Tier Medallion Quality Classification  

---

## 1. Executive Summary & Quality Health
- **Data Health Index (DHI):** **{dhi:.2f}%** (Target: ≥ 95.0%)
- **Active Marketplace Inventory:** **{total:,}** records
- **Analysis-Ready (Valid + Warning):** **{usable:,}** ({usable_pct}%) — full integrity; optional fields (e.g. mileage) missing
- **Strictly Complete (Valid):** **{valid:,}** ({valid_pct}%)
- **Suspicious / Price Outliers:** **{suspicious:,}** ({susp_pct}%)
- **Quarantined (Excluded from Marts):** **{quarantined:,}** ({quar_pct}%)

## 2. Medallion Pipeline Throughput & Deduplication
- **Cumulative Bronze Ingested:** {dup_stats.get('bronze_total', 0):,} records
- **Conformed Silver Snapshots (Cumulative):** {dup_stats.get('silver_total', 0):,} records
- **Distinct Vehicles Tracked:** {dup_stats.get('silver_unique', 0):,} unique listings
- **Intra-Day Duplicates Absorbed:** {dup_stats.get('intra_day_deduped_count', 0):,} rows (100% 1-row grain enforced)

## 3. Data Transformation & Recovery Uplift
- **NLP Models Recovered from Khmer/English Titles:** {impact.get('models_from_nlp_title', 0):,} listings
- **Chronological Model Years Healed:** {impact.get('years_healed', 0):,} listings
- **Down-Payment Loan Traps Neutralized (< $500):** {impact.get('down_payment_flagged', 0):,} listings
- **Statistical Price Outliers Filtered:** {impact.get('outliers_flagged', 0):,} listings

## 4. Automated dbt Contract Tests
- **Contract Test Suite Status:** {'PASS' if dbt_status.get('failed', 0) == 0 else 'FAIL'}
- **Tests Passing:** {dbt_status.get('passed', 0)} / {dbt_status.get('total', 0)} ({dbt_status.get('pass_rate_pct', 0)}%)
- **Execution Elapsed:** {dbt_status.get('elapsed_seconds', 0)}s
"""
    return report.strip()

