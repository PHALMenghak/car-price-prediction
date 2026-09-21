"""
dashboard/queries/cleaning_queries.py
=====================================
Missingness trends, attribute completeness, cleaning impact, and before/after conformed comparisons.
"""
from __future__ import annotations

import os
from pathlib import Path
import pandas as pd
import streamlit as st

from dashboard import config
from dashboard.queries.base import (
    _con,
    _BRONZE_DIR,
    BRONZE_GLOB,
    CACHE_TTL,
    SILVER_PATH,
)

@st.cache_data(ttl=CACHE_TTL)
def load_daily_missingness_trend() -> pd.DataFrame:
    """
    Returns daily null percentages for core vehicle attributes across all snapshots.
    Used to render interactive missingness trend line charts.
    """
    if not os.path.exists(SILVER_PATH):
        return pd.DataFrame()
    con = _con()
    try:
        df = con.execute(f"""
            SELECT
                CAST(scrape_date AS VARCHAR) AS scrape_date,
                ROUND(100.0 * COUNT(*) FILTER (WHERE price IS NULL) / COUNT(*), 2) AS "Price (Target)",
                ROUND(100.0 * COUNT(*) FILTER (WHERE vehicle_brand IS NULL) / COUNT(*), 2) AS "Brand",
                ROUND(100.0 * COUNT(*) FILTER (WHERE vehicle_model IS NULL) / COUNT(*), 2) AS "Model",
                ROUND(100.0 * COUNT(*) FILTER (WHERE vehicle_year IS NULL) / COUNT(*), 2) AS "Year",
                ROUND(100.0 * COUNT(*) FILTER (WHERE vehicle_mileage_km IS NULL) / COUNT(*), 2) AS "Mileage",
                ROUND(100.0 * COUNT(*) FILTER (WHERE vehicle_engine_cc IS NULL) / COUNT(*), 2) AS "Engine Size"
            FROM read_parquet('{SILVER_PATH}')
            GROUP BY 1
            ORDER BY 1 ASC
        """).df()
    except Exception:
        df = pd.DataFrame()
    finally:
        con.close()
    return df


@st.cache_data(ttl=CACHE_TTL)
def load_completeness_detail(scrape_date: str | None = None) -> pd.DataFrame:
    """
    Detailed column completeness breakdown with counts, percentages, and priority tiers.
    Optimized to compute all field statistics in a single Parquet scan.
    """
    if not os.path.exists(SILVER_PATH):
        return pd.DataFrame()

    critical = ["price", "vehicle_brand", "vehicle_model", "vehicle_year", "province"]
    medium   = ["vehicle_mileage_km", "vehicle_engine_cc", "vehicle_fuel_type",
                "vehicle_transmission", "vehicle_body_type", "vehicle_tax_type"]
    low      = ["vehicle_color", "vehicle_condition", "title_clean"]

    fields = critical + medium + low
    priority_map = (
        {f: "🔴 Critical" for f in critical}
        | {f: "🟡 Medium" for f in medium}
        | {f: "🟢 Low" for f in low}
    )

    date_filter = (
        f"WHERE CAST(scrape_date AS VARCHAR) = '{scrape_date}'"
        if scrape_date
        else ""
    )

    con = _con()
    try:
        agg_exprs = ", ".join([f"COUNT({f}) AS cnt_{f}" for f in fields])
        query = f"SELECT COUNT(*) AS total_records, {agg_exprs} FROM read_parquet('{SILVER_PATH}') {date_filter}"
        row = con.execute(query).fetchone()
        if not row:
            return pd.DataFrame()

        total = int(row[0] or 0)
        records = []
        for i, f in enumerate(fields, start=1):
            non_null = int(row[i] or 0)
            null_cnt = total - non_null
            comp_pct = round(100.0 * non_null / total, 2) if total > 0 else 0.0
            null_pct = round(100.0 * null_cnt / total, 2) if total > 0 else 0.0
            records.append({
                "field": f,
                "total_records": total,
                "non_null_count": non_null,
                "null_count": null_cnt,
                "completeness_pct": comp_pct,
                "null_pct": null_pct,
                "priority": priority_map.get(f, "🟢 Low"),
            })

        df = pd.DataFrame(records)
        priority_rank = {"🔴 Critical": 1, "🟡 Medium": 2, "🟢 Low": 3}
        df["rank"] = df["priority"].map(priority_rank)
        df = df.sort_values(by=["rank", "completeness_pct"], ascending=[True, False]).drop(columns=["rank"])
    except Exception:
        df = pd.DataFrame()
    finally:
        con.close()
    return df


@st.cache_data(ttl=CACHE_TTL)
def load_cleaning_impact_stats(scrape_date: str | None = None) -> dict:
    """
    Measures positive uplift created by cleaning: years healed, title NLP models,
    seed normalization, spam & down-payment prevention, and quarantined items.
    """
    if not os.path.exists(SILVER_PATH):
        return {}

    date_filter = f"WHERE CAST(scrape_date AS VARCHAR) = '{scrape_date}'" if scrape_date else ""
    con = _con()
    try:
        row = con.execute(f"""
            SELECT
                COUNT(*) AS total_silver,
                COALESCE(SUM(is_year_healed), 0) AS years_healed,
                COUNT(*) FILTER (WHERE model_extraction_method = 'title_extracted') AS models_from_nlp_title,
                COUNT(*) FILTER (WHERE model_extraction_method = 'seed_alias') AS models_from_seed_alias,
                COUNT(*) FILTER (WHERE model_extraction_method = 'raw_spec') AS models_from_raw_spec,
                COUNT(*) FILTER (WHERE is_spam = 1) AS spam_flagged,
                COUNT(*) FILTER (WHERE is_down_payment = 1) AS down_payment_flagged,
                COUNT(*) FILTER (WHERE is_price_outlier = 1) AS outliers_flagged,
                COUNT(*) FILTER (WHERE data_quality_status = 'QUARANTINED') AS quarantined
            FROM read_parquet('{SILVER_PATH}')
            {date_filter}
        """).fetchone()
    except Exception:
        row = None
    finally:
        con.close()

    if not row or row[0] == 0:
        return {}

    total = int(row[0])
    quarantined = int(row[8] or 0)
    preserved = total - quarantined

    return {
        "total_silver": total,
        "years_healed": int(row[1] or 0),
        "models_from_nlp_title": int(row[2] or 0),
        "models_from_seed_alias": int(row[3] or 0),
        "models_from_raw_spec": int(row[4] or 0),
        "spam_flagged": int(row[5] or 0),
        "down_payment_flagged": int(row[6] or 0),
        "outliers_flagged": int(row[7] or 0),
        "quarantined": quarantined,
        "preserved_count": preserved,
        "preserved_pct": round(100.0 * preserved / total, 1),
        "excluded_count": quarantined,
        "excluded_pct": round(100.0 * quarantined / total, 1),
    }


@st.cache_data(ttl=CACHE_TTL)
def load_raw_vs_conformed_comparison(scrape_date: str | None = None) -> pd.DataFrame:
    """
    Compares raw Bronze fill rate vs conformed Silver fill rate for key attributes.
    Highlights data engineering value added by dbt transformations.
    """
    if not os.path.exists(SILVER_PATH) or len(list(_BRONZE_DIR.glob("cars_*.parquet"))) == 0:
        return pd.DataFrame()

    con = _con()
    b_date_filter = f"WHERE TRY_CAST(scraped_at AS DATE) = '{scrape_date}'" if scrape_date else ""
    s_date_filter = f"WHERE CAST(scrape_date AS VARCHAR) = '{scrape_date}'" if scrape_date else ""

    try:
        df = con.execute(f"""
            WITH bronze_latest AS (
                SELECT
                    listing_id,
                    raw_spec_brand,
                    raw_spec_model,
                    raw_spec_year,
                    raw_spec_transmission,
                    raw_spec_fuel_type,
                    ROW_NUMBER() OVER (PARTITION BY listing_id ORDER BY scraped_at DESC) as _rn
                FROM read_parquet('{BRONZE_GLOB}', union_by_name=true)
                {b_date_filter}
            ),
            silver_latest AS (
                SELECT
                    listing_id,
                    vehicle_brand,
                    vehicle_model,
                    vehicle_year,
                    vehicle_transmission,
                    vehicle_fuel_type,
                    ROW_NUMBER() OVER (PARTITION BY listing_id ORDER BY scraped_at DESC) as _rn
                FROM read_parquet('{SILVER_PATH}')
                {s_date_filter}
            ),
            joined AS (
                SELECT
                    b.raw_spec_brand, s.vehicle_brand,
                    b.raw_spec_model, s.vehicle_model,
                    b.raw_spec_year, s.vehicle_year,
                    b.raw_spec_transmission, s.vehicle_transmission,
                    b.raw_spec_fuel_type, s.vehicle_fuel_type
                FROM silver_latest s
                JOIN bronze_latest b ON s.listing_id = b.listing_id AND b._rn = 1
                WHERE s._rn = 1
            )
            SELECT
                'Brand' AS attribute,
                ROUND(100.0 * COUNT(raw_spec_brand) / NULLIF(COUNT(*), 0), 1) AS raw_bronze_fill_pct,
                ROUND(100.0 * COUNT(vehicle_brand) / NULLIF(COUNT(*), 0), 1) AS conformed_silver_fill_pct
            FROM joined
            UNION ALL
            SELECT
                'Model',
                ROUND(100.0 * COUNT(raw_spec_model) / NULLIF(COUNT(*), 0), 1),
                ROUND(100.0 * COUNT(vehicle_model) / NULLIF(COUNT(*), 0), 1)
            FROM joined
            UNION ALL
            SELECT
                'Year',
                ROUND(100.0 * COUNT(raw_spec_year) / NULLIF(COUNT(*), 0), 1),
                ROUND(100.0 * COUNT(vehicle_year) / NULLIF(COUNT(*), 0), 1)
            FROM joined
            UNION ALL
            SELECT
                'Transmission',
                ROUND(100.0 * COUNT(raw_spec_transmission) / NULLIF(COUNT(*), 0), 1),
                ROUND(100.0 * COUNT(vehicle_transmission) / NULLIF(COUNT(*), 0), 1)
            FROM joined
            UNION ALL
            SELECT
                'Fuel Type',
                ROUND(100.0 * COUNT(raw_spec_fuel_type) / NULLIF(COUNT(*), 0), 1),
                ROUND(100.0 * COUNT(vehicle_fuel_type) / NULLIF(COUNT(*), 0), 1)
            FROM joined
        """).df()
        df["uplift_pct"] = (df["conformed_silver_fill_pct"] - df["raw_bronze_fill_pct"]).round(1)
    except Exception:
        df = pd.DataFrame()
    finally:
        con.close()

    return df


@st.cache_data(ttl=CACHE_TTL)
def load_cleaning_rules_summary() -> pd.DataFrame:
    """
    Returns a structured summary table explaining the dbt cleaning rules and transformations.
    """
    rules = [
        {
            "attribute": "vehicle_brand",
            "transformation": "Seed Mapping + Khmer Title Regex + Placeholder Exclusion",
            "logic": "Maps 68+ multilingual variants to 32 canonical brands. Converts 'ផ្សេងៗ', 'Other', 'Others' to NULL.",
            "conformance_rule": "Enforces automotive brand catalog standard; drops unknown placeholders."
        },
        {
            "attribute": "vehicle_model",
            "transformation": "Seed Alias Dictionary + Regex NLP from Khmer/English Titles",
            "logic": "Recovers 137+ models from free-text titles when seller left dropdown blank or selected 'ផ្សេងៗ'.",
            "conformance_rule": "Conforms 417 models with standardized spelling."
        },
        {
            "attribute": "vehicle_year",
            "transformation": "Evidence-Based Chronological Inversion Healing",
            "logic": "Detects 2026/2027 entries on older Gen 2 models (Prius, RX330) and heals to 2006/2007.",
            "conformance_rule": "Preserves valid modern 2026+ cars (AVATR 07, Grand Highlander); heals fat-finger inversions."
        },
        {
            "attribute": "vehicle_mileage_km",
            "transformation": "Multi-Source NLP + Warranty Disentanglement + Miles Conversion",
            "logic": "Parses មុឺន/ម៉ឺន/miles; converts to KM. Strips factory warranty text (e.g. 10ម៉ឺនគីឡូ) to prevent false odometer matches.",
            "conformance_rule": "Clamped to valid physical range [0 - 500,000 km]; missingness signaled via binary flag."
        },
        {
            "attribute": "vehicle_engine_cc",
            "transformation": "EV Zero-Displacement + Litre-to-CC Normalization",
            "logic": "Sets 0 cc for pure BEVs (Tesla, Zeekr, NIO); parses 1.5L combustion engines for BYD DM-i hybrids.",
            "conformance_rule": "Clamped to [500 - 7,000 cc] (or 0 for EV)."
        },
        {
            "attribute": "price",
            "transformation": "Down-Payment Defense + Typo Outlier Detection",
            "logic": "Flags listings < $500 as invalid. Identifies down-payment loan traps ($500-$3,000) and extra-zero typos.",
            "conformance_rule": "Guarantees Gold ML training target integrity (price >= $500, no scams)."
        },
    ]
    return pd.DataFrame(rules)

