# pipeline/transform.py — Data Cleaning, Preprocessing & Feature Engineering Pipeline
#
# Implements the Medallion Architecture:
#   Bronze (Raw Parquet) → Silver (Clean & Dedup) → Gold (ML Features)
#
# Entry point: run() or cli_main()
# Consumes:    data/raw/cars_*.parquet
# Produces:    data/processed/cars_train.parquet + cars_test.parquet
#              data/processed/preprocessing_manifest.json

import argparse
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from src.config import PROCESSED_DATA_DIR, RAW_DATA_DIR
from src.parsers import extract_brand_model
from src.storage import load_all_parquet

logger = logging.getLogger(__name__)

CURRENT_YEAR = datetime.now().year

# ── Brand Tier Sets ───────────────────────────────────────────────────────────

LUXURY_BRANDS: Set[str] = {
    "Lexus", "Mercedes-Benz", "BMW", "Porsche", "Land Rover",
    "Audi", "Cadillac", "Rolls-Royce", "Bentley", "Maserati",
    "Lamborghini", "Ferrari", "Aston Martin", "Genesis",
}

POPULAR_BRANDS: Set[str] = {
    "Toyota", "Lexus", "Ford", "Hyundai", "Mazda",
    "Kia", "Honda", "Mitsubishi", "Nissan", "Suzuki",
}

CHINESE_EV_BRANDS: Set[str] = {
    "BYD", "MG", "Geely", "Haval", "GAC", "Jetour", "Changan",
    "Denza", "Fangchengbao", "Xpeng", "NIO", "Li Auto", "Zeekr",
    "Avatr", "iCar", "Chery", "GTV", "ZNA", "Arcfox", "Hongqi",
    "Tank", "Dongfeng", "BAIC", "Wuling", "Foton", "DFSK",
    "Omoda", "Jaecoo", "Yangwang",
}

TIER_1_PROVINCES: Set[str] = {"Phnom Penh"}
TIER_2_PROVINCES: Set[str] = {
    "Siem Reap", "Battambang", "Kandal", "Preah Sihanouk", "Kampong Cham",
}


# ═══════════════════════════════════════════════════════════════════════════════
#  SILVER LAYER: Deduplication, Sanity Filtering, Brand Re-Extraction
# ═══════════════════════════════════════════════════════════════════════════════

def deduplicate_snapshots(df: pd.DataFrame) -> pd.DataFrame:
    """
    Multi-day deduplication: keep latest snapshot per listing_id.

    Before deduplication, extracts historical change signals across all snapshots:
    - days_on_market: (max(scraped_at) - min(posted_at)).days
    - initial_price / price_drop_amount / has_price_drop
    - view_velocity: view_count / max(days_on_market, 1)
    """
    if "listing_id" not in df.columns or "scraped_at" not in df.columns:
        logger.warning("Missing listing_id or scraped_at — skipping deduplication.")
        df["days_on_market"] = 0.0
        df["initial_price"] = df.get("price", np.nan)
        df["price_drop_amount"] = 0.0
        df["has_price_drop"] = 0
        df["view_velocity"] = 0.0
        return df

    n_before = len(df)
    df = df.copy()

    # Parse timestamps
    df["_scraped_dt"] = pd.to_datetime(df["scraped_at"], errors="coerce", utc=True)
    df["_posted_dt"] = pd.to_datetime(df["posted_at"], errors="coerce", utc=True)

    # Sort for deterministic first/last
    df = df.sort_values(["listing_id", "_scraped_dt"])

    # ── Historical aggregates per listing ──────────────────────────────────
    grp = df.groupby("listing_id", sort=False)

    hist = grp.agg(
        _min_posted=("_posted_dt", "min"),
        _max_scraped=("_scraped_dt", "max"),
        _first_price=("price", "first"),
        _last_price=("price", "last"),
    )

    hist["days_on_market"] = (
        (hist["_max_scraped"] - hist["_min_posted"])
        .dt.total_seconds()
        .div(86400.0)
        .clip(lower=0)
        .fillna(0)
    )
    hist["initial_price"] = hist["_first_price"]
    hist["price_drop_amount"] = (hist["_first_price"] - hist["_last_price"]).clip(lower=0).fillna(0)
    hist["has_price_drop"] = (hist["price_drop_amount"] > 0).astype(int)

    hist_cols = ["days_on_market", "initial_price", "price_drop_amount", "has_price_drop"]

    # ── Keep the latest snapshot per listing ────────────────────────────────
    df = df.drop_duplicates(subset="listing_id", keep="last")

    # Merge historical features
    df = df.merge(hist[hist_cols], on="listing_id", how="left")

    # View velocity
    vc = pd.to_numeric(df["view_count"], errors="coerce").fillna(0)
    dom = df["days_on_market"].clip(lower=1)
    df["view_velocity"] = (vc / dom).round(2)

    # Cleanup temp columns
    df = df.drop(columns=["_scraped_dt", "_posted_dt"], errors="ignore")

    n_after = len(df)
    logger.info(
        f"Deduplication: {n_before:,} snapshots → {n_after:,} unique listings "
        f"(removed {n_before - n_after:,} duplicate snapshots)."
    )
    return df.reset_index(drop=True)


def apply_sanity_filters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove invalid / extreme records that would harm model training.

    Rules:
    1. Drop rows with null or non-positive price
    2. Retain only $500 ≤ price ≤ $300,000
    3. Model year between 1990 and current_year + 1 (or null)
    4. Mileage 0–500,000 (out-of-range → NaN)
    5. Engine CC 500–7,000 (out-of-range → NaN)
    """
    n_before = len(df)
    df = df.copy()

    # ── Price filters ──────────────────────────────────────────────────────
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df.dropna(subset=["price"])
    df = df[df["price"] > 0]
    df = df[(df["price"] >= 500) & (df["price"] <= 300_000)]

    # ── Model Year bounds ──────────────────────────────────────────────────
    df["vehicle_model_year"] = pd.to_numeric(df["vehicle_model_year"], errors="coerce")
    valid_year = df["vehicle_model_year"].isna() | df["vehicle_model_year"].between(1990, CURRENT_YEAR + 1)
    df = df[valid_year]

    # ── Mileage clamping ───────────────────────────────────────────────────
    df["vehicle_mileage_km"] = pd.to_numeric(df["vehicle_mileage_km"], errors="coerce")
    out_of_range_mileage = (df["vehicle_mileage_km"] < 0) | (df["vehicle_mileage_km"] > 500_000)
    df.loc[out_of_range_mileage, "vehicle_mileage_km"] = np.nan

    # ── Engine CC clamping ─────────────────────────────────────────────────
    df["vehicle_engine_cc"] = pd.to_numeric(df["vehicle_engine_cc"], errors="coerce")
    out_of_range_cc = (df["vehicle_engine_cc"] < 500) | (df["vehicle_engine_cc"] > 7000)
    df.loc[out_of_range_cc, "vehicle_engine_cc"] = np.nan

    n_after = len(df)
    logger.info(
        f"Sanity filters: {n_before:,} → {n_after:,} rows "
        f"(dropped {n_before - n_after:,} invalid records)."
    )
    return df.reset_index(drop=True)


def re_extract_brands(df: pd.DataFrame) -> pd.DataFrame:
    """
    Re-run the upgraded multilingual NLP parser on all listing titles to
    improve brand/model coverage beyond what was captured at scrape time.
    """
    if "listing_title" not in df.columns:
        logger.warning("No listing_title column — skipping brand re-extraction.")
        return df

    df = df.copy()

    brand_before = df["vehicle_brand"].notna().sum()
    model_before = df["vehicle_model"].notna().sum()

    # Extract brand/model from every title
    extracted = df["listing_title"].apply(
        lambda t: pd.Series(extract_brand_model(str(t)), index=["_new_brand", "_new_model"])
    )

    # Fill missing brands with newly extracted values
    mask_brand_missing = df["vehicle_brand"].isna() | (df["vehicle_brand"] == "") | (df["vehicle_brand"] == "Unknown")
    df.loc[mask_brand_missing & extracted["_new_brand"].notna(), "vehicle_brand"] = (
        extracted.loc[mask_brand_missing & extracted["_new_brand"].notna(), "_new_brand"]
    )

    # Fill missing models
    mask_model_missing = df["vehicle_model"].isna() | (df["vehicle_model"] == "") | (df["vehicle_model"] == "Unknown")
    df.loc[mask_model_missing & extracted["_new_model"].notna(), "vehicle_model"] = (
        extracted.loc[mask_model_missing & extracted["_new_model"].notna(), "_new_model"]
    )

    brand_after = df["vehicle_brand"].notna().sum()
    model_after = df["vehicle_model"].notna().sum()

    logger.info(
        f"Brand re-extraction: brand coverage {brand_before}/{len(df)} "
        f"({brand_before/len(df)*100:.1f}%) → {brand_after}/{len(df)} "
        f"({brand_after/len(df)*100:.1f}%)  |  "
        f"model coverage {model_before}/{len(df)} → {model_after}/{len(df)}"
    )
    return df


# ═══════════════════════════════════════════════════════════════════════════════
#  GOLD LAYER: Imputation, Feature Engineering, ML Feature Selection
# ═══════════════════════════════════════════════════════════════════════════════

def impute_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Hierarchical grouped imputation for missing values.

    Strategy:
    - Numeric columns: grouped median cascade → global fallback
    - Categorical columns: mode by model → domain-appropriate default
    - Adds `is_mileage_missing` indicator flag
    """
    df = df.copy()

    # ── Mileage missing indicator (BEFORE imputation) ──────────────────────
    df["is_mileage_missing"] = df["vehicle_mileage_km"].isna().astype(int)

    # ── Model Year: grouped median by (brand, model) → (brand) → global ──
    df["vehicle_model_year"] = pd.to_numeric(df["vehicle_model_year"], errors="coerce")
    df["vehicle_model_year"] = df.groupby(["vehicle_brand", "vehicle_model"])["vehicle_model_year"].transform(
        lambda s: s.fillna(s.median())
    )
    df["vehicle_model_year"] = df.groupby("vehicle_brand")["vehicle_model_year"].transform(
        lambda s: s.fillna(s.median())
    )
    df["vehicle_model_year"] = df["vehicle_model_year"].fillna(2012)

    # ── Mileage: grouped median by (year, brand) → global median → 100k ──
    df["vehicle_mileage_km"] = pd.to_numeric(df["vehicle_mileage_km"], errors="coerce")
    if df["vehicle_mileage_km"].notna().sum() > 0:
        df["vehicle_mileage_km"] = df.groupby(
            ["vehicle_model_year", "vehicle_brand"]
        )["vehicle_mileage_km"].transform(lambda s: s.fillna(s.median()))
        df["vehicle_mileage_km"] = df["vehicle_mileage_km"].fillna(
            df["vehicle_mileage_km"].median()
        )
    df["vehicle_mileage_km"] = df["vehicle_mileage_km"].fillna(100_000)

    # ── Engine CC: grouped median by model → global fallback 2000 ─────────
    df["vehicle_engine_cc"] = pd.to_numeric(df["vehicle_engine_cc"], errors="coerce")
    if df["vehicle_engine_cc"].notna().sum() > 0:
        df["vehicle_engine_cc"] = df.groupby("vehicle_model")["vehicle_engine_cc"].transform(
            lambda s: s.fillna(s.median())
        )
    df["vehicle_engine_cc"] = df["vehicle_engine_cc"].fillna(2000)

    # ── Categorical defaults ──────────────────────────────────────────────
    df["vehicle_brand"] = df["vehicle_brand"].fillna("Unknown").str.strip()
    df["vehicle_model"] = df["vehicle_model"].fillna("Unknown").str.strip()
    df["vehicle_condition"] = df["vehicle_condition"].fillna("used").str.lower().str.strip()
    df["vehicle_tax_type"] = df["vehicle_tax_type"].fillna("Unknown").str.strip()
    df["province"] = df["province"].fillna("Phnom Penh").str.strip()
    df["seller_type"] = df["seller_type"].fillna("individual").str.lower().str.strip()

    # Fuel type: mode by vehicle_model → "Unknown"
    df["vehicle_fuel_type"] = df["vehicle_fuel_type"].replace("", np.nan)
    if df["vehicle_fuel_type"].notna().sum() > 0:
        df["vehicle_fuel_type"] = df.groupby("vehicle_model")["vehicle_fuel_type"].transform(
            lambda s: s.fillna(s.mode().iloc[0]) if len(s.mode()) > 0 else s
        )
    df["vehicle_fuel_type"] = df["vehicle_fuel_type"].fillna("Unknown").str.strip()

    # Transmission: mode by vehicle_model → "Unknown"
    df["vehicle_transmission"] = df["vehicle_transmission"].replace("", np.nan)
    if df["vehicle_transmission"].notna().sum() > 0:
        df["vehicle_transmission"] = df.groupby("vehicle_model")["vehicle_transmission"].transform(
            lambda s: s.fillna(s.mode().iloc[0]) if len(s.mode()) > 0 else s
        )
    df["vehicle_transmission"] = df["vehicle_transmission"].fillna("Unknown").str.strip()

    logger.info(
        f"Imputation complete. Remaining nulls per key column: "
        f"brand={df['vehicle_brand'].isna().sum()}, "
        f"model={df['vehicle_model'].isna().sum()}, "
        f"year={df['vehicle_model_year'].isna().sum()}, "
        f"mileage={df['vehicle_mileage_km'].isna().sum()}, "
        f"fuel={df['vehicle_fuel_type'].isna().sum()}, "
        f"trans={df['vehicle_transmission'].isna().sum()}"
    )
    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create ML features from cleaned data.

    Temporal & depreciation:
      vehicle_age, vehicle_age_squared, mileage_per_year

    Market segmentation:
      is_luxury_brand, is_popular_brand, is_chinese_ev_brand

    Geographic:
      location_tier (Tier_1 / Tier_2 / Tier_3)

    Title NLP indicators:
      has_full_option, has_sunroof, has_leather, has_camera, is_urgent_sale

    Target transformation:
      log_price = ln(1 + price)
    """
    df = df.copy()

    # ── 1. Temporal & Depreciation Features ────────────────────────────────
    df["vehicle_age"] = (CURRENT_YEAR - df["vehicle_model_year"]).clip(lower=0)
    df["vehicle_age_squared"] = df["vehicle_age"] ** 2

    mileage = pd.to_numeric(df["vehicle_mileage_km"], errors="coerce").fillna(0)
    df["mileage_per_year"] = (mileage / (df["vehicle_age"] + 1)).round(1)

    # ── 2. Brand Tier Flags ────────────────────────────────────────────────
    df["is_luxury_brand"] = df["vehicle_brand"].isin(LUXURY_BRANDS).astype(int)
    df["is_popular_brand"] = df["vehicle_brand"].isin(POPULAR_BRANDS).astype(int)
    df["is_chinese_ev_brand"] = df["vehicle_brand"].isin(CHINESE_EV_BRANDS).astype(int)

    # ── 3. Location Tier ───────────────────────────────────────────────────
    df["location_tier"] = "Tier_3"
    df.loc[df["province"].isin(TIER_2_PROVINCES), "location_tier"] = "Tier_2"
    df.loc[df["province"].isin(TIER_1_PROVINCES), "location_tier"] = "Tier_1"

    # ── 4. Title NLP Indicator Flags ───────────────────────────────────────
    title_lower = df["listing_title"].fillna("").str.lower()

    df["has_full_option"] = title_lower.str.contains(
        r"full\s*option|option\s*[34]|f[\-\s]*sport", regex=True
    ).astype(int)

    df["has_sunroof"] = title_lower.str.contains(
        r"solar|sunroof|moonroof|បើកដំបូល|open\s*roof", regex=True
    ).astype(int)

    df["has_leather"] = title_lower.str.contains(
        r"leather|ពូកស្បែក|seat\s*leather", regex=True
    ).astype(int)

    df["has_camera"] = title_lower.str.contains(
        r"camera|sensor|360|reverse\s*cam", regex=True
    ).astype(int)

    df["is_urgent_sale"] = title_lower.str.contains(
        r"urgent|លក់ប្រញាប់|ធូរថ្លៃ|negotiable|ចរចា", regex=True
    ).astype(int)

    # ── 5. Target Transformation ───────────────────────────────────────────
    df["log_price"] = np.log1p(df["price"])

    logger.info(
        f"Feature engineering complete. "
        f"Luxury brands: {df['is_luxury_brand'].sum()}, "
        f"Popular brands: {df['is_popular_brand'].sum()}, "
        f"Chinese EV: {df['is_chinese_ev_brand'].sum()}, "
        f"Full option: {df['has_full_option'].sum()}, "
        f"Urgent sale: {df['is_urgent_sale'].sum()}"
    )
    return df


# ── ML Feature Column Selection ────────────────────────────────────────────

ML_FEATURE_COLUMNS: List[str] = [
    # Identifiers (kept for debugging, NOT used in training)
    "listing_id",
    "listing_title",
    # Target
    "price",
    "log_price",
    # Core vehicle specs
    "vehicle_brand",
    "vehicle_model",
    "vehicle_model_year",
    "vehicle_age",
    "vehicle_age_squared",
    "vehicle_condition",
    "vehicle_tax_type",
    "vehicle_fuel_type",
    "vehicle_transmission",
    "vehicle_mileage_km",
    "is_mileage_missing",
    "mileage_per_year",
    "vehicle_engine_cc",
    # Location
    "province",
    "location_tier",
    # Seller & Engagement
    "seller_type",
    "view_count",
    # Historical change tracking
    "days_on_market",
    "initial_price",
    "price_drop_amount",
    "has_price_drop",
    "view_velocity",
    # Brand tier flags
    "is_luxury_brand",
    "is_popular_brand",
    "is_chinese_ev_brand",
    # Title NLP indicators
    "has_full_option",
    "has_sunroof",
    "has_leather",
    "has_camera",
    "is_urgent_sale",
]


def select_ml_features(df: pd.DataFrame) -> pd.DataFrame:
    """Select and order the final ML-ready columns."""
    available = [c for c in ML_FEATURE_COLUMNS if c in df.columns]
    missing = [c for c in ML_FEATURE_COLUMNS if c not in df.columns]
    if missing:
        logger.warning(f"ML feature selection: missing columns {missing}")
    return df[available].copy()


def split_train_test(
    df: pd.DataFrame,
    test_size: float = 0.2,
    random_state: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split into train/test sets with stratification by vehicle_brand.

    Uses listing_id as the unit of splitting to prevent data leakage
    from multi-day snapshots (though deduplication should already handle this).
    """
    # Ensure brand column has no NaN for stratification
    strat_col = df["vehicle_brand"].fillna("Unknown")

    # Bin rare brands (< 5 samples) into "Other" for stratification stability
    brand_counts = strat_col.value_counts()
    rare_brands = brand_counts[brand_counts < 5].index
    strat_col = strat_col.replace(rare_brands, "Other")

    df_train, df_test = train_test_split(
        df,
        test_size=test_size,
        random_state=random_state,
        stratify=strat_col,
    )

    logger.info(
        f"Train/test split: {len(df_train):,} train / {len(df_test):,} test "
        f"(test_size={test_size}, random_state={random_state})"
    )
    return df_train.reset_index(drop=True), df_test.reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  PIPELINE ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

def run(
    input_dir: str = RAW_DATA_DIR,
    output_dir: str = PROCESSED_DATA_DIR,
    test_size: float = 0.2,
    random_state: int = 42,
) -> Dict[str, Any]:
    """
    Execute the full Bronze → Silver → Gold preprocessing pipeline.

    1. Load raw multi-day Parquet snapshots
    2. Silver: Deduplicate, sanity filter, re-extract brands
    3. Gold: Impute, engineer features, select ML columns
    4. Split train/test and save to output_dir
    5. Write preprocessing_manifest.json

    Returns:
        Summary dict with keys: train_rows, test_rows, total_unique_listings,
        output_files, quality_metrics
    """
    start_time = time.time()

    logger.info("=" * 65)
    logger.info("Transform Pipeline — Bronze → Silver → Gold")
    logger.info(f"  Input directory  : {input_dir}")
    logger.info(f"  Output directory : {output_dir}")
    logger.info(f"  Test split ratio : {test_size}")
    logger.info("=" * 65)

    # ── Step 0: Load raw data ──────────────────────────────────────────────
    df = load_all_parquet(input_dir)
    if df.empty:
        logger.warning("No raw data found. Aborting transform pipeline.")
        return {"train_rows": 0, "test_rows": 0, "total_unique_listings": 0, "output_files": [], "quality_metrics": {}}

    logger.info(f"Loaded {len(df):,} raw rows ({df['listing_id'].nunique():,} unique IDs).")

    # ── Step 1: Silver — Deduplicate ───────────────────────────────────────
    df = deduplicate_snapshots(df)

    # ── Step 2: Silver — Sanity Filters ────────────────────────────────────
    df = apply_sanity_filters(df)

    # ── Step 3: Silver — Re-Extract Brands ─────────────────────────────────
    df = re_extract_brands(df)

    # ── Step 4: Gold — Impute Missing Values ───────────────────────────────
    df = impute_missing_values(df)

    # ── Step 5: Gold — Feature Engineering ─────────────────────────────────
    df = engineer_features(df)

    # ── Step 6: Gold — Select ML Features ──────────────────────────────────
    df = select_ml_features(df)

    # ── Step 7: Train/Test Split ───────────────────────────────────────────
    df_train, df_test = split_train_test(df, test_size=test_size, random_state=random_state)

    # ── Step 8: Save Outputs ───────────────────────────────────────────────
    os.makedirs(output_dir, exist_ok=True)

    train_path = os.path.join(output_dir, "cars_train.parquet")
    test_path = os.path.join(output_dir, "cars_test.parquet")

    df_train.to_parquet(train_path, index=False)
    df_test.to_parquet(test_path, index=False)

    logger.info(f"Saved training set   → {train_path} ({len(df_train):,} rows)")
    logger.info(f"Saved test set       → {test_path} ({len(df_test):,} rows)")

    # ── Quality Metrics ────────────────────────────────────────────────────
    duration = round(time.time() - start_time, 2)

    quality_metrics = {
        "total_unique_listings": len(df),
        "brand_coverage_pct": round(
            (df_train["vehicle_brand"] != "Unknown").sum() / len(df_train) * 100, 1
        ),
        "model_coverage_pct": round(
            (df_train["vehicle_model"] != "Unknown").sum() / len(df_train) * 100, 1
        ),
        "mileage_known_pct": round(
            (1 - df_train["is_mileage_missing"].mean()) * 100, 1
        ),
        "luxury_brand_pct": round(df_train["is_luxury_brand"].mean() * 100, 1),
        "popular_brand_pct": round(df_train["is_popular_brand"].mean() * 100, 1),
        "chinese_ev_pct": round(df_train["is_chinese_ev_brand"].mean() * 100, 1),
        "price_mean": round(df_train["price"].mean(), 2),
        "price_median": round(df_train["price"].median(), 2),
        "mean_vehicle_age": round(df_train["vehicle_age"].mean(), 1),
    }

    manifest = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "duration_seconds": duration,
        "input_dir": input_dir,
        "output_dir": output_dir,
        "train_rows": len(df_train),
        "test_rows": len(df_test),
        "train_columns": list(df_train.columns),
        "test_size": test_size,
        "random_state": random_state,
        "quality_metrics": quality_metrics,
    }

    manifest_path = os.path.join(output_dir, "preprocessing_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved manifest       → {manifest_path}")

    logger.info("=" * 65)
    logger.info(f"Transform Pipeline complete in {duration}s.")
    logger.info(f"  Train: {len(df_train):,} rows  |  Test: {len(df_test):,} rows")
    logger.info(f"  Features: {len(df_train.columns)} columns")
    logger.info("=" * 65)

    return {
        "train_rows": len(df_train),
        "test_rows": len(df_test),
        "total_unique_listings": len(df),
        "output_files": [train_path, test_path, manifest_path],
        "quality_metrics": quality_metrics,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def cli_main() -> None:
    """CLI handler for direct execution of pipeline/transform.py."""
    parser = argparse.ArgumentParser(
        description="Khmer24 Car Listings — Data Cleaning & Feature Engineering Pipeline"
    )
    parser.add_argument(
        "--input-dir", default=RAW_DATA_DIR,
        help="Input directory containing raw Parquet files",
    )
    parser.add_argument(
        "--output-dir", default=PROCESSED_DATA_DIR,
        help="Output directory for processed train/test Parquet files",
    )
    parser.add_argument(
        "--test-size", type=float, default=0.2,
        help="Fraction of data to hold out as test set (default: 0.2)",
    )
    parser.add_argument(
        "--random-state", type=int, default=42,
        help="Random seed for reproducible splits (default: 42)",
    )

    args = parser.parse_args()

    # Configure logging for CLI use
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    run(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        test_size=args.test_size,
        random_state=args.random_state,
    )


if __name__ == "__main__":
    cli_main()
