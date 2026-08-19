# src/storage.py — Parquet & CSV persistence for AdListingModel records

import json
import logging
import os
from typing import List, Literal

import pandas as pd

from src.config import RAW_DATA_DIR, PARQUET_FILENAME
from src.schemas import AdListingModel

logger = logging.getLogger(__name__)

SampleSize = Literal[30, 60]


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


# ── Column Ordering (Logical grouping with zero renaming) ──────────────────────

REORDERED_COLUMNS: List[str] = [
    # 1. Identity & Title
    "listing_id",
    "listing_title",
    # 2. Target Variable & Pricing
    "price",
    "currency",
    "discount_price",
    # 3. Core Car Specs (ML Features)
    "vehicle_brand",
    "vehicle_model",
    "vehicle_model_year",
    "vehicle_condition",
    "vehicle_tax_type",
    "vehicle_transmission",
    "vehicle_fuel_type",
    "vehicle_mileage_km",
    "vehicle_engine_cc",
    "vehicle_color",
    # 4. Location & Category
    "province",
    "district",
    "location_full",
    "category",
    "category_slug",
    "province_slug",
    # 5. Seller & Engagement
    "seller_id",
    "seller_name",
    "seller_type",
    "seller_username",
    "seller_phones",
    "view_count",
    "is_premium",
    # 6. Timestamps
    "posted_at",
    "renewed_at",
    "scraped_at",
    # 7. URLs & Raw Payloads
    "thumbnail_url",
    "listing_url",
    "raw_specs",
]


def reorder_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Reorder DataFrame columns logically without renaming any column."""
    ordered = [c for c in REORDERED_COLUMNS if c in df.columns]
    extra = [c for c in df.columns if c not in REORDERED_COLUMNS]
    return df[ordered + extra]


# ── Parquet ────────────────────────────────────────────────────────────────────

def save_to_parquet(
    listings: List[AdListingModel],
    filename: str = PARQUET_FILENAME,
    directory: str = RAW_DATA_DIR,
) -> str:
    """
    Serialize all ``AdListingModel`` records to a Parquet file with logical column ordering.

    List/dict columns (``phone_numbers``, ``specs``) are JSON-encoded so the
    Parquet schema stays flat and portable across tools.

    Returns the path to the written file.
    """
    _ensure_dir(directory)
    path = os.path.join(directory, filename)

    rows = [item.model_dump() for item in listings]
    df = pd.DataFrame(rows)

    # Reorder columns into logical groups
    df = reorder_columns(df)

    # Parquet cannot store arbitrary Python objects — serialize known complex columns to JSON.
    # Only target columns that are expected to hold lists or dicts (avoids scanning all columns).
    _COMPLEX_COLS = {"seller_phones", "raw_specs"}
    for col in _COMPLEX_COLS:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: json.dumps(x) if isinstance(x, (list, dict)) else x
            )

    df.to_parquet(path, index=False)
    logger.info(f"Saved {len(df)} records to Parquet -> {path}")
    return path


def load_from_parquet(
    filename: str = PARQUET_FILENAME,
    directory: str = RAW_DATA_DIR,
) -> pd.DataFrame:
    """
    Load listings from an existing Parquet file, restoring serialized columns.
    """
    path = os.path.join(directory, filename)
    df = pd.read_parquet(path)

    # Restore list/dict columns from JSON strings
    for col in ("seller_phones", "raw_specs", "phone_numbers", "specs"):
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: json.loads(x)
                if isinstance(x, str) and x.startswith(("[", "{"))
                else x
            )
    return df


def load_all_parquet(directory: str = RAW_DATA_DIR) -> pd.DataFrame:
    """
    Load and concatenate all raw Parquet files from `directory` (including subdirectories).
    Restores serialized complex columns (JSON strings -> python objects).
    """
    import glob
    files = sorted(
        set(
            glob.glob(os.path.join(directory, "**", "*.parquet"), recursive=True)
            + glob.glob(os.path.join(directory, "*.parquet"))
        )
    )
    if not files:
        logger.warning(f"No Parquet files found in {directory}")
        return pd.DataFrame()

    dfs = []
    for f in files:
        try:
            df = pd.read_parquet(f)
            dfs.append(df)
        except Exception as exc:
            logger.warning(f"Could not load {f}: {exc}")

    if not dfs:
        return pd.DataFrame()

    combined = pd.concat(dfs, ignore_index=True)
    for col in ("seller_phones", "raw_specs", "phone_numbers", "specs"):
        if col in combined.columns:
            combined[col] = combined[col].apply(
                lambda x: json.loads(x)
                if isinstance(x, str) and x.startswith(("[", "{"))
                else x
            )
    return combined

def save_sample_csv(
    listings: List[AdListingModel],
    n: SampleSize = 30,
    directory: str = RAW_DATA_DIR,
) -> str:
    """
    Save a random sample of ``n`` listings (30 or 60) to a CSV file.

    Only the human-readable columns are included — large blobs like ``specs``
    and ``phone_numbers`` are omitted to keep the CSV clean and easy to open
    in Excel / Google Sheets.

    Args:
        listings: Full list of scraped ``AdListingModel`` records.
        n:        Sample size — either ``30`` or ``60``.
        directory: Output directory (default: ``data/raw/``).

    Returns:
        Path to the written CSV file.
    """
    if n not in (30, 60):
        raise ValueError(f"Sample size must be 30 or 60, got {n}")

    _ensure_dir(directory)
    filename = f"khmer24_cars_sample_{n}.csv"
    path = os.path.join(directory, filename)

    df = pd.DataFrame([item.model_dump() for item in listings])
    df = reorder_columns(df)

    # Random sample (seed fixed for reproducibility); cap at total available
    sample_size = min(n, len(df))
    df_sample = df.sample(n=sample_size, random_state=42).reset_index(drop=True)

    df_sample.to_csv(path, index=False, encoding="utf-8-sig")  # utf-8-sig for Excel compat
    logger.info(f"Saved {sample_size}-row CSV sample -> {path}")
    return path
