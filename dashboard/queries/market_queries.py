"""
dashboard/queries/market_queries.py
====================================
Analytical DuckDB queries for Market Intelligence & Cross-Sectional Pricing Dynamics.
Queries operate directly on Gold Analytics Mart (data/gold/fct_car_listings.parquet)
and Silver Conformed (data/silver/cars_cleaned.parquet).

Methodological Notes:
  - All aggregations enforce sample size (N >= 30) gating on vintage curves to prevent outlier distortion.
  - Price metrics prioritize Median and IQR (P25-P75) over arithmetic mean due to right-skewed price distributions.
  - Cross-sectional listings represent vintage price spreads across current listings, not longitudinal depreciation.
"""

from __future__ import annotations

import os
import pandas as pd
import streamlit as st

from dashboard.queries.base import (
    _con,
    CACHE_TTL,
    GOLD_MART_PATH,
    SILVER_PATH,
)


@st.cache_data(ttl=CACHE_TTL)
def load_market_kpis(scrape_date: str | None = None) -> dict:
    """
    Computes high-level Cambodian market KPIs from Gold/Silver listings.
    """
    target_path = GOLD_MART_PATH if os.path.exists(GOLD_MART_PATH) else SILVER_PATH
    if not os.path.exists(target_path):
        return {}

    date_filter = f"WHERE CAST(scrape_date AS VARCHAR) = '{scrape_date}'" if scrape_date else ""

    con = _con()
    try:
        query = f"""
            WITH base AS (
                SELECT
                    price,
                    vehicle_brand,
                    vehicle_model,
                    vehicle_year,
                    vehicle_tax_type,
                    vehicle_fuel_type,
                    province
                FROM read_parquet('{target_path}')
                {date_filter}
            )
            SELECT
                COUNT(*)                                                            AS total_listings,
                ROUND(MEDIAN(price), 0)                                            AS median_price,
                ROUND(AVG(price), 0)                                               AS mean_price,
                ROUND(QUANTILE_CONT(price, 0.25), 0)                               AS p25_price,
                ROUND(QUANTILE_CONT(price, 0.75), 0)                               AS p75_price,
                COUNT(DISTINCT vehicle_brand)                                      AS distinct_brands,
                COUNT(DISTINCT vehicle_model)                                      AS distinct_models,
                -- Tax paper vs Plate median
                ROUND(MEDIAN(CASE WHEN vehicle_tax_type ILIKE '%tax%' THEN price END), 0) AS median_tax_paper,
                ROUND(MEDIAN(CASE WHEN vehicle_tax_type ILIKE '%plate%' THEN price END), 0) AS median_plate,
                -- Top Brand
                MODE(vehicle_brand)                                                AS top_brand,
                -- Hybrid share
                ROUND(100.0 * COUNT(*) FILTER (WHERE vehicle_fuel_type ILIKE '%hybrid%') / NULLIF(COUNT(*), 0), 1) AS hybrid_share_pct
            FROM base
            WHERE price > 500 AND price < 300000
        """
        row = con.execute(query).df().iloc[0].to_dict()
        return row
    except Exception:
        return {}
    finally:
        con.close()


@st.cache_data(ttl=CACHE_TTL)
def load_vintage_price_curves(min_model_samples: int = 30, scrape_date: str | None = None) -> pd.DataFrame:
    """
    Computes cross-sectional median price and IQR (P25-P75) by model and year.
    Only models with at least `min_model_samples` total listings are included.
    """
    target_path = GOLD_MART_PATH if os.path.exists(GOLD_MART_PATH) else SILVER_PATH
    if not os.path.exists(target_path):
        return pd.DataFrame()

    date_filter = f"AND CAST(scrape_date AS VARCHAR) = '{scrape_date}'" if scrape_date else ""

    con = _con()
    try:
        query = f"""
            WITH qualified_models AS (
                SELECT
                    vehicle_brand,
                    vehicle_model,
                    COUNT(*) AS model_total_count
                FROM read_parquet('{target_path}')
                WHERE price >= 500 AND price <= 300000
                  AND vehicle_year >= 1995 AND vehicle_year <= 2026
                  AND vehicle_model IS NOT NULL AND vehicle_model != ''
                  {date_filter}
                GROUP BY vehicle_brand, vehicle_model
                HAVING COUNT(*) >= {min_model_samples}
            ),
            model_year_stats AS (
                SELECT
                    t.vehicle_brand,
                    t.vehicle_model,
                    CONCAT(t.vehicle_brand, ' ', t.vehicle_model)                   AS full_model_name,
                    q.model_total_count,
                    t.vehicle_year,
                    COUNT(*)                                                        AS sample_size,
                    ROUND(MEDIAN(t.price), 0)                                       AS median_price,
                    ROUND(AVG(t.price), 0)                                          AS mean_price,
                    ROUND(QUANTILE_CONT(t.price, 0.25), 0)                          AS p25_price,
                    ROUND(QUANTILE_CONT(t.price, 0.75), 0)                          AS p75_price,
                    ROUND(MIN(t.price), 0)                                          AS min_price,
                    ROUND(MAX(t.price), 0)                                          AS max_price
                FROM read_parquet('{target_path}') t
                JOIN qualified_models q
                  ON t.vehicle_brand = q.vehicle_brand AND t.vehicle_model = q.vehicle_model
                WHERE t.price >= 500 AND t.price <= 300000
                  AND t.vehicle_year >= 1995 AND t.vehicle_year <= 2026
                  {date_filter}
                GROUP BY t.vehicle_brand, t.vehicle_model, q.model_total_count, t.vehicle_year
                HAVING COUNT(*) >= 3
            )
            SELECT *
            FROM model_year_stats
            ORDER BY model_total_count DESC, full_model_name, vehicle_year ASC
        """
        df = con.execute(query).df()
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()


@st.cache_data(ttl=CACHE_TTL)
def load_regional_pricing(scrape_date: str | None = None) -> pd.DataFrame:
    """
    Computes listing volume and median price by province, grouping small provinces (N < 20) into 'Other Provinces'.
    """
    target_path = GOLD_MART_PATH if os.path.exists(GOLD_MART_PATH) else SILVER_PATH
    if not os.path.exists(target_path):
        return pd.DataFrame()

    date_filter = f"AND CAST(scrape_date AS VARCHAR) = '{scrape_date}'" if scrape_date else ""

    con = _con()
    try:
        query = f"""
            WITH raw_prov AS (
                SELECT
                    COALESCE(NULLIF(province, ''), 'Unknown')                       AS province_clean,
                    price
                FROM read_parquet('{target_path}')
                WHERE price >= 500 AND price <= 300000
                  {date_filter}
            ),
            prov_grouped AS (
                SELECT
                    province_clean,
                    COUNT(*)                                                        AS count,
                    ROUND(MEDIAN(price), 0)                                         AS median_price,
                    ROUND(AVG(price), 0)                                            AS mean_price,
                    ROUND(QUANTILE_CONT(price, 0.25), 0)                            AS p25_price,
                    ROUND(QUANTILE_CONT(price, 0.75), 0)                            AS p75_price
                FROM raw_prov
                GROUP BY province_clean
            ),
            total_cnt AS (
                SELECT SUM(count) AS grand_total FROM prov_grouped
            )
            SELECT
                CASE WHEN p.count >= 20 THEN p.province_clean ELSE 'Other Provinces (N < 20)' END AS province,
                SUM(p.count)                                                        AS sample_size,
                ROUND(100.0 * SUM(p.count) / t.grand_total, 1)                      AS share_pct,
                ROUND(AVG(p.median_price), 0)                                       AS median_price,
                ROUND(AVG(p.p25_price), 0)                                          AS p25_price,
                ROUND(AVG(p.p75_price), 0)                                          AS p75_price
            FROM prov_grouped p, total_cnt t
            GROUP BY CASE WHEN p.count >= 20 THEN p.province_clean ELSE 'Other Provinces (N < 20)' END, t.grand_total
            ORDER BY sample_size DESC
        """
        df = con.execute(query).df()
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()


@st.cache_data(ttl=CACHE_TTL)
def load_tax_type_comparison(scrape_date: str | None = None) -> pd.DataFrame:
    """
    Compares Tax Paper (Fresh Import) vs Plate Number (Registered) prices across top models.
    """
    target_path = GOLD_MART_PATH if os.path.exists(GOLD_MART_PATH) else SILVER_PATH
    if not os.path.exists(target_path):
        return pd.DataFrame()

    date_filter = f"AND CAST(scrape_date AS VARCHAR) = '{scrape_date}'" if scrape_date else ""

    con = _con()
    try:
        query = f"""
            WITH model_tax_counts AS (
                SELECT 
                    vehicle_model,
                    COUNT(*) FILTER (WHERE vehicle_tax_type ILIKE '%tax%') AS tax_cnt,
                    COUNT(*) FILTER (WHERE vehicle_tax_type ILIKE '%plate%') AS plate_cnt,
                    COUNT(*) AS total_cnt
                FROM read_parquet('{target_path}')
                WHERE price >= 500 AND price <= 300000
                  AND vehicle_model IS NOT NULL AND vehicle_model != ''
                  {date_filter}
                GROUP BY vehicle_model
                HAVING COUNT(*) >= 20
                   AND COUNT(*) FILTER (WHERE vehicle_tax_type ILIKE '%tax%') >= 3
                   AND COUNT(*) FILTER (WHERE vehicle_tax_type ILIKE '%plate%') >= 3
            )
            SELECT
                t.vehicle_model,
                CASE 
                    WHEN t.vehicle_tax_type ILIKE '%tax%' THEN 'Tax Paper (Fresh Import)'
                    ELSE 'Plate Number (Registered)'
                END                                                                 AS tax_status,
                COUNT(*)                                                            AS sample_size,
                ROUND(MEDIAN(t.price), 0)                                           AS median_price,
                ROUND(QUANTILE_CONT(t.price, 0.25), 0)                              AS p25_price,
                ROUND(QUANTILE_CONT(t.price, 0.75), 0)                              AS p75_price
            FROM read_parquet('{target_path}') t
            JOIN model_tax_counts mc ON t.vehicle_model = mc.vehicle_model
            WHERE t.vehicle_tax_type IS NOT NULL AND t.vehicle_tax_type != ''
              AND t.price >= 500 AND t.price <= 300000
              {date_filter}
            GROUP BY t.vehicle_model, tax_status, mc.total_cnt
            ORDER BY mc.total_cnt DESC, t.vehicle_model, tax_status
        """
        df = con.execute(query).df()
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()


@st.cache_data(ttl=CACHE_TTL)
def load_market_share_breakdown(scrape_date: str | None = None) -> dict[str, pd.DataFrame]:
    """
    Returns market breakdown by Brand, Body Type, and Fuel Type with sample sizes.
    """
    target_path = GOLD_MART_PATH if os.path.exists(GOLD_MART_PATH) else SILVER_PATH
    if not os.path.exists(target_path):
        return {}

    date_filter = f"WHERE price >= 500 AND price <= 300000 " + (f"AND CAST(scrape_date AS VARCHAR) = '{scrape_date}'" if scrape_date else "")

    con = _con()
    try:
        # 1. Brands
        brands_df = con.execute(f"""
            SELECT
                COALESCE(NULLIF(vehicle_brand, ''), 'Unknown') AS brand,
                COUNT(*) AS count,
                ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM read_parquet('{target_path}') {date_filter}), 1) AS share_pct,
                ROUND(MEDIAN(price), 0) AS median_price
            FROM read_parquet('{target_path}')
            {date_filter}
            GROUP BY brand
            ORDER BY count DESC
            LIMIT 12
        """).df()

        # 2. Body Types
        body_df = con.execute(f"""
            SELECT
                COALESCE(NULLIF(vehicle_body_type, ''), 'Unspecified') AS body_type,
                COUNT(*) AS count,
                ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM read_parquet('{target_path}') {date_filter}), 1) AS share_pct,
                ROUND(MEDIAN(price), 0) AS median_price
            FROM read_parquet('{target_path}')
            {date_filter}
            GROUP BY body_type
            ORDER BY count DESC
        """).df()

        # 3. Fuel Types
        fuel_df = con.execute(f"""
            SELECT
                COALESCE(NULLIF(vehicle_fuel_type, ''), 'Unspecified') AS fuel_type,
                COUNT(*) AS count,
                ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM read_parquet('{target_path}') {date_filter}), 1) AS share_pct,
                ROUND(MEDIAN(price), 0) AS median_price
            FROM read_parquet('{target_path}')
            {date_filter}
            GROUP BY fuel_type
            ORDER BY count DESC
        """).df()

        return {
            "brands": brands_df,
            "body_types": body_df,
            "fuels": fuel_df,
        }
    except Exception:
        return {}
    finally:
        con.close()
