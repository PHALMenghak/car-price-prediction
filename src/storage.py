# src/storage.py — Parquet & CSV persistence for RawCarListing records
# Stores structured raw data in Bronze layer without transformation.

import glob
import json
import logging
import os
from typing import Any, Dict, List, Optional, Set

import pandas as pd
import pyarrow.parquet as pq

from src.config import BRONZE_DATA_DIR, PARQUET_FILENAME, RAW_CSV_FILENAME
from src.schemas import RawCarListing

logger = logging.getLogger(__name__)


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


# ── Column Ordering (Logical grouping of structured raw data) ─────────────────

REORDERED_COLUMNS: List[str] = [
    # 1. Identity & Pricing
    "listing_id",
    "raw_title",
    "raw_price",
    "raw_currency",
    # 2. Raw Vehicle Specs (Direct from Detail Page / Feed)
    "raw_spec_brand",
    "raw_spec_model",
    "raw_spec_year",
    "raw_spec_mileage",
    "raw_spec_engine_size",
    "raw_spec_fuel_type",
    "raw_spec_transmission",
    "raw_spec_color",
    "raw_spec_condition",
    "raw_spec_tax_type",
    "raw_spec_body_type",
    # 3. Location
    "raw_province",
    "raw_district",
    # 4. Seller & Contact
    "seller_id",
    "seller_name",
    "seller_type_code",
    "seller_username",
    "seller_phones",
    # 5. Content & Media
    "raw_description",
    "thumbnail_url",
    "listing_url",
    "images",
    # 6. Timestamps & Lineage
    "posted_at",
    "renewed_at",
    "scraped_at",
    "detail_source",
    "has_detail",
    # 7. Audit Blobs
    "raw_feed_payload",
    "raw_detail_payload",
]

_COMPLEX_COLS = {"seller_phones", "images", "raw_specs"}


def reorder_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Reorder DataFrame columns logically without dropping any column."""
    ordered = [c for c in REORDERED_COLUMNS if c in df.columns]
    extra = [c for c in df.columns if c not in REORDERED_COLUMNS]
    return df[ordered + extra]


# ── Fast Historical ID Discovery ───────────────────────────────────────────────

def get_historical_ids(directory: str = BRONZE_DATA_DIR) -> Set[str]:
    """
    Fast discovery of all historical unique listing IDs across all Parquet files.
    Reads only the ID column (zero full-data loading) for optimal performance.
    """
    files = sorted(
        set(
            glob.glob(os.path.join(directory, "**", "*.parquet"), recursive=True)
            + glob.glob(os.path.join(directory, "*.parquet"))
        )
    )
    historical_ids: Set[str] = set()

    for fpath in files:
        try:
            schema = pq.read_schema(fpath)
            target_col = None
            for col in ("listing_id", "id"):
                if col in schema.names:
                    target_col = col
                    break
            if target_col:
                df_part = pd.read_parquet(fpath, columns=[target_col])
                historical_ids.update(df_part[target_col].dropna().astype(str).tolist())
            else:
                df_part = pd.read_parquet(fpath)
                for col in ("listing_id", "id"):
                    if col in df_part.columns:
                        historical_ids.update(df_part[col].dropna().astype(str).tolist())
                        break
        except Exception as exc:
            logger.warning(f"Could not read IDs from {fpath}: {exc}")

    return historical_ids


# ── Parquet & Full CSV Persistence ─────────────────────────────────────────────

def save_to_parquet(
    listings: List[RawCarListing],
    filename: str = PARQUET_FILENAME,
    directory: str = BRONZE_DATA_DIR,
) -> str:
    """
    Serialize all ``RawCarListing`` records to a Bronze Parquet file with logical column ordering.
    """
    _ensure_dir(directory)
    path = os.path.join(directory, filename)

    rows = [item.model_dump() for item in listings]
    df = pd.DataFrame(rows)
    df = reorder_columns(df)

    # Exclude massive raw audit payloads from Parquet file to keep files lightweight (<1MB) and avoid GitHub's 100MB limit
    drop_from_parquet = [c for c in ("raw_feed_payload", "raw_detail_payload") if c in df.columns]
    df = df.drop(columns=drop_from_parquet)

    for col in _COMPLEX_COLS:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: json.dumps(x) if isinstance(x, (list, dict)) else x
            )

    df.to_parquet(path, index=False)
    logger.info(f"Saved {len(df)} raw records to Parquet -> {path}")
    return path


def save_to_csv(
    listings: List[RawCarListing],
    filename: str = RAW_CSV_FILENAME,
    directory: str = BRONZE_DATA_DIR,
) -> str:
    """
    Serialize 100% of today's scraped ``RawCarListing`` records to a single full Bronze CSV file
    for fast human inspection and review.
    Uses UTF-8 with BOM (utf-8-sig) to guarantee Khmer Unicode renders properly in Excel.
    """
    _ensure_dir(directory)
    path = os.path.join(directory, filename)

    rows = [item.model_dump() for item in listings]
    df = pd.DataFrame(rows)
    df = reorder_columns(df)

    # Exclude massive raw audit payloads from CSV inspection if present
    drop_from_csv = [c for c in ("raw_feed_payload", "raw_detail_payload") if c in df.columns]
    df_csv = df.drop(columns=drop_from_csv)

    # Convert complex collections to readable string representations
    for col in _COMPLEX_COLS:
        if col in df_csv.columns:
            df_csv[col] = df_csv[col].apply(
                lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, (list, dict)) else x
            )

    df_csv.to_csv(path, index=False, encoding="utf-8-sig")
    logger.info(f"Saved {len(df_csv)} full raw records from today's run to CSV -> {path}")
    return path


def save_sample_csv(
    listings: List[RawCarListing],
    n: int = 60,
    directory: str = BRONZE_DATA_DIR,
) -> str:
    """
    Backward-compatible alias for saving CSV data.
    """
    return save_to_csv(listings, filename=RAW_CSV_FILENAME, directory=directory)


_JSON_RESTORE_COLS = ("seller_phones", "images", "raw_specs", "phone_numbers")


def _restore_json_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Restore list/dict columns from JSON strings back to Python objects."""
    for col in _JSON_RESTORE_COLS:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: json.loads(x)
                if isinstance(x, str) and x.startswith(("[", "{"))
                else x
            )
    return df


def load_from_parquet(
    filename: str = PARQUET_FILENAME,
    directory: str = BRONZE_DATA_DIR,
) -> pd.DataFrame:
    """Load listings from an existing Bronze Parquet file."""
    path = os.path.join(directory, filename)
    df = pd.read_parquet(path)
    return _restore_json_columns(df)


def load_all_parquet(directory: str = BRONZE_DATA_DIR) -> pd.DataFrame:
    """Load and concatenate all raw Parquet files from `directory`."""
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
    return _restore_json_columns(combined)


def save_run_manifest(
    manifest_data: Dict[str, Any],
    filename: str = "ingestion_manifest.json",
    directory: str = BRONZE_DATA_DIR,
) -> str:
    """Save run metadata and metrics to a JSON manifest for auditability."""
    _ensure_dir(directory)
    path = os.path.join(directory, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved ingestion run manifest -> {path}")
    return path
