# pipeline/extract_load.py
# Extract & Load pipeline for Khmer24 car listings.
#
# Stage : EL only (Extract → raw Parquet)
# Transform stage is handled separately by dbt (see dbt/).
#
# Entry point : called by main.py
# GitHub CI   : triggered by .github/workflows/daily_scraper.yml

import glob
import logging
import os

import pandas as pd
import pyarrow.parquet as pq

from src.client import Khmer24Client
from src.config import (
    MAX_PAGES,
    RAW_DATA_DIR,
    TARGET_CATEGORY,
    TARGET_PROVINCE,
    get_next_daily_version_filename,
)
from src.storage import save_sample_csv, save_to_parquet

logger = logging.getLogger(__name__)


def run(
    category: str = TARGET_CATEGORY,
    province: "str | None" = TARGET_PROVINCE,
    max_pages: int = MAX_PAGES,
) -> int:
    """
    Run the Extract-Load pipeline.

    1. Discover existing raw parquet files and build a seen-ID set
       for incremental (delta) scraping.
    2. Scrape new listings from the Khmer24 Posts API.
    3. Save results as a versioned daily Parquet file + two CSV samples.

    Args:
        category:  Khmer24 category slug (default: cars-for-sale).
        province:  Province slug filter; None = all provinces.
        max_pages: Maximum API pages to fetch (30 listings each).

    Returns:
        Number of new listings collected (0 if already up-to-date).
    """
    logger.info("=" * 65)
    logger.info("EL Pipeline  --  Extract & Load")
    logger.info(f"  Category  : {category}")
    logger.info(f"  Province  : {province or 'ALL'}")
    logger.info(f"  Max pages : {max_pages}  ({max_pages * 30} listings max)")
    logger.info("=" * 65)

    # -- Step 1: Discover existing raw files & build seen-ID set --------------
    existing_files = sorted(
        glob.glob(os.path.join(RAW_DATA_DIR, "cars_*.parquet"))
        + glob.glob(os.path.join(RAW_DATA_DIR, "khmer24_cars.parquet"))
    )
    seen_ids: set = set()

    for fpath in existing_files:
        try:
            id_col = _detect_id_col_from_schema(fpath)
            if id_col:
                df_part = pd.read_parquet(fpath, columns=[id_col])
            else:
                df_part = pd.read_parquet(fpath)
            col = _detect_id_col(df_part)
            if col:
                seen_ids.update(df_part[col].astype(str))
        except Exception as exc:
            logger.warning(f"  Could not read {fpath}: {exc}")

    if seen_ids:
        logger.info(
            f"  Found {len(seen_ids):,} existing IDs across "
            f"{len(existing_files)} file(s) -- running incremental sync."
        )
    else:
        logger.info("  No prior raw files found -- running full scrape.")

    # -- Step 2: Scrape -------------------------------------------------------
    with Khmer24Client(lang="en") as client:
        new_listings = client.scrape_category_feed(
            category_slug=category,
            province_slug=province,
            max_pages=max_pages,
            seen_ids=seen_ids,
        )

    if not new_listings:
        logger.info("No new listings found -- raw data is already up to date.")
        return 0

    logger.info(f"Collected {len(new_listings):,} new listings.")

    # -- Step 3: Save versioned Parquet + CSV samples -------------------------
    filename     = get_next_daily_version_filename(directory=RAW_DATA_DIR)
    parquet_path = save_to_parquet(new_listings, filename, RAW_DATA_DIR)
    csv_60_path  = save_sample_csv(new_listings, n=60, directory=RAW_DATA_DIR)

    logger.info(f"Raw Parquet -> {parquet_path}")
    logger.info(f"CSV sample  -> 60 rows : {csv_60_path}")

    # -- Step 4: Data quality summary (informational only) --------------------
    _log_quality_summary(new_listings)

    return len(new_listings)


# -- Helpers ------------------------------------------------------------------

def _detect_id_col_from_schema(fpath: str):
    """Return the ID column name by reading only the Parquet schema (zero data read)."""
    try:
        schema = pq.read_schema(fpath)
        for col in ("listing_id", "id"):
            if col in schema.names:
                return col
    except Exception:
        pass
    return None


def _detect_id_col(df: pd.DataFrame):
    """Return the name of the listing-ID column present in a DataFrame, or None."""
    for col in ("listing_id", "id"):
        if col in df.columns:
            return col
    return None


def _log_quality_summary(listings) -> None:
    """Log a quick field-coverage report for the newly scraped batch."""
    df = pd.DataFrame([item.model_dump() for item in listings])
    n = len(df)
    if n == 0:
        return

    year_col  = "vehicle_model_year" if "vehicle_model_year" in df.columns else None
    n_price   = int(df["price"].notna().sum())
    n_year    = int(df[year_col].notna().sum()) if year_col else 0
    n_brand   = int(df["vehicle_brand"].notna().sum())
    n_prov    = int(df["province"].notna().sum())

    logger.info("-- Data Quality (new batch) -------------------------------------")
    logger.info(f"  Total listings   : {n:,}")
    logger.info(f"  With price       : {n_price:,}  ({n_price / n * 100:.1f}%)")
    logger.info(f"  With model year  : {n_year:,}  ({n_year  / n * 100:.1f}%)")
    logger.info(f"  With brand       : {n_brand:,}  ({n_brand / n * 100:.1f}%)")
    logger.info(f"  With province    : {n_prov:,}  ({n_prov  / n * 100:.1f}%)")

    # Phase 1 gate checks
    ok = True
    if n < 2000:
        logger.warning(f"  Need >= 2,000 listings (have {n}). Increase MAX_PAGES.")
        ok = False
    if n_price < 1500:
        logger.warning(f"  Need >= 1,500 priced listings (have {n_price}).")
        ok = False
    if ok:
        logger.info("  Phase 1 data requirements met!")
