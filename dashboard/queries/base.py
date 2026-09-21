"""
dashboard/queries/base.py
=========================
Shared paths, cache constants, and DuckDB connection helper for dashboard queries.
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb
import streamlit as st

# ── Paths (relative to project root, resolved at import time) ──────────────────
_HERE = Path(__file__).parent.parent.parent  # project root
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
