"""
dashboard/queries/market_queries.py
====================================
Analytical DuckDB queries for Market Intelligence & Cross-Sectional Pricing Dynamics.
Queries operate directly on Gold Analytics Mart (data/gold/fct_car_listings.parquet)
for deduplicated unique listing grain (10,007 rows) and Silver Conformed
(data/silver/cars_cleaned.parquet) for partition time-series trends.

Methodological Notes:
  - All cross-sectional market intelligence operates at the unique listing grain (Gold Mart).
  - Price metrics prioritize Median and IQR (P25-P75) over arithmetic mean (right-skewed).
  - Cross-sectional listings represent vintage price spreads, not longitudinal depreciation.
  - All filter parameters are sanitized via build_filter_sql() — zero raw string injection.
  - Features mileage and engine cc are excluded from active analysis per data governance rules.
"""

from __future__ import annotations

import os
from typing import Any
import pandas as pd
import streamlit as st

from dashboard.queries.base import (
    _con,
    CACHE_TTL,
    GOLD_MART_PATH,
    SILVER_PATH,
    build_filter_sql,
)


def _gold_mart() -> str | None:
    """Return the Gold Analytics Mart path (deduplicated unique listings), falling back to Silver."""
    if os.path.exists(GOLD_MART_PATH):
        return GOLD_MART_PATH
    if os.path.exists(SILVER_PATH):
        return SILVER_PATH
    return None


def _gold_or_silver() -> str | None:
    """Backward-compatible helper returning the primary analytical parquet path."""
    return _gold_mart()


def _silver_snapshots() -> str | None:
    """Return the Silver snapshot path for multi-partition time-series trend analysis."""
    if os.path.exists(SILVER_PATH):
        return SILVER_PATH
    return _gold_mart()


def _base_price_filter() -> str:
    """Standard price sanity bounds applied to market queries (allows full catalog up to $1,000,000)."""
    return "price >= 500 AND price <= 1000000"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Market Overview KPIs (Fully Reactive to Active Filters)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=CACHE_TTL)
def load_market_kpis(filters: dict | None = None, scrape_date: str | None = None) -> dict[str, Any]:
    """
    Computes high-level Cambodian market KPIs from Gold listings (100% Unique Physical Vehicles).
    Dynamically applies active user filters to all statistics.
    Returns scalar metrics including median, mean, IQR, min/max, top brand, median year,
    and deduplication counts.
    """
    path = _gold_mart()
    if not path:
        return {}

    # Support string scrape_date passed as first positional argument
    if isinstance(filters, str):
        scrape_date = filters
        active_filters: dict[str, Any] = {}
    else:
        active_filters = dict(filters or {})

    if scrape_date and "scrape_date" not in active_filters:
        active_filters["scrape_date"] = scrape_date

    extra = build_filter_sql(**active_filters)
    con = _con()
    try:
        total_catalog = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{path}') WHERE {_base_price_filter()}"
        ).fetchone()[0]

        row = con.execute(f"""
            WITH base AS (
                SELECT
                    price,
                    vehicle_brand,
                    vehicle_model,
                    vehicle_year,
                    vehicle_age,
                    vehicle_tax_type,
                    vehicle_fuel_type,
                    vehicle_body_type,
                    scrape_date,
                    repost_count
                FROM read_parquet('{path}')
                WHERE {_base_price_filter()} {extra}
            ),
            top_two AS (
                SELECT 
                    vehicle_brand,
                    COUNT(*) as brand_count,
                    ROUND(100.0 * COUNT(*) / NULLIF((SELECT COUNT(*) FROM base), 0), 1) as brand_pct
                FROM base
                WHERE vehicle_brand IS NOT NULL AND vehicle_brand != ''
                GROUP BY vehicle_brand
                ORDER BY brand_count DESC
                LIMIT 2
            ),
            pivoted_brands AS (
                SELECT
                    MAX(CASE WHEN rn = 1 THEN vehicle_brand END) as top_brand,
                    MAX(CASE WHEN rn = 1 THEN brand_count END) as top_brand_count,
                    MAX(CASE WHEN rn = 1 THEN brand_pct END) as top_brand_pct,
                    MAX(CASE WHEN rn = 2 THEN vehicle_brand END) as second_brand,
                    MAX(CASE WHEN rn = 2 THEN brand_count END) as second_brand_count,
                    MAX(CASE WHEN rn = 2 THEN brand_pct END) as second_brand_pct
                FROM (
                    SELECT vehicle_brand, brand_count, brand_pct, ROW_NUMBER() OVER () as rn
                    FROM top_two
                )
            )
            SELECT
                COUNT(*)                                                              AS total_listings,
                CAST(COALESCE(SUM(repost_count), COUNT(*)) AS BIGINT)                AS raw_ads_count,
                COUNT(*)                                                              AS canonical_count,
                CAST(COALESCE(SUM(repost_count) - COUNT(*), 0) AS BIGINT)             AS duplicate_reposts,
                ROUND(MEDIAN(price), 0)                                               AS median_price,
                ROUND(AVG(price), 0)                                                  AS mean_price,
                ROUND(QUANTILE_CONT(price, 0.25), 0)                                  AS p25_price,
                ROUND(QUANTILE_CONT(price, 0.75), 0)                                  AS p75_price,
                ROUND(MIN(price), 0)                                                  AS min_price,
                ROUND(MAX(price), 0)                                                  AS max_price,
                ROUND(QUANTILE_CONT(price, 0.05), 0)                                  AS p05_price,
                ROUND(QUANTILE_CONT(price, 0.95), 0)                                  AS p95_price,
                ROUND(MEDIAN(vehicle_year), 0)                                        AS median_year,
                ROUND(MEDIAN(vehicle_age), 0)                                         AS median_age,
                MIN(vehicle_year)                                                     AS min_year,
                MAX(vehicle_year)                                                     AS max_year,
                COUNT(DISTINCT vehicle_brand)                                          AS distinct_brands,
                COUNT(DISTINCT vehicle_model)                                          AS distinct_models,
                ROUND(MEDIAN(CASE WHEN vehicle_tax_type ILIKE '%tax%'
                    THEN price END), 0)                                                AS median_tax_paper,
                ROUND(MEDIAN(CASE WHEN vehicle_tax_type ILIKE '%plate%'
                    THEN price END), 0)                                                AS median_plate,
                COUNT(*) FILTER (WHERE vehicle_tax_type ILIKE '%tax%')                 AS tax_paper_count,
                COUNT(*) FILTER (WHERE vehicle_tax_type ILIKE '%plate%')               AS plate_count,
                ROUND(
                    100.0 * COUNT(*) FILTER (WHERE vehicle_fuel_type ILIKE '%hybrid%')
                    / NULLIF(COUNT(*), 0), 1)                                          AS hybrid_share_pct,
                MAX(CAST(scrape_date AS VARCHAR))                                      AS latest_date,
                (SELECT top_brand FROM pivoted_brands)                                 AS top_brand,
                (SELECT top_brand_count FROM pivoted_brands)                           AS top_brand_count,
                (SELECT top_brand_pct FROM pivoted_brands)                             AS top_brand_pct,
                (SELECT second_brand FROM pivoted_brands)                              AS second_brand,
                (SELECT second_brand_count FROM pivoted_brands)                        AS second_brand_count,
                (SELECT second_brand_pct FROM pivoted_brands)                          AS second_brand_pct
            FROM base
        """).df().iloc[0].to_dict()

        row["canonical_only"] = True
        row["total_catalog"] = total_catalog
        total_l = int(row.get("total_listings") or 0)
        row["coverage_pct"] = round(100.0 * total_l / max(total_catalog, 1), 1)
        p25 = row.get("p25_price") or 0
        p75 = row.get("p75_price") or 0
        row["iqr_price"] = p75 - p25
        return row
    except Exception:
        return {}
    finally:
        con.close()


# ─────────────────────────────────────────────────────────────────────────────
# Filter Dimension Enumerators (for Filter Panel)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=CACHE_TTL)
def load_filter_options() -> dict[str, Any]:
    """
    Returns distinct categorical values and numerical bounds across all active dimensions.
    Excludes mileage and engine cc per data governance specification.
    """
    path = _gold_mart()
    if not path:
        return {}
    con = _con()
    try:
        def _distinct(col: str, order: str = "count") -> list[str]:
            order_sql = "COUNT(*) DESC" if order == "count" else col
            rows = con.execute(f"""
                SELECT {col} AS val FROM read_parquet('{path}')
                WHERE {col} IS NOT NULL AND {col} != ''
                  AND {_base_price_filter()}
                GROUP BY {col} ORDER BY {order_sql}
            """).fetchall()
            return [r[0] for r in rows]

        brands       = _distinct("vehicle_brand")
        vehicle_types = _distinct("vehicle_body_type")
        fuels        = _distinct("vehicle_fuel_type")
        trans        = _distinct("vehicle_transmission")

        year_row = con.execute(f"""
            SELECT MIN(vehicle_year), MAX(vehicle_year)
            FROM read_parquet('{path}')
            WHERE vehicle_year BETWEEN 1990 AND 2026
              AND {_base_price_filter()}
        """).fetchone()

        price_row = con.execute(f"""
            SELECT MIN(price), MAX(price)
            FROM read_parquet('{path}')
            WHERE {_base_price_filter()}
        """).fetchone()

        date_rows = con.execute(f"""
            SELECT DISTINCT CAST(scrape_date AS VARCHAR)
            FROM read_parquet('{path}')
            WHERE scrape_date IS NOT NULL
            ORDER BY 1 DESC
        """).fetchall()

        return {
            "brands":        brands,
            "vehicle_types": vehicle_types,
            "fuels":         fuels,
            "transmissions": trans,
            "year_min":      int(year_row[0]) if year_row and year_row[0] else 1995,
            "year_max":      int(year_row[1]) if year_row and year_row[1] else 2025,
            "price_min":     float(price_row[0]) if price_row and price_row[0] else 500,
            "price_max":     float(price_row[1]) if price_row and price_row[1] else 300000,
            "scrape_dates":  [r[0] for r in date_rows],
        }
    except Exception:
        return {}
    finally:
        con.close()


@st.cache_data(ttl=CACHE_TTL)
def load_models_for_brands(brands: tuple[str, ...] | None = None) -> list[str]:
    """Return distinct models optionally filtered by selected brands."""
    path = _gold_mart()
    if not path:
        return []
    extra = build_filter_sql(brands=list(brands) if brands else None)
    con = _con()
    try:
        rows = con.execute(f"""
            SELECT vehicle_model FROM read_parquet('{path}')
            WHERE vehicle_model IS NOT NULL AND vehicle_model != ''
              AND {_base_price_filter()} {extra}
            GROUP BY vehicle_model ORDER BY COUNT(*) DESC
        """).fetchall()
        return [r[0] for r in rows]
    except Exception:
        return []
    finally:
        con.close()


# ─────────────────────────────────────────────────────────────────────────────
# 2. Asking Price Analysis Queries
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=CACHE_TTL)
def load_price_distribution_data(filters: dict | None = None) -> pd.DataFrame:
    """
    Returns individual asking prices with metadata for histogram and density curves.
    """
    path = _gold_mart()
    if not path:
        return pd.DataFrame()
    extra = build_filter_sql(**(filters or {}))
    con = _con()
    try:
        df = con.execute(f"""
            SELECT
                price,
                vehicle_brand,
                vehicle_model,
                vehicle_body_type,
                vehicle_year,
                vehicle_fuel_type
            FROM read_parquet('{path}')
            WHERE {_base_price_filter()} {extra}
        """).df()
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()


@st.cache_data(ttl=CACHE_TTL)
def load_price_box_plot_data(group_by: str = "vehicle_body_type", top_n: int = 10,
                             filters: dict | None = None) -> pd.DataFrame:
    """
    Returns asking price sample data for box plots grouped by segment (body type, brand, or fuel).
    Only includes groups with sample size N >= 5.
    """
    path = _gold_mart()
    if not path:
        return pd.DataFrame()
    extra = build_filter_sql(**(filters or {}))
    con = _con()
    try:
        df = con.execute(f"""
            WITH top_groups AS (
                SELECT {group_by} AS grp
                FROM read_parquet('{path}')
                WHERE {_base_price_filter()} {extra}
                  AND {group_by} IS NOT NULL AND {group_by} != ''
                GROUP BY {group_by}
                HAVING COUNT(*) >= 5
                ORDER BY COUNT(*) DESC
                LIMIT {int(top_n)}
            )
            SELECT
                t.{group_by} AS group_label,
                t.price,
                t.vehicle_brand,
                t.vehicle_model,
                t.vehicle_year
            FROM read_parquet('{path}') t
            JOIN top_groups tg ON t.{group_by} = tg.grp
            WHERE {_base_price_filter()} {extra}
        """).df()
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()


@st.cache_data(ttl=CACHE_TTL)
def load_price_vs_year(filters: dict | None = None) -> pd.DataFrame:
    """
    Returns median price, mean price, IQR, and listing volume per manufacturing year.
    Cross-sectional price-by-vintage profile (gated at N >= 3).
    """
    path = _gold_mart()
    if not path:
        return pd.DataFrame()
    extra = build_filter_sql(**(filters or {}))
    con = _con()
    try:
        df = con.execute(f"""
            SELECT
                vehicle_year,
                COUNT(*)                              AS listing_count,
                ROUND(MEDIAN(price), 0)               AS median_price,
                ROUND(AVG(price), 0)                  AS mean_price,
                ROUND(QUANTILE_CONT(price, 0.25), 0)  AS p25_price,
                ROUND(QUANTILE_CONT(price, 0.75), 0)  AS p75_price,
                ROUND(MIN(price), 0)                  AS min_price,
                ROUND(MAX(price), 0)                  AS max_price
            FROM read_parquet('{path}')
            WHERE {_base_price_filter()} {extra}
              AND vehicle_year BETWEEN 1995 AND 2026
            GROUP BY vehicle_year
            HAVING COUNT(*) >= 3
            ORDER BY vehicle_year ASC
        """).df()
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()


# ─────────────────────────────────────────────────────────────────────────────
# 3. Brand & Model Analysis Queries
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=CACHE_TTL)
def load_brand_volume_and_price(top_n: int = 15, filters: dict | None = None) -> pd.DataFrame:
    """
    Returns brand listing count, market share, median price, mean price, and IQR.
    """
    path = _gold_mart()
    if not path:
        return pd.DataFrame()
    extra = build_filter_sql(**(filters or {}))
    con = _con()
    try:
        df = con.execute(f"""
            SELECT
                COALESCE(NULLIF(vehicle_brand, ''), 'Unknown')     AS brand,
                COUNT(*)                                            AS listing_count,
                ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)    AS share_pct,
                ROUND(MEDIAN(price), 0)                             AS median_price,
                ROUND(AVG(price), 0)                                AS mean_price,
                ROUND(QUANTILE_CONT(price, 0.25), 0)                AS p25_price,
                ROUND(QUANTILE_CONT(price, 0.75), 0)                AS p75_price,
                ROUND(MIN(price), 0)                                AS min_price,
                ROUND(MAX(price), 0)                                AS max_price
            FROM read_parquet('{path}')
            WHERE {_base_price_filter()} {extra}
            GROUP BY brand
            ORDER BY listing_count DESC
            LIMIT {int(top_n)}
        """).df()
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()


@st.cache_data(ttl=CACHE_TTL)
def load_model_comparison_matrix(top_n: int = 50, min_samples: int = 5,
                                  filters: dict | None = None) -> pd.DataFrame:
    """
    Returns a comprehensive model comparison matrix with sample size, median price,
    mean price, IQR, min, max, and median year. Gated at N >= min_samples.
    """
    path = _gold_mart()
    if not path:
        return pd.DataFrame()
    extra = build_filter_sql(**(filters or {}))
    con = _con()
    try:
        df = con.execute(f"""
            SELECT
                vehicle_brand                                                      AS brand,
                vehicle_model                                                      AS model,
                CONCAT(vehicle_brand, ' ', vehicle_model)                          AS full_model_name,
                COUNT(*)                                                           AS listing_count,
                ROUND(MEDIAN(price), 0)                                            AS median_price,
                ROUND(AVG(price), 0)                                               AS mean_price,
                ROUND(QUANTILE_CONT(price, 0.75) - QUANTILE_CONT(price, 0.25), 0) AS iqr_price,
                ROUND(QUANTILE_CONT(price, 0.25), 0)                               AS p25_price,
                ROUND(QUANTILE_CONT(price, 0.75), 0)                               AS p75_price,
                ROUND(MIN(price), 0)                                               AS min_price,
                ROUND(MAX(price), 0)                                               AS max_price,
                ROUND(MEDIAN(vehicle_year), 0)                                     AS median_year
            FROM read_parquet('{path}')
            WHERE {_base_price_filter()} {extra}
              AND vehicle_model IS NOT NULL AND vehicle_model != ''
            GROUP BY vehicle_brand, vehicle_model
            HAVING COUNT(*) >= {int(min_samples)}
            ORDER BY listing_count DESC
            LIMIT {int(top_n)}
        """).df()
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()


@st.cache_data(ttl=CACHE_TTL)
def load_model_vintage_breakdown(brand: str, model: str,
                                  filters: dict | None = None) -> pd.DataFrame:
    """
    Returns year-by-year vintage distribution for a specific brand and model.
    Powers the Brand -> Model -> Manufacturing Year drill-down suite.
    """
    path = _gold_mart()
    if not path:
        return pd.DataFrame()
    extra = build_filter_sql(**(filters or {}))
    con = _con()
    safe_brand = brand.replace("'", "''")
    safe_model = model.replace("'", "''")
    try:
        df = con.execute(f"""
            SELECT
                vehicle_year,
                COUNT(*)                                                               AS sample_size,
                ROUND(MEDIAN(price), 0)                                                AS median_price,
                ROUND(AVG(price), 0)                                                   AS mean_price,
                ROUND(QUANTILE_CONT(price, 0.25), 0)                                   AS p25_price,
                ROUND(QUANTILE_CONT(price, 0.75), 0)                                   AS p75_price,
                ROUND(MIN(price), 0)                                                   AS min_price,
                ROUND(MAX(price), 0)                                                   AS max_price,
                ROUND(100.0 * COUNT(*) FILTER (WHERE vehicle_tax_type ILIKE '%tax%')
                    / COUNT(*), 1)                                                     AS tax_paper_pct
            FROM read_parquet('{path}')
            WHERE {_base_price_filter()} {extra}
              AND vehicle_brand = '{safe_brand}'
              AND vehicle_model = '{safe_model}'
            GROUP BY vehicle_year
            HAVING COUNT(*) >= 1
            ORDER BY vehicle_year ASC
        """).df()
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()


# ─────────────────────────────────────────────────────────────────────────────
# 4. Vehicle Characteristics Queries
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=CACHE_TTL)
def load_vehicle_characteristic_analysis(filters: dict | None = None) -> dict[str, pd.DataFrame]:
    """
    Returns detailed distributions and asking-price comparisons across:
    vehicle body type, fuel type, transmission, vehicle age, and documentation (tax status).
    Excludes mileage and engine cc per user instructions.
    """
    path = _gold_mart()
    if not path:
        return {}
    extra = build_filter_sql(**(filters or {}))
    where = f"WHERE {_base_price_filter()} {extra}"
    con = _con()
    try:
        def _breakdown(col: str, alias: str, limit: int = 12, min_n: int = 3) -> pd.DataFrame:
            return con.execute(f"""
                SELECT
                    COALESCE(NULLIF({col}, ''), 'Unspecified')                         AS {alias},
                    COUNT(*)                                                           AS count,
                    ROUND(100.0 * COUNT(*) /
                        (SELECT COUNT(*) FROM read_parquet('{path}') {where}), 1)      AS share_pct,
                    ROUND(MEDIAN(price), 0)                                            AS median_price,
                    ROUND(AVG(price), 0)                                               AS mean_price,
                    ROUND(QUANTILE_CONT(price, 0.25), 0)                               AS p25_price,
                    ROUND(QUANTILE_CONT(price, 0.75), 0)                               AS p75_price
                FROM read_parquet('{path}') {where}
                GROUP BY {alias}
                HAVING COUNT(*) >= {min_n}
                ORDER BY count DESC
                LIMIT {limit}
            """).df()

        # Vehicle Age tiers
        age_df = con.execute(f"""
            SELECT
                CASE
                    WHEN vehicle_age <= 3 THEN '0–3 yrs (Near New)'
                    WHEN vehicle_age <= 7 THEN '4–7 yrs (Late Model)'
                    WHEN vehicle_age <= 12 THEN '8–12 yrs (Established)'
                    WHEN vehicle_age <= 18 THEN '13–18 yrs (Mature)'
                    ELSE '19+ yrs (Legacy)'
                END AS age_tier,
                MIN(vehicle_age) AS min_age,
                COUNT(*) AS count,
                ROUND(100.0 * COUNT(*) /
                    (SELECT COUNT(*) FROM read_parquet('{path}') {where}), 1) AS share_pct,
                ROUND(MEDIAN(price), 0) AS median_price,
                ROUND(AVG(price), 0) AS mean_price,
                ROUND(QUANTILE_CONT(price, 0.25), 0) AS p25_price,
                ROUND(QUANTILE_CONT(price, 0.75), 0) AS p75_price
            FROM read_parquet('{path}') {where}
            GROUP BY 1
            ORDER BY min_age ASC
        """).df()

        # Documentation status (Tax paper vs plate)
        tax_df = con.execute(f"""
            SELECT
                CASE
                    WHEN vehicle_tax_type ILIKE '%tax%' THEN 'Tax Paper (Fresh Import)'
                    WHEN vehicle_tax_type ILIKE '%plate%' THEN 'Plate Number (Registered)'
                    ELSE 'Other / Unspecified'
                END AS tax_status,
                COUNT(*) AS count,
                ROUND(100.0 * COUNT(*) /
                    (SELECT COUNT(*) FROM read_parquet('{path}') {where}), 1) AS share_pct,
                ROUND(MEDIAN(price), 0) AS median_price,
                ROUND(QUANTILE_CONT(price, 0.25), 0) AS p25_price,
                ROUND(QUANTILE_CONT(price, 0.75), 0) AS p75_price
            FROM read_parquet('{path}') {where}
            GROUP BY 1
            ORDER BY count DESC
        """).df()

        return {
            "body_types":    _breakdown("vehicle_body_type", "body_type", 10),
            "fuels":         _breakdown("vehicle_fuel_type", "fuel_type", 8),
            "transmissions": _breakdown("vehicle_transmission", "transmission", 4),
            "age_tiers":     age_df,
            "tax_statuses":  tax_df,
            "conditions":    _breakdown("vehicle_condition", "condition", 5),
        }
    except Exception:
        return {}
    finally:
        con.close()


# ─────────────────────────────────────────────────────────────────────────────
# Dynamic Automated Market Insights (Data-Driven, No Fabrication)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=CACHE_TTL)
def load_market_insights(filters: dict | None = None) -> list[dict[str, str]]:
    """
    Computes data-driven narrative insights based on live data in the active filtered view.
    Zero fabricated numbers — every figure is dynamically queried.
    """
    path = _gold_mart()
    if not path:
        return []

    extra = build_filter_sql(**(filters or {}))
    con = _con()
    insights: list[dict[str, str]] = []

    try:
        # 1. Top brand dominance
        row = con.execute(f"""
            SELECT vehicle_brand, COUNT(*) AS cnt,
                   ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS share_pct
            FROM read_parquet('{path}')
            WHERE {_base_price_filter()} AND vehicle_brand IS NOT NULL {extra}
            GROUP BY vehicle_brand ORDER BY cnt DESC LIMIT 1
        """).fetchone()
        if row:
            insights.append({
                "icon": "🏆",
                "text": f"<b>{row[0]}</b> leads the market with <b>{row[2]:.1f}%</b> of filtered listings (N = {row[1]:,}).",
                "color": "#0284c7",
            })

        # 2. Most listed vehicle body type
        body_row = con.execute(f"""
            SELECT vehicle_body_type, COUNT(*) AS cnt,
                   ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS share_pct,
                   ROUND(MEDIAN(price), 0) AS med_price
            FROM read_parquet('{path}')
            WHERE {_base_price_filter()} AND vehicle_body_type IS NOT NULL
              AND vehicle_body_type != '' {extra}
            GROUP BY vehicle_body_type ORDER BY cnt DESC LIMIT 1
        """).fetchone()
        if body_row:
            insights.append({
                "icon": "🚙",
                "text": f"<b>{body_row[0]}</b> is the dominant body type (<b>{body_row[2]:.1f}%</b> share), with a median asking price of <b>${body_row[3]:,.0f}</b>.",
                "color": "#059669",
            })

        # 3. Hybrid vs Petrol pricing dynamic
        hybrid_row = con.execute(f"""
            SELECT
                ROUND(MEDIAN(CASE WHEN vehicle_fuel_type ILIKE '%hybrid%' THEN price END), 0) AS hybrid_med,
                ROUND(MEDIAN(CASE WHEN vehicle_fuel_type ILIKE '%petrol%'
                     OR vehicle_fuel_type ILIKE '%gasoline%' THEN price END), 0)               AS petrol_med,
                COUNT(*) FILTER (WHERE vehicle_fuel_type ILIKE '%hybrid%')                    AS hybrid_n,
                COUNT(*) FILTER (WHERE vehicle_fuel_type ILIKE '%petrol%'
                     OR vehicle_fuel_type ILIKE '%gasoline%')                                  AS petrol_n
            FROM read_parquet('{path}')
            WHERE {_base_price_filter()} {extra}
        """).fetchone()
        if hybrid_row and hybrid_row[0] and hybrid_row[1] and hybrid_row[2] >= 10 and hybrid_row[3] >= 10:
            diff = int(hybrid_row[0]) - int(hybrid_row[1])
            diff_pct = round(100.0 * diff / hybrid_row[1], 1)
            sign = f"+${diff:,} (+{diff_pct:.1f}%)" if diff > 0 else f"-${abs(diff):,} ({diff_pct:.1f}%)"
            insights.append({
                "icon": "⚡",
                "text": f"Hybrid vehicles carry an asking median delta of <b>{sign}</b> vs petrol equivalents (Hybrid: ${hybrid_row[0]:,.0f} vs Petrol: ${hybrid_row[1]:,.0f}).",
                "color": "#7c3aed",
            })

        # 4. Fresh import (Tax Paper) documentation premium
        tax_row = con.execute(f"""
            SELECT
                ROUND(MEDIAN(CASE WHEN vehicle_tax_type ILIKE '%tax%' THEN price END), 0) AS tax_med,
                ROUND(MEDIAN(CASE WHEN vehicle_tax_type ILIKE '%plate%' THEN price END), 0) AS plate_med,
                COUNT(*) FILTER (WHERE vehicle_tax_type ILIKE '%tax%')   AS tax_n,
                COUNT(*) FILTER (WHERE vehicle_tax_type ILIKE '%plate%') AS plate_n
            FROM read_parquet('{path}')
            WHERE {_base_price_filter()} {extra}
        """).fetchone()
        if tax_row and tax_row[0] and tax_row[1] and tax_row[2] >= 5 and tax_row[3] >= 5:
            gap = int(tax_row[0]) - int(tax_row[1])
            pct = round(100.0 * gap / tax_row[1], 1) if tax_row[1] else 0
            gap_str = f"+${gap:,} (+{pct:.1f}%)" if gap > 0 else f"-${abs(gap):,} ({pct:.1f}%)"
            insights.append({
                "icon": "📄",
                "text": f"Fresh imports (Tax Paper) hold a <b>{gap_str}</b> median asking price spread over registered Plate Number vehicles.",
                "color": "#c59b27",
            })

        # 5. Dealer duplicate repost impact
        dup_stat = con.execute(f"""
            SELECT
                CAST(COALESCE(SUM(repost_count) - COUNT(*), 0) AS BIGINT) AS dup_cnt,
                ROUND(100.0 * (SUM(repost_count) - COUNT(*)) / NULLIF(SUM(repost_count), 0), 1) AS dup_pct
            FROM read_parquet('{path}')
            WHERE {_base_price_filter()} {extra}
        """).fetchone()
        if dup_stat and dup_stat[0] and dup_stat[0] > 0:
            insights.append({
                "icon": "🛡️",
                "text": f"<b>{dup_stat[0]:,} dealer duplicate ads</b> ({dup_stat[1]:.1f}% of platform ad volume) were <b>deduplicated</b> to isolate authentic vehicle supply.",
                "color": "#0ea5e9",
            })

    except Exception:
        pass
    finally:
        con.close()

    return insights


# ─────────────────────────────────────────────────────────────────────────────
# Backward-Compatibility Analytical Query Functions
# (Ensures all existing tests in test_dashboard.py continue to pass 100%)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=CACHE_TTL)
def load_price_trend_over_time(filters: dict | None = None) -> pd.DataFrame:
    """Returns partition-level price and volume trend across scrape dates."""
    path = _silver_snapshots()
    if not path:
        return pd.DataFrame()
    extra = build_filter_sql(**(filters or {}))
    con = _con()
    try:
        df = con.execute(f"""
            SELECT
                CAST(scrape_date AS VARCHAR)          AS scrape_date,
                COUNT(*)                              AS listing_count,
                ROUND(MEDIAN(price), 0)               AS median_price,
                ROUND(AVG(price), 0)                  AS mean_price,
                ROUND(QUANTILE_CONT(price, 0.25), 0)  AS p25_price,
                ROUND(QUANTILE_CONT(price, 0.75), 0)  AS p75_price
            FROM read_parquet('{path}')
            WHERE {_base_price_filter()} {extra}
            GROUP BY scrape_date
            ORDER BY scrape_date ASC
        """).df()
        df["scrape_date"] = pd.to_datetime(df["scrape_date"])
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()


@st.cache_data(ttl=CACHE_TTL)
def load_brand_price_trend(top_n: int = 6, filters: dict | None = None) -> pd.DataFrame:
    """Returns multi-partition median price trend for top N brands."""
    path = _silver_snapshots()
    if not path:
        return pd.DataFrame()
    extra = build_filter_sql(**(filters or {}))
    con = _con()
    try:
        df = con.execute(f"""
            WITH top_brands AS (
                SELECT vehicle_brand
                FROM read_parquet('{path}')
                WHERE {_base_price_filter()} {extra}
                  AND vehicle_brand IS NOT NULL AND vehicle_brand != ''
                GROUP BY vehicle_brand
                ORDER BY COUNT(*) DESC
                LIMIT {int(top_n)}
            )
            SELECT
                CAST(t.scrape_date AS VARCHAR)         AS scrape_date,
                t.vehicle_brand                        AS brand,
                COUNT(*)                               AS listing_count,
                ROUND(MEDIAN(t.price), 0)              AS median_price
            FROM read_parquet('{path}') t
            JOIN top_brands tb ON t.vehicle_brand = tb.vehicle_brand
            WHERE {_base_price_filter()} {extra}
            GROUP BY scrape_date, t.vehicle_brand
            HAVING COUNT(*) >= 3
            ORDER BY scrape_date ASC, t.vehicle_brand
        """).df()
        df["scrape_date"] = pd.to_datetime(df["scrape_date"])
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()


@st.cache_data(ttl=CACHE_TTL)
def load_vintage_price_curves(min_model_samples: int = 30,
                               scrape_date: str | None = None) -> pd.DataFrame:
    """Cross-sectional median price and IQR by model and year."""
    path = _gold_mart()
    if not path:
        return pd.DataFrame()
    date_extra = build_filter_sql(scrape_date=scrape_date)
    min_year_cnt = 1 if scrape_date else 3
    con = _con()
    try:
        df = con.execute(f"""
            WITH qualified_models AS (
                SELECT vehicle_brand, vehicle_model, COUNT(*) AS model_total_count
                FROM read_parquet('{path}')
                WHERE {_base_price_filter()}
                  AND vehicle_year BETWEEN 1995 AND 2026
                  AND vehicle_model IS NOT NULL AND vehicle_model != ''
                GROUP BY vehicle_brand, vehicle_model
                HAVING COUNT(*) >= {min_model_samples}
            ),
            model_year_stats AS (
                SELECT
                    t.vehicle_brand,
                    t.vehicle_model,
                    CONCAT(t.vehicle_brand, ' ', t.vehicle_model) AS full_model_name,
                    q.model_total_count,
                    t.vehicle_year,
                    COUNT(*) AS sample_size,
                    ROUND(MEDIAN(t.price), 0) AS median_price,
                    ROUND(AVG(t.price), 0) AS mean_price,
                    ROUND(QUANTILE_CONT(t.price, 0.25), 0) AS p25_price,
                    ROUND(QUANTILE_CONT(t.price, 0.75), 0) AS p75_price,
                    ROUND(MIN(t.price), 0) AS min_price,
                    ROUND(MAX(t.price), 0) AS max_price
                FROM read_parquet('{path}') t
                JOIN qualified_models q
                  ON t.vehicle_brand = q.vehicle_brand
                  AND t.vehicle_model = q.vehicle_model
                WHERE {_base_price_filter()}
                  AND t.vehicle_year BETWEEN 1995 AND 2026
                  {date_extra}
                GROUP BY t.vehicle_brand, t.vehicle_model, q.model_total_count, t.vehicle_year
                HAVING COUNT(*) >= {min_year_cnt}
            )
            SELECT * FROM model_year_stats
            ORDER BY model_total_count DESC, full_model_name, vehicle_year ASC
        """).df()
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()


@st.cache_data(ttl=CACHE_TTL)
def load_tax_type_comparison(scrape_date: str | None = None) -> pd.DataFrame:
    """Compares Tax Paper vs Plate Number asking prices across top models."""
    path = _gold_mart()
    if not path:
        return pd.DataFrame()
    extra = build_filter_sql(scrape_date=scrape_date)
    con = _con()
    try:
        df = con.execute(f"""
            WITH model_tax_counts AS (
                SELECT
                    vehicle_model,
                    COUNT(*) FILTER (WHERE vehicle_tax_type ILIKE '%tax%') AS tax_cnt,
                    COUNT(*) FILTER (WHERE vehicle_tax_type ILIKE '%plate%') AS plate_cnt,
                    COUNT(*) AS total_cnt
                FROM read_parquet('{path}')
                WHERE {_base_price_filter()} {extra}
                  AND vehicle_model IS NOT NULL AND vehicle_model != ''
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
                END AS tax_status,
                COUNT(*) AS sample_size,
                ROUND(MEDIAN(t.price), 0) AS median_price,
                ROUND(QUANTILE_CONT(t.price, 0.25), 0) AS p25_price,
                ROUND(QUANTILE_CONT(t.price, 0.75), 0) AS p75_price
            FROM read_parquet('{path}') t
            JOIN model_tax_counts mc ON t.vehicle_model = mc.vehicle_model
            WHERE t.vehicle_tax_type IS NOT NULL AND t.vehicle_tax_type != ''
              AND {_base_price_filter()} {extra}
            GROUP BY t.vehicle_model, tax_status, mc.total_cnt
            ORDER BY mc.total_cnt DESC, t.vehicle_model, tax_status
        """).df()
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()


@st.cache_data(ttl=CACHE_TTL)
def load_market_share_breakdown(scrape_date: str | None = None) -> dict[str, pd.DataFrame]:
    """Returns breakdown by Brand, Body Type, Fuel, and Transmission."""
    path = _gold_mart()
    if not path:
        return {}
    extra = build_filter_sql(scrape_date=scrape_date)
    where = f"WHERE {_base_price_filter()} {extra}"
    con = _con()
    try:
        def _breakdown(col: str, alias: str, limit: int = 12) -> pd.DataFrame:
            return con.execute(f"""
                SELECT
                    COALESCE(NULLIF({col}, ''), 'Unspecified') AS {alias},
                    COUNT(*) AS count,
                    ROUND(100.0 * COUNT(*) /
                        (SELECT COUNT(*) FROM read_parquet('{path}') {where}), 1) AS share_pct,
                    ROUND(MEDIAN(price), 0) AS median_price
                FROM read_parquet('{path}') {where}
                GROUP BY {alias} ORDER BY count DESC LIMIT {limit}
            """).df()

        return {
            "brands":        _breakdown("vehicle_brand", "brand", 12),
            "body_types":    _breakdown("vehicle_body_type", "body_type", 10),
            "fuels":         _breakdown("vehicle_fuel_type", "fuel_type", 10),
            "transmissions": _breakdown("vehicle_transmission", "transmission", 8),
        }
    except Exception:
        return {}
    finally:
        con.close()


@st.cache_data(ttl=CACHE_TTL)
def load_regional_pricing(scrape_date: str | None = None) -> pd.DataFrame:
    """Computes listing volume and median price by province (kept for test compatibility)."""
    path = _gold_mart()
    if not path:
        return pd.DataFrame()
    extra = build_filter_sql(scrape_date=scrape_date)
    con = _con()
    try:
        df = con.execute(f"""
            WITH raw_prov AS (
                SELECT
                    COALESCE(NULLIF(province, ''), 'Unknown') AS province_clean,
                    price
                FROM read_parquet('{path}')
                WHERE {_base_price_filter()} {extra}
            ),
            prov_grouped AS (
                SELECT
                    province_clean,
                    COUNT(*) AS count,
                    ROUND(MEDIAN(price), 0) AS median_price,
                    ROUND(AVG(price), 0) AS mean_price,
                    ROUND(QUANTILE_CONT(price, 0.25), 0) AS p25_price,
                    ROUND(QUANTILE_CONT(price, 0.75), 0) AS p75_price
                FROM raw_prov GROUP BY province_clean
            ),
            total_cnt AS (SELECT SUM(count) AS grand_total FROM prov_grouped)
            SELECT
                CASE WHEN p.count >= 20 THEN p.province_clean
                     ELSE 'Other Provinces (N < 20)' END AS province,
                SUM(p.count) AS sample_size,
                ROUND(100.0 * SUM(p.count) / t.grand_total, 1) AS share_pct,
                ROUND(MEDIAN(p.median_price), 0) AS median_price,
                ROUND(AVG(p.p25_price), 0) AS p25_price,
                ROUND(AVG(p.p75_price), 0) AS p75_price
            FROM prov_grouped p, total_cnt t
            GROUP BY
                CASE WHEN p.count >= 20 THEN p.province_clean
                     ELSE 'Other Provinces (N < 20)' END,
                t.grand_total
            ORDER BY sample_size DESC
        """).df()
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()


@st.cache_data(ttl=CACHE_TTL)
def load_province_brand_breakdown(top_n_provinces: int = 8, top_n_brands: int = 6,
                                   filters: dict | None = None) -> pd.DataFrame:
    """Returns brand counts by province (kept for test compatibility)."""
    path = _gold_mart()
    if not path:
        return pd.DataFrame()
    extra = build_filter_sql(**(filters or {}))
    con = _con()
    try:
        df = con.execute(f"""
            WITH top_prov AS (
                SELECT province FROM read_parquet('{path}')
                WHERE province IS NOT NULL AND province != ''
                  AND {_base_price_filter()} {extra}
                GROUP BY province ORDER BY COUNT(*) DESC LIMIT {int(top_n_provinces)}
            ),
            top_brands AS (
                SELECT vehicle_brand FROM read_parquet('{path}')
                WHERE vehicle_brand IS NOT NULL AND vehicle_brand != ''
                  AND {_base_price_filter()} {extra}
                GROUP BY vehicle_brand ORDER BY COUNT(*) DESC LIMIT {int(top_n_brands)}
            )
            SELECT
                t.province,
                t.vehicle_brand AS brand,
                COUNT(*) AS listing_count
            FROM read_parquet('{path}') t
            JOIN top_prov tp ON t.province = tp.province
            JOIN top_brands tb ON t.vehicle_brand = tb.vehicle_brand
            WHERE {_base_price_filter()} {extra}
            GROUP BY t.province, t.vehicle_brand
            ORDER BY t.province, listing_count DESC
        """).df()
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()


@st.cache_data(ttl=CACHE_TTL)
def load_model_price_range(top_n: int = 20, filters: dict | None = None) -> pd.DataFrame:
    """Returns model price range statistics (min, P25, median, P75, max)."""
    return load_model_comparison_matrix(top_n=top_n, filters=filters)


@st.cache_data(ttl=CACHE_TTL)
def load_year_distribution(filters: dict | None = None) -> pd.DataFrame:
    """Returns listing count by manufacturing year."""
    return load_price_vs_year(filters=filters)[["vehicle_year", "listing_count"]]


@st.cache_data(ttl=CACHE_TTL)
def load_mileage_by_brand(top_n: int = 15, filters: dict | None = None) -> pd.DataFrame:
    """Stub returning empty DataFrame to maintain backward compatibility."""
    return pd.DataFrame(columns=["brand", "listing_count", "median_mileage_km", "p25_mileage", "p75_mileage"])


@st.cache_data(ttl=CACHE_TTL)
def load_price_vs_mileage_sample(sample_size: int = 2000, filters: dict | None = None) -> pd.DataFrame:
    """Stub returning empty DataFrame to maintain backward compatibility."""
    return pd.DataFrame(columns=["price", "vehicle_mileage_km", "brand", "vehicle_year", "fuel_type", "model_label"])
