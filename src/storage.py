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


# ── Parquet ────────────────────────────────────────────────────────────────────

def save_to_parquet(
    listings: List[AdListingModel],
    filename: str = PARQUET_FILENAME,
    directory: str = RAW_DATA_DIR,
) -> str:
    """
    Serialize all ``AdListingModel`` records to a Parquet file.

    List/dict columns (``phone_numbers``, ``specs``) are JSON-encoded so the
    Parquet schema stays flat and portable across tools.

    Returns the path to the written file.
    """
    _ensure_dir(directory)
    path = os.path.join(directory, filename)

    rows = [item.model_dump() for item in listings]
    df = pd.DataFrame(rows)

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


# ── CSV sample ─────────────────────────────────────────────────────────────────

# Columns written to the CSV sample — human-readable subset, no raw blobs
_CSV_COLUMNS = [
    "listing_id",
    "listing_title",
    "price",
    "currency",
    "vehicle_model_year",
    "vehicle_condition",
    "vehicle_tax_type",
    "vehicle_brand",
    "vehicle_model",
    "vehicle_mileage_km",
    "vehicle_fuel_type",
    "vehicle_transmission",
    "vehicle_engine_cc",
    "vehicle_color",
    "province",
    "district",
    "seller_type",
    "view_count",
    "posted_at",
    "scraped_at",
    "is_premium",
    "listing_url",
]


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

    # Keep only columns that exist in this DataFrame
    cols = [c for c in _CSV_COLUMNS if c in df.columns]
    df_sample = df[cols]

    # Random sample (seed fixed for reproducibility); cap at total available
    sample_size = min(n, len(df_sample))
    df_sample = df_sample.sample(n=sample_size, random_state=42).reset_index(drop=True)

    df_sample.to_csv(path, index=False, encoding="utf-8-sig")  # utf-8-sig for Excel compat
    logger.info(f"Saved {sample_size}-row CSV sample -> {path}")
    return path
