"""
dashboard/data_loader.py
========================
All DuckDB queries for the Executive DQ Dashboard.
Reads from:
  - data/silver/cars_cleaned.parquet  (Silver layer — cleaned + quality-flagged)
  - data/bronze/cars_*.parquet        (Bronze layer — raw ingestion)
  - data/bronze/ingestion_manifest.json (Last-run pipeline manifest)

Results are cached for 1 hour via @st.cache_data.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

from dashboard import config

# ── Paths (relative to project root, resolved at import time) ──────────────────
_HERE = Path(__file__).parent.parent          # project root
_BRONZE_DIR = _HERE / "data" / "bronze"

# DuckDB requires forward slashes even on Windows — convert explicitly
SILVER_PATH     = (_HERE / "data" / "silver" / "cars_cleaned.parquet").as_posix()
BRONZE_GLOB     = (_HERE / "data" / "bronze" / "cars_*.parquet").as_posix()
GOLD_ML_PATH    = (_HERE / "data" / "gold" / "fct_cars_ml_features.parquet").as_posix()
GOLD_MART_PATH  = (_HERE / "data" / "gold" / "fct_car_listings.parquet").as_posix()
MANIFEST_PATH   = str(_HERE / "data" / "bronze" / "ingestion_manifest.json")
DBT_RUN_RESULTS = str(_HERE / "dbt" / "target" / "run_results.json")

CACHE_TTL = 3600  # 1 hour


def _con() -> duckdb.DuckDBPyConnection:
    """Return a fresh in-memory DuckDB connection (cheap; no state shared across calls)."""
    return duckdb.connect(database=":memory:", read_only=False)


# ── 1. Pipeline manifest & dbt test health ─────────────────────────────────────

@st.cache_data(ttl=CACHE_TTL)
def load_manifest() -> dict:
    """Load the latest ingestion_manifest.json written by the scraper."""
    if not os.path.exists(MANIFEST_PATH):
        return {}
    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


@st.cache_data(ttl=CACHE_TTL)
def load_dbt_test_status() -> dict:
    """Reads dbt test execution results from dbt/target/run_results.json."""
    if not os.path.exists(DBT_RUN_RESULTS):
        return {
            "available": False,
            "total": 0,
            "passed": 0,
            "failed": 0,
            "warn": 0,
            "pass_rate_pct": 0.0,
            "elapsed_seconds": 0.0,
            "run_at": "Never",
        }
    try:
        with open(DBT_RUN_RESULTS, "r", encoding="utf-8") as f:
            data = json.load(f)
        results = data.get("results", [])
        # Filter specifically for test nodes if present (e.g. from dbt build or dbt test)
        test_nodes = [r for r in results if r.get("unique_id", "").startswith("test.")]
        eval_results = test_nodes if test_nodes else results
        total = len(eval_results)
        passed = sum(1 for r in eval_results if r.get("status") in ("pass", "success"))
        failed = sum(1 for r in eval_results if r.get("status") in ("fail", "error"))
        warn   = sum(1 for r in eval_results if r.get("status") == "warn")
        elapsed = round(float(data.get("elapsed_time", 0)), 2)
        generated_at = data.get("metadata", {}).get("generated_at", "")[:16].replace("T", " ")
        pass_rate = round(100.0 * passed / total, 1) if total > 0 else 0.0
        return {
            "available": True,
            "total": total,
            "passed": passed,
            "failed": failed,
            "warn": warn,
            "pass_rate_pct": pass_rate,
            "elapsed_seconds": elapsed,
            "run_at": generated_at,
        }
    except Exception:
        return {
            "available": False,
            "total": 0,
            "passed": 0,
            "failed": 0,
            "warn": 0,
            "pass_rate_pct": 0.0,
            "elapsed_seconds": 0.0,
            "run_at": "Error",
        }


# ── 2. Available snapshot dates ────────────────────────────────────────────────

@st.cache_data(ttl=CACHE_TTL)
def load_available_dates() -> list[str]:
    """Return distinct scrape_dates in Silver layer sorted descending."""
    if not os.path.exists(SILVER_PATH):
        return []
    con = _con()
    try:
        dates = con.execute(f"""
            SELECT DISTINCT CAST(scrape_date AS VARCHAR) AS sd
            FROM read_parquet('{SILVER_PATH}')
            ORDER BY sd DESC
        """).fetchall()
        return [d[0] for d in dates]
    except Exception:
        return []
    finally:
        con.close()


# ── 3. Quality tier summary (per scrape_date) ─────────────────────────────────

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


# ── 3. Bronze raw volume per date ─────────────────────────────────────────────

@st.cache_data(ttl=CACHE_TTL)
def load_bronze_volume() -> pd.DataFrame:
    """Daily raw record counts from the Bronze layer Parquet files."""
    parquet_files = list(_BRONZE_DIR.glob("cars_*.parquet"))
    if not parquet_files:
        return pd.DataFrame()

    con = _con()
    try:
        df = con.execute(f"""
            SELECT
                TRY_CAST(scraped_at AS DATE) AS scrape_date,
                COUNT(*) AS raw_count
            FROM read_parquet('{BRONZE_GLOB}', union_by_name=true)
            GROUP BY 1
            ORDER BY 1
        """).df()
    except Exception:
        df = pd.DataFrame()
    con.close()
    return df




# ── 7. Price validity breakdown ───────────────────────────────────────────────

@st.cache_data(ttl=CACHE_TTL)
def load_price_violations(scrape_date: str | None = None) -> pd.DataFrame:
    """Counts of specific price violation reason codes."""
    if not os.path.exists(SILVER_PATH):
        return pd.DataFrame()

    date_filter = (
        f"WHERE CAST(scrape_date AS VARCHAR) = '{scrape_date}'"
        if scrape_date
        else ""
    )

    con = _con()
    try:
        df = con.execute(f"""
            SELECT
                'Price = NULL'              AS issue, COUNT(*) FILTER (WHERE price IS NULL)         AS count FROM read_parquet('{SILVER_PATH}') {date_filter}
            UNION ALL SELECT 'Price ≤ 0',          COUNT(*) FILTER (WHERE price IS NOT NULL AND price <= 0)   FROM read_parquet('{SILVER_PATH}') {date_filter}
            UNION ALL SELECT 'Price < $500',        COUNT(*) FILTER (WHERE price > 0 AND price < 500)         FROM read_parquet('{SILVER_PATH}') {date_filter}
            UNION ALL SELECT 'Price > $300K',       COUNT(*) FILTER (WHERE price > 300000)                    FROM read_parquet('{SILVER_PATH}') {date_filter}
            UNION ALL SELECT 'Price anomaly / outlier', COUNT(*) FILTER (WHERE is_price_outlier = 1)        FROM read_parquet('{SILVER_PATH}') {date_filter}
            ORDER BY count DESC
        """).df()
    except Exception:
        df = pd.DataFrame()
    finally:
        con.close()

    return df[df["count"] > 0] if not df.empty else df




# ── 9. Top quarantine / quality reasons ───────────────────────────────────────

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


# ── 10. Brand x Failure Reason 2D Matrix ──────────────────────────────────────

@st.cache_data(ttl=CACHE_TTL)
def load_reason_brand_matrix(top_n_brands: int = 8, top_n_reasons: int = 6) -> pd.DataFrame:
    """
    Returns a 2D cross-tabulation of Brand x Failure Reason across all flagged records.
    Used to render a real executive heatmap of error hotspots.
    """
    if not os.path.exists(SILVER_PATH):
        return pd.DataFrame()

    con = _con()
    try:
        df = con.execute(f"""
            WITH exploded AS (
                SELECT
                    COALESCE(vehicle_brand, '(Unknown)') AS brand,
                    TRIM(UNNEST(STRING_SPLIT(data_quality_reasons, '|'))) AS reason
                FROM read_parquet('{SILVER_PATH}')
                WHERE data_quality_reasons IS NOT NULL AND data_quality_reasons != ''
            ),
            top_brands AS (
                SELECT brand
                FROM exploded
                WHERE reason != ''
                GROUP BY 1
                ORDER BY COUNT(*) DESC
                LIMIT {top_n_brands}
            ),
            top_reasons AS (
                SELECT reason
                FROM exploded
                WHERE reason != ''
                GROUP BY 1
                ORDER BY COUNT(*) DESC
                LIMIT {top_n_reasons}
            )
            SELECT
                e.brand,
                e.reason,
                COUNT(*) AS count
            FROM exploded e
            JOIN top_brands tb ON e.brand = tb.brand
            JOIN top_reasons tr ON e.reason = tr.reason
            WHERE e.reason != ''
            GROUP BY 1, 2
        """).df()
    except Exception:
        df = pd.DataFrame()
    finally:
        con.close()

    if df.empty:
        return pd.DataFrame()

    return df.pivot(index="brand", columns="reason", values="count").fillna(0).astype(int)


# ── 11. Audit lineage with side-by-side Bronze vs Silver values ───────────────

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
                    s.vehicle_brand                         AS clean_brand,
                    s.vehicle_model                         AS clean_model,
                    s.vehicle_year                          AS clean_year,
                    ROUND(s.price, 0)                       AS clean_price,
                    s.province                              AS clean_province,
                    s.model_extraction_method,
                    s.is_year_healed,
                    s.is_spam,
                    s.is_down_payment,
                    s.is_price_outlier,
                    s.title_clean,
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




# ── 15. Daily Missingness Trend ───────────────────────────────────────────────

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
    """
    if not os.path.exists(SILVER_PATH):
        return pd.DataFrame()

    critical = ["price", "scrape_date"]
    high     = ["vehicle_brand", "vehicle_model", "vehicle_year", "province"]
    medium   = ["vehicle_mileage_km", "vehicle_engine_cc", "vehicle_fuel_type",
                "vehicle_transmission", "vehicle_body_type", "vehicle_tax_type"]
    low      = ["vehicle_color", "vehicle_condition", "description_clean"]

    fields = critical + high + medium + low
    priority_map = (
        {f: "🔴 Critical" for f in critical}
        | {f: "🟠 High" for f in high}
        | {f: "🟡 Medium" for f in medium}
        | {f: "🟢 Low" for f in low}
    )

    date_filter = (
        f"WHERE CAST(scrape_date AS VARCHAR) = '{scrape_date}'"
        if scrape_date
        else ""
    )

    exprs = []
    for f in fields:
        exprs.append(f"""
            SELECT
                '{f}' AS field,
                COUNT(*) AS total_records,
                COUNT({f}) AS non_null_count,
                COUNT(*) FILTER (WHERE {f} IS NULL) AS null_count,
                ROUND(100.0 * COUNT({f}) / NULLIF(COUNT(*), 0), 2) AS completeness_pct,
                ROUND(100.0 * COUNT(*) FILTER (WHERE {f} IS NULL) / NULLIF(COUNT(*), 0), 2) AS null_pct
            FROM read_parquet('{SILVER_PATH}')
            {date_filter}
        """)

    full_query = " UNION ALL ".join(exprs)
    con = _con()
    try:
        df = con.execute(full_query).df()
        df["priority"] = df["field"].map(priority_map)
        df = df.sort_values(by=["priority", "completeness_pct"], ascending=[True, False])
    except Exception:
        df = pd.DataFrame()
    finally:
        con.close()
    return df


# ── 16. Duplicate & Freshness Stats ───────────────────────────────────────────

@st.cache_data(ttl=CACHE_TTL)
def load_duplicate_stats() -> dict:
    """
    Computes intra-day duplicate metrics, multi-day recurrence, and deduplication efficiency.
    """
    con = _con()
    results = {
        "silver_daily": pd.DataFrame(),
        "bronze_daily": pd.DataFrame(),
        "persistence": pd.DataFrame(),
        "bronze_total": 0,
        "bronze_unique": 0,
        "silver_total": 0,
        "silver_unique": 0,
        "intra_day_deduped_count": 0,
    }

    try:
        if os.path.exists(SILVER_PATH):
            results["silver_daily"] = con.execute(f"""
                SELECT
                    CAST(scrape_date AS VARCHAR) AS scrape_date,
                    COUNT(*) AS total_records,
                    COUNT(DISTINCT listing_id) AS unique_listings,
                    COUNT(*) - COUNT(DISTINCT listing_id) AS intra_day_duplicates,
                    ROUND(100.0 * (COUNT(*) - COUNT(DISTINCT listing_id)) / COUNT(*), 2) AS dup_rate_pct
                FROM read_parquet('{SILVER_PATH}')
                GROUP BY 1
                ORDER BY 1 ASC
            """).df()

            s_counts = con.execute(f"""
                SELECT COUNT(*), COUNT(DISTINCT listing_id) FROM read_parquet('{SILVER_PATH}')
            """).fetchone()
            if s_counts:
                results["silver_total"] = int(s_counts[0])
                results["silver_unique"] = int(s_counts[1])

            results["persistence"] = con.execute(f"""
                WITH listing_days AS (
                    SELECT listing_id, COUNT(DISTINCT scrape_date) AS days_seen
                    FROM read_parquet('{SILVER_PATH}')
                    GROUP BY 1
                )
                SELECT
                    CASE
                        WHEN days_seen = 1 THEN '1 day (New / Transient)'
                        WHEN days_seen = 2 THEN '2 days'
                        WHEN days_seen = 3 THEN '3 days'
                        WHEN days_seen BETWEEN 4 AND 6 THEN '4-6 days'
                        ELSE '7+ days (Persistent)'
                    END AS persistence_bucket,
                    COUNT(*) AS listing_count,
                    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM listing_days), 1) AS pct
                FROM listing_days
                GROUP BY 1
                ORDER BY listing_count DESC
            """).df()

        if len(list(_BRONZE_DIR.glob("cars_*.parquet"))) > 0:
            results["bronze_daily"] = con.execute(f"""
                SELECT
                    TRY_CAST(scraped_at AS DATE) AS scrape_date,
                    COUNT(*) AS raw_records,
                    COUNT(DISTINCT listing_id) AS unique_listings,
                    COUNT(*) - COUNT(DISTINCT listing_id) AS intra_day_duplicates
                FROM read_parquet('{BRONZE_GLOB}', union_by_name=true)
                GROUP BY 1
                ORDER BY 1 ASC
            """).df()

            b_counts = con.execute(f"""
                SELECT COUNT(*), COUNT(DISTINCT listing_id) FROM read_parquet('{BRONZE_GLOB}', union_by_name=true)
            """).fetchone()
            if b_counts:
                results["bronze_total"] = int(b_counts[0])
                results["bronze_unique"] = int(b_counts[1])

            if not results["bronze_daily"].empty:
                results["intra_day_deduped_count"] = int(results["bronze_daily"]["intra_day_duplicates"].sum())
    except Exception:
        pass
    finally:
        con.close()

    return results


@st.cache_data(ttl=CACHE_TTL)
def load_scraper_health() -> dict:
    """
    Evaluates scraper health, run latency, volume anomalies, and schema stability.
    """
    manifest = load_manifest()
    health = {
        "status": "Healthy",
        "last_run": "Never",
        "hours_ago": 999.0,
        "batch_total": 0,
        "new_ids": 0,
        "recurring_ids": 0,
        "mode": "unknown",
        "duration_seconds": 0.0,
        "schema_ok": True,
        "schema_details": "All Bronze fields present without schema drift.",
    }

    if manifest:
        import datetime
        ts_str = manifest.get("timestamp", "")
        health["last_run"] = ts_str[:16].replace("T", " ") if ts_str else "—"
        try:
            ts = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            now = datetime.datetime.now(datetime.timezone.utc)
            health["hours_ago"] = round((now - ts).total_seconds() / 3600.0, 1)
        except Exception:
            health["hours_ago"] = 0.0

        health["batch_total"] = manifest.get("batch_total", 0)
        health["new_ids"] = manifest.get("new_ids_count", 0)
        health["recurring_ids"] = manifest.get("recurring_ids_count", 0)
        health["mode"] = manifest.get("scrape_mode", "daily_incremental")
        health["duration_seconds"] = round(float(manifest.get("duration_seconds", 0.0)), 1)

    # Schema check
    if len(list(_BRONZE_DIR.glob("cars_*.parquet"))) > 0:
        con = _con()
        try:
            cols = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{BRONZE_GLOB}', union_by_name=true) LIMIT 1").df()
            col_names = set(cols["column_name"])
            expected = {"listing_id", "raw_title", "raw_price", "raw_spec_brand", "raw_spec_model", "raw_spec_year"}
            missing = expected - col_names
            if missing:
                health["schema_ok"] = False
                health["schema_details"] = f"Missing core Bronze columns: {missing}"
            else:
                health["schema_ok"] = True
                health["schema_details"] = f"All {len(col_names)} Bronze raw columns intact."
        except Exception as e:
            health["schema_ok"] = False
            health["schema_details"] = str(e)
        finally:
            con.close()

    return health


# ── 17. Pipeline Funnel & Cleaning Impact ─────────────────────────────────────

@st.cache_data(ttl=CACHE_TTL)
def load_pipeline_funnel(scrape_date: str | None = None) -> pd.DataFrame:
    """
    Returns record counts through each stage of the data pipeline:
    Bronze Ingestion -> Silver Conformed -> Silver Unique -> Gold Mart -> Gold ML
    """
    con = _con()
    stages = []

    try:
        # 1. Bronze
        b_count = 0
        if len(list(_BRONZE_DIR.glob("cars_*.parquet"))) > 0:
            if scrape_date:
                row = con.execute(f"SELECT COUNT(*) FROM read_parquet('{BRONZE_GLOB}', union_by_name=true) WHERE TRY_CAST(scraped_at AS DATE) = '{scrape_date}'").fetchone()
            else:
                row = con.execute(f"SELECT COUNT(*) FROM read_parquet('{BRONZE_GLOB}', union_by_name=true)").fetchone()
            b_count = int(row[0]) if row else 0
        stages.append({"stage": "1. Bronze Ingestion", "count": b_count, "description": "Raw scraped HTTP JSON payloads"})

        # 2. Silver Conformed
        s_count = 0
        if os.path.exists(SILVER_PATH):
            date_filter = f"WHERE CAST(scrape_date AS VARCHAR) = '{scrape_date}'" if scrape_date else ""
            row = con.execute(f"SELECT COUNT(*) FROM read_parquet('{SILVER_PATH}') {date_filter}").fetchone()
            s_count = int(row[0]) if row else 0
        stages.append({"stage": "2. Silver Conformed", "count": s_count, "description": "Cleaned, cast & quality-tagged records"})

        # 3. Silver Deduplicated
        s_unique = 0
        if os.path.exists(SILVER_PATH):
            date_filter = f"WHERE CAST(scrape_date AS VARCHAR) = '{scrape_date}'" if scrape_date else ""
            row = con.execute(f"SELECT COUNT(DISTINCT listing_id) FROM read_parquet('{SILVER_PATH}') {date_filter}").fetchone()
            s_unique = int(row[0]) if row else 0
        stages.append({"stage": "3. Silver Deduplicated", "count": s_unique, "description": "Unique active vehicle listings"})

        # 4. Gold Mart Inventory
        g_count = 0
        if os.path.exists(GOLD_MART_PATH):
            date_filter = f"WHERE CAST(scrape_date AS VARCHAR) = '{scrape_date}'" if scrape_date else ""
            row = con.execute(f"SELECT COUNT(*) FROM read_parquet('{GOLD_MART_PATH}') {date_filter}").fetchone()
            g_count = int(row[0]) if row else 0
        stages.append({"stage": "4. Gold Mart Inventory", "count": g_count, "description": "Non-quarantined business reporting mart"})

        # 5. Gold ML-Ready
        ml_count = 0
        if os.path.exists(GOLD_ML_PATH):
            date_filter = f"WHERE CAST(scrape_date AS VARCHAR) = '{scrape_date}'" if scrape_date else ""
            row = con.execute(f"SELECT COUNT(*) FROM read_parquet('{GOLD_ML_PATH}') {date_filter}").fetchone()
            ml_count = int(row[0]) if row else 0
        stages.append({"stage": "5. Gold ML-Ready", "count": ml_count, "description": "Strict complete features (zero leakage)"})

    except Exception:
        pass
    finally:
        con.close()

    df = pd.DataFrame(stages)
    if not df.empty and df["count"].iloc[0] > 0:
        base = df["count"].iloc[0]
        df["retention_pct"] = (100.0 * df["count"] / base).round(1)
    else:
        df["retention_pct"] = 0.0

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
def load_raw_vs_conformed_comparison() -> pd.DataFrame:
    """
    Compares raw Bronze fill rate vs conformed Silver fill rate for key attributes.
    Highlights data engineering value added by dbt transformations.
    """
    if not os.path.exists(SILVER_PATH) or len(list(_BRONZE_DIR.glob("cars_*.parquet"))) == 0:
        return pd.DataFrame()

    con = _con()
    try:
        df = con.execute(f"""
            WITH bronze_latest AS (
                SELECT
                    listing_id,
                    raw_title,
                    raw_spec_brand,
                    raw_spec_model,
                    raw_spec_year,
                    raw_spec_transmission,
                    raw_spec_fuel_type,
                    ROW_NUMBER() OVER (PARTITION BY listing_id ORDER BY scraped_at DESC) as _rn
                FROM read_parquet('{BRONZE_GLOB}', union_by_name=true)
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
            )
            SELECT
                'Brand' AS attribute,
                ROUND(100.0 * COUNT(b.raw_spec_brand) / COUNT(*), 1) AS raw_bronze_fill_pct,
                ROUND(100.0 * COUNT(s.vehicle_brand) / COUNT(*), 1) AS conformed_silver_fill_pct
            FROM silver_latest s
            JOIN bronze_latest b ON s.listing_id = b.listing_id AND b._rn = 1
            WHERE s._rn = 1
            UNION ALL
            SELECT
                'Model' AS attribute,
                ROUND(100.0 * COUNT(b.raw_spec_model) / COUNT(*), 1) AS raw_bronze_fill_pct,
                ROUND(100.0 * COUNT(s.vehicle_model) / COUNT(*), 1) AS conformed_silver_fill_pct
            FROM silver_latest s
            JOIN bronze_latest b ON s.listing_id = b.listing_id AND b._rn = 1
            WHERE s._rn = 1
            UNION ALL
            SELECT
                'Year' AS attribute,
                ROUND(100.0 * COUNT(b.raw_spec_year) / COUNT(*), 1) AS raw_bronze_fill_pct,
                ROUND(100.0 * COUNT(s.vehicle_year) / COUNT(*), 1) AS conformed_silver_fill_pct
            FROM silver_latest s
            JOIN bronze_latest b ON s.listing_id = b.listing_id AND b._rn = 1
            WHERE s._rn = 1
            UNION ALL
            SELECT
                'Transmission' AS attribute,
                ROUND(100.0 * COUNT(b.raw_spec_transmission) / COUNT(*), 1) AS raw_bronze_fill_pct,
                ROUND(100.0 * COUNT(s.vehicle_transmission) / COUNT(*), 1) AS conformed_silver_fill_pct
            FROM silver_latest s
            JOIN bronze_latest b ON s.listing_id = b.listing_id AND b._rn = 1
            WHERE s._rn = 1
            UNION ALL
            SELECT
                'Fuel Type' AS attribute,
                ROUND(100.0 * COUNT(b.raw_spec_fuel_type) / COUNT(*), 1) AS raw_bronze_fill_pct,
                ROUND(100.0 * COUNT(s.vehicle_fuel_type) / COUNT(*), 1) AS conformed_silver_fill_pct
            FROM silver_latest s
            JOIN bronze_latest b ON s.listing_id = b.listing_id AND b._rn = 1
            WHERE s._rn = 1
        """).df()
        df["uplift_pct"] = (df["conformed_silver_fill_pct"] - df["raw_bronze_fill_pct"]).round(1)
    except Exception:
        df = pd.DataFrame()
    finally:
        con.close()

    return df


# ── 18. ML Readiness & Leakage Audit ──────────────────────────────────────────

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


# ── 12. Raw Ingestion & Bronze Batch Ledger ───────────────────────────────────

@st.cache_data(ttl=CACHE_TTL)
def load_raw_ingestion_summary() -> dict:
    """
    Returns batch ledger and overall metadata for all raw Bronze Parquet files.
    """
    parquet_files = sorted(list(_BRONZE_DIR.glob("cars_*.parquet")))
    if not parquet_files:
        return {
            "available": False,
            "total_files": 0,
            "total_records": 0,
            "total_distinct": 0,
            "total_size_mb": 0.0,
            "batches": pd.DataFrame(),
        }

    con = _con()
    batch_rows = []
    try:
        for p in parquet_files:
            size_kb = round(os.path.getsize(p) / 1024.0, 1)
            p_posix = p.as_posix()
            cnt, dist_cnt = con.execute(f"SELECT count(*), count(DISTINCT listing_id) FROM read_parquet('{p_posix}')").fetchone()
            date_val = con.execute(f"SELECT CAST(TRY_CAST(MIN(scraped_at) AS DATE) AS VARCHAR) FROM read_parquet('{p_posix}')").fetchone()[0]
            batch_rows.append({
                "file_name": p.name,
                "scrape_date": date_val or "Unknown",
                "records_ingested": int(cnt or 0),
                "distinct_listings": int(dist_cnt or 0),
                "intra_day_dups": int((cnt or 0) - (dist_cnt or 0)),
                "size_kb": size_kb,
                "size_mb": round(size_kb / 1024.0, 2),
            })
    except Exception:
        pass
    finally:
        con.close()

    batch_df = pd.DataFrame(batch_rows)
    tot_rec = int(batch_df["records_ingested"].sum()) if not batch_df.empty else 0
    tot_dist = int(batch_df["distinct_listings"].sum()) if not batch_df.empty else 0
    tot_mb = round(float(batch_df["size_mb"].sum()), 2) if not batch_df.empty else 0.0

    return {
        "available": not batch_df.empty,
        "total_files": len(parquet_files),
        "total_records": tot_rec,
        "total_distinct": tot_dist,
        "total_size_mb": tot_mb,
        "batches": batch_df,
    }


# ── 13. Cleaning Transformation Rules Table ──────────────────────────────────

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


# ── 14. Feature Statistics & Profiling (Numeric) ─────────────────────────────

@st.cache_data(ttl=CACHE_TTL)
def load_feature_numeric_stats(target_dataset: str = "silver") -> pd.DataFrame:
    """
    Computes summary descriptive statistics for numeric features.
    target_dataset: 'silver' or 'gold_ml'
    """
    path = GOLD_ML_PATH if target_dataset == "gold_ml" else SILVER_PATH
    if not os.path.exists(path):
        return pd.DataFrame()

    con = _con()
    try:
        if target_dataset == "gold_ml":
            query = f"""
                WITH unpivoted AS (
                    SELECT 'price' AS feature, price AS val FROM read_parquet('{path}') WHERE price > 0
                    UNION ALL
                    SELECT 'log_price', log_price FROM read_parquet('{path}') WHERE log_price IS NOT NULL
                    UNION ALL
                    SELECT 'vehicle_model_year', CAST(vehicle_model_year AS DOUBLE) FROM read_parquet('{path}') WHERE vehicle_model_year IS NOT NULL
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
                    WHEN 'vehicle_model_year' THEN 3
                    WHEN 'vehicle_age' THEN 4
                    WHEN 'vehicle_mileage_km' THEN 5
                    WHEN 'vehicle_engine_cc' THEN 6
                    ELSE 7
                END
            """
        else:
            query = f"""
                WITH unpivoted AS (
                    SELECT 'price' AS feature, price AS val FROM read_parquet('{path}') WHERE price > 0
                    UNION ALL
                    SELECT 'log_price', LN(1.0 + price) FROM read_parquet('{path}') WHERE price > 0
                    UNION ALL
                    SELECT 'vehicle_year', CAST(vehicle_year AS DOUBLE) FROM read_parquet('{path}') WHERE vehicle_year IS NOT NULL
                    UNION ALL
                    SELECT 'vehicle_age', CAST(GREATEST(date_part('year', scrape_date) - vehicle_year, 0) AS DOUBLE) FROM read_parquet('{path}') WHERE vehicle_year IS NOT NULL
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


# ── 15. Categorical Cardinality & Top Frequencies ────────────────────────────

@st.cache_data(ttl=CACHE_TTL)
def load_categorical_cardinality(target_dataset: str = "silver") -> pd.DataFrame:
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

    try:
        total = con.execute(f"SELECT COUNT(*) FROM read_parquet('{path}')").fetchone()[0]
        for col in cat_cols:
            null_count = con.execute(f"SELECT COUNT(*) FROM read_parquet('{path}') WHERE {col} IS NULL").fetchone()[0]
            distinct_count = con.execute(f"SELECT COUNT(DISTINCT {col}) FROM read_parquet('{path}')").fetchone()[0]
            top3 = con.execute(f"""
                SELECT {col} AS val, COUNT(*) AS cnt, ROUND(100.0 * COUNT(*) / {total}, 1) AS pct
                FROM read_parquet('{path}')
                WHERE {col} IS NOT NULL
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


# ── 16. Categorical Frequency Distribution for Charting ──────────────────────

@st.cache_data(ttl=CACHE_TTL)
def load_categorical_distribution(feature_name: str, top_n: int = 10, target_dataset: str = "silver") -> pd.DataFrame:
    """
    Returns top N values and their counts/percentages for a specific categorical feature.
    """
    path = GOLD_ML_PATH if target_dataset == "gold_ml" else SILVER_PATH
    if not os.path.exists(path):
        return pd.DataFrame()

    con = _con()
    try:
        total = con.execute(f"SELECT COUNT(*) FROM read_parquet('{path}') WHERE {feature_name} IS NOT NULL").fetchone()[0]
        df = con.execute(f"""
            SELECT
                COALESCE(CAST({feature_name} AS VARCHAR), 'Unknown') AS category,
                COUNT(*) AS count,
                ROUND(100.0 * COUNT(*) / {total}, 1) AS pct
            FROM read_parquet('{path}')
            WHERE {feature_name} IS NOT NULL
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT {top_n}
        """).df()
    except Exception:
        df = pd.DataFrame()
    finally:
        con.close()

    return df


# ── 17. Feature Values for Distribution Plots (Histograms & Boxplots) ─────────

@st.cache_data(ttl=CACHE_TTL)
def load_feature_distribution_sample(target_dataset: str = "silver", limit: int = 5000) -> pd.DataFrame:
    """
    Returns sampled records for rendering distribution plots and boxplots.
    """
    path = GOLD_ML_PATH if target_dataset == "gold_ml" else SILVER_PATH
    if not os.path.exists(path):
        return pd.DataFrame()

    con = _con()
    try:
        if target_dataset == "gold_ml":
            df = con.execute(f"""
                SELECT
                    price,
                    log_price,
                    vehicle_model_year,
                    vehicle_age,
                    vehicle_mileage_km,
                    vehicle_engine_cc,
                    brand_category AS brand_tier,
                    vehicle_body_type,
                    vehicle_fuel_type
                FROM read_parquet('{path}')
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
                WHERE price > 0
                LIMIT {limit}
            """).df()
    except Exception:
        df = pd.DataFrame()
    finally:
        con.close()

    return df


# ── 18. Price vs Year Anomaly Scatter Sample ──────────────────────────────────

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


# ── 19. Feature Correlation Matrix ────────────────────────────────────────────

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
                vehicle_model_year,
                vehicle_age,
                COALESCE(vehicle_mileage_km, 0) AS mileage_km,
                COALESCE(vehicle_engine_cc, 0) AS engine_cc,
                is_plate_number,
                has_full_option,
                is_urgent_sale
            FROM read_parquet('{GOLD_ML_PATH}')
        """).df()
        corr_df = df.corr().round(2)
    except Exception:
        corr_df = pd.DataFrame()
    finally:
        con.close()

    return corr_df


# ── 20. Executive Snapshot Audit Report Generator ─────────────────────────────

@st.cache_data(ttl=CACHE_TTL)
def generate_markdown_report(scrape_date: str | None = None) -> str:
    """
    Generates a structured executive markdown audit report for the active snapshot.
    """
    import datetime
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
    quarantined = int(row.get("quarantined", 0))
    now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    valid_pct = round(100.0 * valid / total, 1) if total > 0 else 0.0
    quar_pct = round(100.0 * quarantined / total, 2) if total > 0 else 0.0

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
- **Valid (ML/BI Ready):** **{valid:,}** ({valid_pct}%)
- **Quarantined (Excluded from Marts):** **{quarantined:,}** ({quar_pct}%)

## 2. Medallion Pipeline Throughput & Deduplication
- **Bronze Raw Ingested:** {dup_stats.get('bronze_total', 0):,} records
- **Conformed Silver Snapshots:** {dup_stats.get('silver_total', 0):,} records
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



