"""
dashboard/queries/quality_queries.py
====================================
Data Health Index (DHI), quality tier waterfall, reason codes, and anomaly audits.
"""
from __future__ import annotations

import os
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
def load_quality_summary() -> pd.DataFrame:
    """
    Returns one row per scrape_date with counts for each quality tier and calibrated DHI.
    Columns: scrape_date, total, valid, warning, suspicious, invalid, quarantined, dhi
    """
    if not os.path.exists(SILVER_PATH):
        return pd.DataFrame()

    con = _con()
    w_q = config.DHI_WEIGHTS.get("quarantined", 1.0)
    w_i = config.DHI_WEIGHTS.get("invalid", 0.7)
    w_s = config.DHI_WEIGHTS.get("suspicious", 0.3)
    w_w = config.DHI_WEIGHTS.get("warning", 0.03)

    try:
        df = con.execute(f"""
            SELECT
                CAST(scrape_date AS VARCHAR)                                    AS scrape_date,
                COUNT(*)                                                        AS total,
                COUNT(*) FILTER (WHERE data_quality_status = 'VALID')          AS valid,
                COUNT(*) FILTER (WHERE data_quality_status = 'WARNING')        AS warning,
                COUNT(*) FILTER (WHERE data_quality_status = 'SUSPICIOUS')     AS suspicious,
                COUNT(*) FILTER (WHERE data_quality_status = 'INVALID')        AS invalid,
                COUNT(*) FILTER (WHERE data_quality_status = 'QUARANTINED')    AS quarantined,

                -- Data Health Index: calibrated domain penalty score
                ROUND(
                    GREATEST(0.0,
                        100.0
                        - (100.0 * COUNT(*) FILTER (WHERE data_quality_status = 'QUARANTINED') / NULLIF(COUNT(*), 0)) * {w_q}
                        - (100.0 * COUNT(*) FILTER (WHERE data_quality_status = 'INVALID')     / NULLIF(COUNT(*), 0)) * {w_i}
                        - (100.0 * COUNT(*) FILTER (WHERE data_quality_status = 'SUSPICIOUS')  / NULLIF(COUNT(*), 0)) * {w_s}
                        - (100.0 * COUNT(*) FILTER (WHERE data_quality_status = 'WARNING')     / NULLIF(COUNT(*), 0)) * {w_w}
                    )
                , 2)                                                            AS dhi

            FROM read_parquet('{SILVER_PATH}')
            GROUP BY scrape_date
            ORDER BY scrape_date DESC
        """).df()
    except Exception:
        df = pd.DataFrame()
    finally:
        con.close()

    return df


@st.cache_data(ttl=CACHE_TTL)
def load_top_reasons(top_n: int = 12, scrape_date: str | None = None) -> pd.DataFrame:
    """
    Explodes the pipe-delimited data_quality_reasons column and
    returns the top-N failure reason codes by frequency.
    """
    if not os.path.exists(SILVER_PATH):
        return pd.DataFrame()

    date_filter = (
        f"AND CAST(scrape_date AS VARCHAR) = '{scrape_date}'"
        if scrape_date
        else ""
    )

    con = _con()
    try:
        df = con.execute(f"""
            WITH reasons AS (
                SELECT TRIM(UNNEST(STRING_SPLIT(data_quality_reasons, '|'))) AS reason
                FROM read_parquet('{SILVER_PATH}')
                WHERE data_quality_reasons IS NOT NULL AND data_quality_reasons != ''
                {date_filter}
            )
            SELECT reason, COUNT(*) AS count
            FROM reasons
            WHERE reason != ''
            GROUP BY reason
            ORDER BY count DESC
            LIMIT {top_n}
        """).df()
    except Exception:
        df = pd.DataFrame()
    finally:
        con.close()

    return df


@st.cache_data(ttl=CACHE_TTL)
def load_audit_sample(
    statuses: list[str] | None = None,
    reason_filter: str = "",
    scrape_date: str | None = None,
    limit: int = 200,
) -> pd.DataFrame:
    """
    Returns a side-by-side audit table joining Silver conformed records with
    Bronze raw inputs (mirrors int_cars_audit_lineage) for deep root cause debugging.
    """
    if not os.path.exists(SILVER_PATH):
        return pd.DataFrame()

    where_conds = []
    if statuses:
        valid_statuses = [s.strip().upper() for s in statuses if s and s.strip().upper() != "ALL"]
        if valid_statuses:
            status_list = ", ".join(f"'{s}'" for s in valid_statuses)
            where_conds.append(f"s.data_quality_status IN ({status_list})")
    else:
        where_conds.append("s.data_quality_status IN ('QUARANTINED', 'INVALID', 'SUSPICIOUS')")

    if reason_filter and reason_filter.strip() and reason_filter.strip().upper() != "ALL":
        rf = reason_filter.strip().replace("'", "''")
        where_conds.append(f"s.data_quality_reasons ILIKE '%{rf}%'")

    if scrape_date and scrape_date.strip() and scrape_date.strip().upper() != "ALL":
        where_conds.append(f"CAST(s.scrape_date AS VARCHAR) = '{scrape_date.strip()}'")

    where_clause = ("WHERE " + " AND ".join(where_conds)) if where_conds else ""

    con = _con()
    has_bronze = len(list(_BRONZE_DIR.glob("cars_*.parquet"))) > 0

    try:
        if has_bronze:
            df = con.execute(f"""
                WITH silver_sample AS (
                    SELECT
                        s.listing_id,
                        CAST(s.scrape_date AS VARCHAR)      AS scrape_date,
                        s.data_quality_status               AS status,
                        s.data_quality_reasons              AS reasons,
                        s.vehicle_brand                     AS clean_brand,
                        s.vehicle_model                     AS clean_model,
                        s.vehicle_year                      AS clean_year,
                        ROUND(s.price, 0)                   AS clean_price,
                        s.province                          AS clean_province,
                        s.model_extraction_method,
                        s.is_year_healed,
                        s.is_spam,
                        s.is_down_payment,
                        s.is_price_outlier,
                        s.outlier_method,
                        s.price_lower_fence,
                        s.price_upper_fence,
                        s.title_clean,
                        s.listing_url
                    FROM read_parquet('{SILVER_PATH}') s
                    {where_clause}
                    ORDER BY s.scrape_date DESC, s.data_quality_status
                    LIMIT {limit}
                ),
                bronze_latest AS (
                    SELECT
                        listing_id,
                        raw_title,
                        raw_price,
                        raw_spec_brand,
                        raw_spec_model,
                        raw_spec_year,
                        ROW_NUMBER() OVER (PARTITION BY listing_id ORDER BY scraped_at DESC) AS _rn
                    FROM read_parquet('{BRONZE_GLOB}', union_by_name=true)
                    WHERE listing_id IN (SELECT listing_id FROM silver_sample)
                )
                SELECT
                    s.listing_id,
                    s.scrape_date,
                    s.status,
                    s.reasons,
                    -- Side-by-side Brand
                    b.raw_spec_brand                        AS raw_brand,
                    s.clean_brand,
                    -- Side-by-side Model
                    b.raw_spec_model                        AS raw_model,
                    s.clean_model,
                    s.model_extraction_method,
                    -- Side-by-side Year
                    b.raw_spec_year                         AS raw_year,
                    s.clean_year,
                    s.is_year_healed,
                    -- Side-by-side Price
                    b.raw_price,
                    s.clean_price,
                    -- Dynamic Outlier Fences
                    s.outlier_method,
                    s.price_lower_fence,
                    s.price_upper_fence,
                    -- Side-by-side Title
                    b.raw_title,
                    s.title_clean,
                    -- Details
                    s.clean_province,
                    s.is_spam,
                    s.is_down_payment,
                    s.is_price_outlier,
                    s.listing_url
                FROM silver_sample s
                LEFT JOIN bronze_latest b
                  ON s.listing_id = b.listing_id AND b._rn = 1
                ORDER BY s.scrape_date DESC, s.status
            """).df()
        else:
            df = con.execute(f"""
                SELECT
                    s.listing_id,
                    CAST(s.scrape_date AS VARCHAR)          AS scrape_date,
                    s.data_quality_status                   AS status,
                    s.data_quality_reasons                  AS reasons,
                    CAST(NULL AS VARCHAR)                   AS raw_brand,
                    s.vehicle_brand                         AS clean_brand,
                    CAST(NULL AS VARCHAR)                   AS raw_model,
                    s.vehicle_model                         AS clean_model,
                    s.model_extraction_method,
                    CAST(NULL AS VARCHAR)                   AS raw_year,
                    s.vehicle_year                          AS clean_year,
                    s.is_year_healed,
                    CAST(NULL AS VARCHAR)                   AS raw_price,
                    ROUND(s.price, 0)                       AS clean_price,
                    s.outlier_method,
                    s.price_lower_fence,
                    s.price_upper_fence,
                    CAST(NULL AS VARCHAR)                   AS raw_title,
                    s.title_clean,
                    s.province                              AS clean_province,
                    s.is_spam,
                    s.is_down_payment,
                    s.is_price_outlier,
                    s.listing_url
                FROM read_parquet('{SILVER_PATH}') s
                {where_clause}
                ORDER BY s.scrape_date DESC, s.data_quality_status
                LIMIT {limit}
            """).df()
    except Exception:
        df = pd.DataFrame()
    finally:
        con.close()

    return df


@st.cache_data(ttl=CACHE_TTL)
def load_price_year_anomaly_sample(limit: int = 2500, scrape_date: str | None = None) -> pd.DataFrame:
    """
    Returns sampled listings with anomaly indicators for interactive scatter plot.
    """
    if not os.path.exists(SILVER_PATH):
        return pd.DataFrame()

    where_parts = ["price IS NOT NULL", "vehicle_year IS NOT NULL"]
    if scrape_date:
        where_parts.append(f"CAST(scrape_date AS VARCHAR) = '{scrape_date}'")
    where_sql = "WHERE " + " AND ".join(where_parts)

    con = _con()
    try:
        df = con.execute(f"""
            SELECT
                listing_id,
                vehicle_year,
                price,
                vehicle_brand,
                vehicle_model,
                province,
                data_quality_status,
                is_down_payment,
                is_price_outlier,
                data_quality_reasons,
                CASE
                    WHEN is_down_payment = 1 THEN 'Down Payment Trap'
                    WHEN data_quality_reasons LIKE '%STATISTICAL_OUTLIER_LOW%' THEN 'IQR Outlier (Low / Scam)'
                    WHEN data_quality_reasons LIKE '%STATISTICAL_OUTLIER_HIGH%' THEN 'IQR Outlier (High)'
                    WHEN data_quality_reasons LIKE '%HEURISTIC_PRICE_OUTLIER%' THEN 'Heuristic Outlier'
                    WHEN is_price_outlier = 1 THEN 'Price Outlier'
                    WHEN vehicle_year < 1990 OR vehicle_year > (CAST(date_part('year', CURRENT_DATE) AS INTEGER) + 1) THEN 'Invalid Year'
                    WHEN price < 500 THEN 'Price Below $500'
                    WHEN data_quality_status = 'VALID' THEN 'Normal (Valid)'
                    ELSE 'Warning Spec'
                END AS anomaly_group
            FROM read_parquet('{SILVER_PATH}')
            {where_sql}
            ORDER BY RANDOM()
            LIMIT {limit}
        """).df()
    except Exception:
        df = pd.DataFrame()
    finally:
        con.close()

    return df

