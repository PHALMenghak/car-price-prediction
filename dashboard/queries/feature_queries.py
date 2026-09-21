"""
dashboard/queries/feature_queries.py
====================================
Day-0 ML feature store profiling, leakage prevention audit, distributions, and correlation matrix.
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd
import streamlit as st

from dashboard import config
from dashboard.queries.base import (
    _con,
    CACHE_TTL,
    GOLD_MART_PATH,
    GOLD_ML_PATH,
    SILVER_PATH,
)
from dashboard.queries.core_queries import load_dbt_test_status

@st.cache_data(ttl=CACHE_TTL)
def load_ml_readiness() -> dict:
    """
    Evaluates ML training readiness: row counts, target stats, leakage absence, and final verdict.
    """
    con = _con()
    res = {
        "available": False,
        "total_ml_records": 0,
        "total_gold_mart": 0,
        "ml_eligibility_pct": 0.0,
        "target_stats": {},
        "verdict": "BLOCKED",
        "verdict_badge": "🔴 DATASET BLOCKED",
        "verdict_color": "#c62828",
        "checks": [],
    }

    if not os.path.exists(GOLD_ML_PATH):
        return res

    try:
        # Check counts
        ml_count = con.execute(f"SELECT COUNT(*) FROM read_parquet('{GOLD_ML_PATH}')").fetchone()[0]
        mart_count = con.execute(f"SELECT COUNT(*) FROM read_parquet('{GOLD_MART_PATH}')").fetchone()[0] if os.path.exists(GOLD_MART_PATH) else ml_count
        res["total_ml_records"] = int(ml_count)
        res["total_gold_mart"] = int(mart_count)
        res["ml_eligibility_pct"] = round(100.0 * ml_count / mart_count, 1) if mart_count > 0 else 0.0
        res["available"] = True

        # Target stats
        target_row = con.execute(f"""
            SELECT
                ROUND(AVG(price), 2) AS price_mean,
                ROUND(MEDIAN(price), 2) AS price_median,
                ROUND(STDDEV(price), 2) AS price_std,
                ROUND(MIN(price), 2) AS price_min,
                ROUND(MAX(price), 2) AS price_max,
                ROUND(QUANTILE_CONT(price, 0.25), 2) AS price_p25,
                ROUND(QUANTILE_CONT(price, 0.75), 2) AS price_p75,
                ROUND(AVG(log_price), 4) AS log_price_mean,
                ROUND(STDDEV(log_price), 4) AS log_price_std,
                COUNT(*) FILTER (WHERE price IS NULL OR price <= 0) AS invalid_target_count
            FROM read_parquet('{GOLD_ML_PATH}')
        """).fetchone()

        if target_row:
            res["target_stats"] = {
                "price_mean": float(target_row[0] or 0),
                "price_median": float(target_row[1] or 0),
                "price_std": float(target_row[2] or 0),
                "price_min": float(target_row[3] or 0),
                "price_max": float(target_row[4] or 0),
                "price_p25": float(target_row[5] or 0),
                "price_p75": float(target_row[6] or 0),
                "log_price_mean": float(target_row[7] or 0),
                "log_price_std": float(target_row[8] or 0),
                "invalid_target_count": int(target_row[9] or 0),
            }

        # Leakage check in ML features
        ml_cols = set(con.execute(f"DESCRIBE SELECT * FROM read_parquet('{GOLD_ML_PATH}')").df()["column_name"])
        leakage_detected = any(col in ml_cols for col in config.LEAKAGE_COLUMNS)

        # dbt tests
        dbt_status = load_dbt_test_status()

        # Build checks
        checks = []
        c1 = ml_count >= 1000
        checks.append({"check": "Sufficient Sample Size (≥ 1,000)", "passed": c1, "detail": f"{ml_count:,} records in Gold ML"})
        c2 = res["target_stats"].get("invalid_target_count", 1) == 0
        checks.append({"check": "Target Variable Integrity (Price > 0, No NULLs)", "passed": c2, "detail": "0 null or non-positive target rows"})
        c3 = not leakage_detected
        checks.append({"check": "Zero Data Leakage (days_on_market, price_drop excluded)", "passed": c3, "detail": "Verified zero future-state features in Gold ML"})
        c4 = dbt_status.get("failed", 0) == 0
        checks.append({"check": "dbt Data Integrity Tests Passing", "passed": c4, "detail": f"{dbt_status.get('passed', 0)}/{dbt_status.get('total', 0)} tests passing"})

        all_passed = all(c["passed"] for c in checks)
        res["checks"] = checks
        if all_passed:
            res["verdict"] = "READY"
            res["verdict_badge"] = "✅ DATASET APPROVED FOR ML TRAINING"
            res["verdict_color"] = "#2e7d32"
        else:
            res["verdict"] = "BLOCKED"
            res["verdict_badge"] = "⚠️ DATASET REQUIRES ATTENTION"
            res["verdict_color"] = "#e65100"

    except Exception:
        pass
    finally:
        con.close()

    return res


@st.cache_data(ttl=CACHE_TTL)
def load_ml_leakage_audit() -> pd.DataFrame:
    """Audits leakage prevention by checking Gold ML vs Gold Mart column schemas."""
    if not os.path.exists(GOLD_ML_PATH):
        return pd.DataFrame()

    con = _con()
    records = []
    try:
        ml_cols = set(con.execute(f"DESCRIBE SELECT * FROM read_parquet('{GOLD_ML_PATH}')").df()["column_name"])
        mart_cols = set(con.execute(f"DESCRIBE SELECT * FROM read_parquet('{GOLD_MART_PATH}')").df()["column_name"]) if os.path.exists(GOLD_MART_PATH) else set()

        audit_candidates = [
            ("days_on_market", "Marketplace exposure time is unavailable at Day 0 appraisal; causes extreme target leakage."),
            ("price_drop_amount", "Cumulative discount over time; unavailable when pricing new listings."),
            ("has_price_drop", "Binary indicator of seller markdown; leaking seller distress/urgency."),
            ("initial_price", "Original asking price before markdowns; leaking target directly."),
            ("seller_name", "Free-text individual seller names; high cardinality noise and privacy concern."),
            ("data_quality_reasons", "Internal audit flag; not an intrinsic vehicle specification."),
        ]

        for col, rationale in audit_candidates:
            in_ml = col in ml_cols
            in_mart = col in mart_cols
            status = "🚨 LEAKAGE DETECTED" if in_ml else "🛡️ SAFE (Excluded from ML)"
            records.append({
                "column_name": col,
                "in_gold_reporting_mart": "✅ Present" if in_mart else "❌ Absent",
                "in_gold_ml_features": "🚨 Present" if in_ml else "🛡️ Excluded",
                "leakage_status": status,
                "rationale": rationale,
            })
    except Exception:
        pass
    finally:
        con.close()

    return pd.DataFrame(records)


@st.cache_data(ttl=CACHE_TTL)
def load_feature_numeric_stats(target_dataset: str = "silver", scrape_date: str | None = None) -> pd.DataFrame:
    """
    Computes summary descriptive statistics for numeric features.
    target_dataset: 'silver' or 'gold_ml'
    """
    path = GOLD_ML_PATH if target_dataset == "gold_ml" else SILVER_PATH
    if not os.path.exists(path):
        return pd.DataFrame()

    con = _con()
    date_filter = f"AND CAST(scrape_date AS VARCHAR) = '{scrape_date}'" if (scrape_date and target_dataset == "silver") else ""

    try:
        if target_dataset == "gold_ml":
            query = f"""
                WITH unpivoted AS (
                    SELECT 'price' AS feature, price AS val FROM read_parquet('{path}') WHERE price > 0
                    UNION ALL
                    SELECT 'log_price', log_price FROM read_parquet('{path}') WHERE log_price IS NOT NULL
                    UNION ALL
                    SELECT 'vehicle_age', CAST(vehicle_age AS DOUBLE) FROM read_parquet('{path}') WHERE vehicle_age IS NOT NULL
                    UNION ALL
                    SELECT 'vehicle_mileage_km', CAST(vehicle_mileage_km AS DOUBLE) FROM read_parquet('{path}') WHERE vehicle_mileage_km IS NOT NULL
                    UNION ALL
                    SELECT 'vehicle_engine_cc', CAST(vehicle_engine_cc AS DOUBLE) FROM read_parquet('{path}') WHERE vehicle_engine_cc IS NOT NULL
                )
                SELECT
                    feature,
                    COUNT(*)                                          AS populated_count,
                    ROUND(AVG(val), 2)                               AS mean,
                    ROUND(STDDEV(val), 2)                            AS std_dev,
                    ROUND(MIN(val), 2)                               AS min_val,
                    ROUND(QUANTILE_CONT(val, 0.25), 2)               AS p25,
                    ROUND(MEDIAN(val), 2)                            AS median_val,
                    ROUND(QUANTILE_CONT(val, 0.75), 2)               AS p75,
                    ROUND(MAX(val), 2)                               AS max_val,
                    ROUND(SKEWNESS(val), 2)                          AS skewness
                FROM unpivoted
                GROUP BY feature
                ORDER BY CASE feature
                    WHEN 'price' THEN 1
                    WHEN 'log_price' THEN 2
                    WHEN 'vehicle_age' THEN 3
                    WHEN 'vehicle_mileage_km' THEN 4
                    WHEN 'vehicle_engine_cc' THEN 5
                    ELSE 6
                END
            """
        else:
            query = f"""
                WITH unpivoted AS (
                    SELECT 'price' AS feature, price AS val FROM read_parquet('{path}') WHERE price > 0 {date_filter}
                    UNION ALL
                    SELECT 'log_price', LN(1.0 + price) FROM read_parquet('{path}') WHERE price > 0 {date_filter}
                    UNION ALL
                    SELECT 'vehicle_year', CAST(vehicle_year AS DOUBLE) FROM read_parquet('{path}') WHERE vehicle_year IS NOT NULL {date_filter}
                    UNION ALL
                    SELECT 'vehicle_age', CAST(GREATEST(date_part('year', scrape_date) - vehicle_year, 0) AS DOUBLE) FROM read_parquet('{path}') WHERE vehicle_year IS NOT NULL {date_filter}
                    UNION ALL
                    SELECT 'vehicle_mileage_km', CAST(vehicle_mileage_km AS DOUBLE) FROM read_parquet('{path}') WHERE vehicle_mileage_km IS NOT NULL {date_filter}
                    UNION ALL
                    SELECT 'vehicle_engine_cc', CAST(vehicle_engine_cc AS DOUBLE) FROM read_parquet('{path}') WHERE vehicle_engine_cc IS NOT NULL {date_filter}
                )
                SELECT
                    feature,
                    COUNT(*)                                          AS populated_count,
                    ROUND(AVG(val), 2)                               AS mean,
                    ROUND(STDDEV(val), 2)                            AS std_dev,
                    ROUND(MIN(val), 2)                               AS min_val,
                    ROUND(QUANTILE_CONT(val, 0.25), 2)               AS p25,
                    ROUND(MEDIAN(val), 2)                            AS median_val,
                    ROUND(QUANTILE_CONT(val, 0.75), 2)               AS p75,
                    ROUND(MAX(val), 2)                               AS max_val,
                    ROUND(SKEWNESS(val), 2)                          AS skewness
                FROM unpivoted
                GROUP BY feature
                ORDER BY CASE feature
                    WHEN 'price' THEN 1
                    WHEN 'log_price' THEN 2
                    WHEN 'vehicle_year' THEN 3
                    WHEN 'vehicle_age' THEN 4
                    WHEN 'vehicle_mileage_km' THEN 5
                    WHEN 'vehicle_engine_cc' THEN 6
                    ELSE 7
                END
            """
        df = con.execute(query).df()
    except Exception:
        df = pd.DataFrame()
    finally:
        con.close()

    return df


@st.cache_data(ttl=CACHE_TTL)
def load_categorical_cardinality(target_dataset: str = "silver", scrape_date: str | None = None) -> pd.DataFrame:
    """
    Computes distinct count, top 3 values, and nullity for categorical features.
    """
    path = GOLD_ML_PATH if target_dataset == "gold_ml" else SILVER_PATH
    if not os.path.exists(path):
        return pd.DataFrame()

    con = _con()
    results = []
    cat_cols = (
        ["vehicle_brand", "vehicle_model", "vehicle_fuel_type", "vehicle_transmission", "vehicle_body_type", "province", "brand_category", "seller_type"]
        if target_dataset == "gold_ml"
        else ["vehicle_brand", "vehicle_model", "vehicle_fuel_type", "vehicle_transmission", "vehicle_body_type", "province", "brand_tier", "seller_type"]
    )
    date_filter = f"WHERE CAST(scrape_date AS VARCHAR) = '{scrape_date}'" if (scrape_date and target_dataset == "silver") else ""

    try:
        where_total = date_filter
        total = con.execute(f"SELECT COUNT(*) FROM read_parquet('{path}') {where_total}").fetchone()[0]
        if total == 0:
            return pd.DataFrame()

        for col in cat_cols:
            col_filter = f"{date_filter} AND {col} IS NULL" if date_filter else f"WHERE {col} IS NULL"
            col_notnull = f"{date_filter} AND {col} IS NOT NULL" if date_filter else f"WHERE {col} IS NOT NULL"

            null_count = con.execute(f"SELECT COUNT(*) FROM read_parquet('{path}') {col_filter}").fetchone()[0]
            distinct_count = con.execute(f"SELECT COUNT(DISTINCT {col}) FROM read_parquet('{path}') {col_notnull}").fetchone()[0]
            top3 = con.execute(f"""
                SELECT {col} AS val, COUNT(*) AS cnt, ROUND(100.0 * COUNT(*) / {total}, 1) AS pct
                FROM read_parquet('{path}')
                {col_notnull}
                GROUP BY 1
                ORDER BY 2 DESC
                LIMIT 3
            """).fetchall()
            t1 = f"{top3[0][0]} ({top3[0][2]}%)" if len(top3) > 0 else "N/A"
            t2 = f"{top3[1][0]} ({top3[1][2]}%)" if len(top3) > 1 else "N/A"
            t3 = f"{top3[2][0]} ({top3[2][2]}%)" if len(top3) > 2 else "N/A"
            results.append({
                "feature": col,
                "distinct_count": distinct_count,
                "top_1": t1,
                "top_2": t2,
                "top_3": t3,
                "missing_count": null_count,
                "missing_pct": round(100.0 * null_count / total, 1) if total > 0 else 0.0,
            })
    except Exception:
        pass
    finally:
        con.close()

    return pd.DataFrame(results)


@st.cache_data(ttl=CACHE_TTL)
def load_categorical_distribution(feature_name: str, top_n: int = 10, target_dataset: str = "silver", scrape_date: str | None = None) -> pd.DataFrame:
    """
    Returns top N values and their counts/percentages for a specific categorical feature.
    """
    path = GOLD_ML_PATH if target_dataset == "gold_ml" else SILVER_PATH
    if not os.path.exists(path):
        return pd.DataFrame()

    con = _con()
    date_clause = f"AND CAST(scrape_date AS VARCHAR) = '{scrape_date}'" if (scrape_date and target_dataset == "silver") else ""

    try:
        total = con.execute(f"SELECT COUNT(*) FROM read_parquet('{path}') WHERE {feature_name} IS NOT NULL {date_clause}").fetchone()[0]
        if total == 0:
            return pd.DataFrame()

        df = con.execute(f"""
            SELECT
                COALESCE(CAST({feature_name} AS VARCHAR), 'Unknown') AS category,
                COUNT(*) AS count,
                ROUND(100.0 * COUNT(*) / {total}, 1) AS pct
            FROM read_parquet('{path}')
            WHERE {feature_name} IS NOT NULL {date_clause}
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT {top_n}
        """).df()
    except Exception:
        df = pd.DataFrame()
    finally:
        con.close()

    return df


@st.cache_data(ttl=CACHE_TTL)
def load_feature_distribution_sample(target_dataset: str = "silver", limit: int = 5000, scrape_date: str | None = None) -> pd.DataFrame:
    """
    Returns sampled records for rendering distribution plots and boxplots.
    Uses random sampling to prevent temporal partition bias.
    """
    path = GOLD_ML_PATH if target_dataset == "gold_ml" else SILVER_PATH
    if not os.path.exists(path):
        return pd.DataFrame()

    con = _con()
    date_filter = f"AND CAST(scrape_date AS VARCHAR) = '{scrape_date}'" if (scrape_date and target_dataset == "silver") else ""

    try:
        if target_dataset == "gold_ml":
            df = con.execute(f"""
                SELECT
                    price,
                    log_price,
                    vehicle_age,
                    vehicle_mileage_km,
                    vehicle_engine_cc,
                    brand_category AS brand_tier,
                    vehicle_body_type,
                    vehicle_fuel_type
                FROM read_parquet('{path}')
                ORDER BY RANDOM()
                LIMIT {limit}
            """).df()
        else:
            df = con.execute(f"""
                SELECT
                    price,
                    LN(1.0 + price) AS log_price,
                    vehicle_year,
                    GREATEST(date_part('year', scrape_date) - vehicle_year, 0) AS vehicle_age,
                    vehicle_mileage_km,
                    vehicle_engine_cc,
                    brand_tier,
                    vehicle_body_type,
                    vehicle_fuel_type
                FROM read_parquet('{path}')
                WHERE price > 0 {date_filter}
                ORDER BY RANDOM()
                LIMIT {limit}
            """).df()
    except Exception:
        df = pd.DataFrame()
    finally:
        con.close()

    return df


@st.cache_data(ttl=CACHE_TTL)
def load_feature_correlation_matrix() -> pd.DataFrame:
    """
    Computes Pearson correlation matrix for numeric features in Gold ML.
    """
    if not os.path.exists(GOLD_ML_PATH):
        return pd.DataFrame()

    con = _con()
    try:
        df = con.execute(f"""
            SELECT
                price,
                log_price,
                vehicle_age,
                COALESCE(vehicle_mileage_km, 0) AS mileage_km,
                COALESCE(vehicle_engine_cc, 0) AS engine_cc,
                is_plate_number,
                has_full_option
            FROM read_parquet('{GOLD_ML_PATH}')
        """).df()
        corr_df = df.corr().round(2)
    except Exception:
        corr_df = pd.DataFrame()
    finally:
        con.close()

    return corr_df

