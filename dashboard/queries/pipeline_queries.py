"""
dashboard/queries/pipeline_queries.py
=====================================
Bronze raw ingestion volumes, scraper health, deduplication, and pipeline funnel.
"""
from __future__ import annotations

import json
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
    GOLD_MART_PATH,
    GOLD_ML_PATH,
    MANIFEST_PATH,
    SILVER_PATH,
)
from dashboard.queries.core_queries import load_manifest

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
def load_raw_ingestion_summary() -> dict:
    """
    Returns batch ledger and overall metadata for all raw Bronze Parquet files.
    """
    parquet_files = sorted(list(_BRONZE_DIR.glob("cars_*.parquet")), reverse=True)
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
            cnt, dist_cnt, date_val = con.execute(f"""
                SELECT count(*), count(DISTINCT listing_id), CAST(TRY_CAST(MIN(scraped_at) AS DATE) AS VARCHAR)
                FROM read_parquet('{p_posix}')
            """).fetchone()
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

