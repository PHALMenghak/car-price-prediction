"""
dashboard/queries/core_queries.py
=================================
Pipeline metadata, dbt test execution health, and snapshot dates.
"""
from __future__ import annotations

import json
import os
import streamlit as st

from dashboard.queries.base import (
    _con,
    CACHE_TTL,
    DBT_RUN_RESULTS,
    MANIFEST_PATH,
    SILVER_PATH,
)

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

