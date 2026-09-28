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
MODELS_DIR      = _HERE / "models"

CACHE_TTL = 3600  # 1 hour


def _con() -> duckdb.DuckDBPyConnection:
    """Return a fresh in-memory DuckDB connection (cheap; no state shared across calls)."""
    return duckdb.connect(database=":memory:", read_only=False)


def build_date_filter(scrape_date: str | None, alias: str = "") -> str:
    """Return a SQL AND-clause for a scrape_date partition filter, or empty string."""
    col = f"{alias}.scrape_date" if alias else "scrape_date"
    if scrape_date:
        return f"AND CAST({col} AS VARCHAR) = '{scrape_date}'"
    return ""


def build_filter_sql(
    brands: list[str] | None = None,
    models: list[str] | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    fuels: list[str] | None = None,
    transmissions: list[str] | None = None,
    vehicle_types: list[str] | None = None,
    provinces: list[str] | None = None,
    scrape_date: str | None = None,
    canonical_only: bool = False,
    **_kwargs: Any,
) -> str:
    """
    Build a safe SQL WHERE/AND clause from validated filter parameters.
    All string lists are sanitized (single-quote escaped) before interpolation.
    Returns a string starting with 'AND ...' (empty string if no filters).
    """
    parts: list[str] = []

    def _quote_list(values: list[str]) -> str:
        safe = [v.replace("'", "''") for v in values]
        return "(" + ", ".join(f"'{v}'" for v in safe) + ")"

    if canonical_only:
        parts.append("is_canonical_vehicle = 1")
    if brands:
        parts.append(f"vehicle_brand IN {_quote_list(brands)}")
    if models:
        parts.append(f"vehicle_model IN {_quote_list(models)}")
    if year_min is not None:
        parts.append(f"vehicle_year >= {int(year_min)}")
    if year_max is not None:
        parts.append(f"vehicle_year <= {int(year_max)}")
    if price_min is not None:
        parts.append(f"price >= {float(price_min)}")
    if price_max is not None:
        parts.append(f"price <= {float(price_max)}")
    if fuels:
        parts.append(f"vehicle_fuel_type IN {_quote_list(fuels)}")
    if transmissions:
        parts.append(f"vehicle_transmission IN {_quote_list(transmissions)}")
    if vehicle_types:
        parts.append(f"vehicle_body_type IN {_quote_list(vehicle_types)}")
    if provinces:
        parts.append(f"province IN {_quote_list(provinces)}")
    if scrape_date:
        parts.append(f"CAST(scrape_date AS VARCHAR) = '{scrape_date}'")

    return ("AND " + " AND ".join(parts)) if parts else ""
