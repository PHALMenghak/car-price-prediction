# src/cleaning.py — Data cleaning for raw Khmer24 car listings
#
# Takes a raw scraped DataFrame and applies quality rules to produce
# a clean, analysis-ready dataset. Feature engineering lives separately
# in pipeline/transform.py (Phase 2+).

import logging
from typing import Optional

from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)

CURRENT_YEAR = datetime.now().year

def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply data-quality rules to the raw scraped DataFrame.

    Rules
    -----
    1. Drop rows with no price (target variable is required for modeling).
    2. Remove price outliers outside $500 – $300,000.
    3. Drop rows with impossible car years (keep 1990 – current_year + 1).
    4. Standardize ``vehicle_condition`` to lowercase & fill missing → "used".
    5. Fill missing ``vehicle_tax_type``      → "Unknown".
    6. Fill missing ``vehicle_brand``         → "Unknown".
    7. Fill missing ``province``              → "Unknown".
    8. Fill missing ``vehicle_transmission``  → "Unknown".
    9. Fill missing ``vehicle_fuel_type``     → "Unknown".
    10. Deduplicate by ``listing_id`` (keep first occurrence).

    Parameters
    ----------
    df : pd.DataFrame
        Raw DataFrame built from ``AdListingModel.model_dump()`` records.

    Returns
    -------
    pd.DataFrame
        Cleaned DataFrame with reset index.
    """
    df = df.copy()
    initial = len(df)

    # Rule 1 — price must exist
    df = df.dropna(subset=["price"])
    logger.info(f"Rule 1 (no price)     : removed {initial - len(df):>4}  | remaining {len(df)}")

    # Rule 2 — price sanity bounds
    before = len(df)
    df = df[(df["price"] >= 500) & (df["price"] <= 300_000)]
    logger.info(f"Rule 2 (price bounds) : removed {before - len(df):>4}  | remaining {len(df)}")

    # Rule 3 — car year sanity bounds (allow null years to pass through)
    year_col = "vehicle_model_year" if "vehicle_model_year" in df.columns else ("car_year" if "car_year" in df.columns else None)
    if year_col:
        before = len(df)
        df = df[
            df[year_col].between(1990, CURRENT_YEAR + 1, inclusive="both")
            | df[year_col].isna()
        ]
        logger.info(f"Rule 3 (year bounds)  : removed {before - len(df):>4}  | remaining {len(df)}")

    # Rules 4-9 — standardize / fill string fields
    _fill_str(df, "vehicle_condition" if "vehicle_condition" in df.columns else "car_condition", default="used", lower=True)
    _fill_str(df, "vehicle_tax_type" if "vehicle_tax_type" in df.columns else "tax_type", default="Unknown")
    _fill_str(df, "vehicle_brand", default="Unknown")
    _fill_str(df, "province", default="Unknown")
    _fill_str(df, "vehicle_transmission" if "vehicle_transmission" in df.columns else "transmission", default="Unknown")
    _fill_str(df, "vehicle_fuel_type" if "vehicle_fuel_type" in df.columns else "fuel_type", default="Unknown")

    # Rule 10 — remove duplicates
    id_col = "listing_id" if "listing_id" in df.columns else ("id" if "id" in df.columns else None)
    if id_col:
        before = len(df)
        df = df.drop_duplicates(subset=[id_col])
        logger.info(f"Rule 10 (duplicates)  : removed {before - len(df):>4}  | remaining {len(df)}")

    logger.info(f"Cleaning complete: {initial} -> {len(df)} rows ({initial - len(df)} removed total)")
    return df.reset_index(drop=True)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fill_str(df: pd.DataFrame, col: str, default: str, lower: bool = False) -> None:
    """In-place: standardize and fill missing values in a string column."""
    if col not in df.columns:
        return
    if lower:
        df[col] = df[col].str.lower().str.strip()
    df[col] = df[col].fillna(default)
