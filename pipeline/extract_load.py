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
    SCRAPE_MODE,
    TARGET_CATEGORY,
    TARGET_PROVINCE,
    get_daily_parquet_filename,
)
from src.storage import save_sample_csv, save_to_parquet

logger = logging.getLogger(__name__)


def run(
    category: str = TARGET_CATEGORY,
    province: "str | None" = TARGET_PROVINCE,
    max_pages: int = MAX_PAGES,
    scrape_mode: str = SCRAPE_MODE,
) -> int:
    """
    Run the Extract-Load pipeline with multi-day change tracking support.

    1. Discover existing raw parquet files and build a historical-ID set
       for change-tracking statistics and deduplication.
    2. Scrape active listings feed from the Khmer24 Posts API:
       - 'feed_window' (default): Scrapes recent active pages, capturing new
         listings as well as updated/renewed listings with current prices & view counts.
       - 'delta_only': Stops pagination once an entire page of previously known IDs is hit.
    3. Save results as a versioned daily Parquet file + CSV sample.
    4. Log batch breakdown (new vs. recurring) and data quality report.

    Args:
        category:    Khmer24 category slug (default: cars-for-sale).
        province:    Province slug filter; None = all provinces.
        max_pages:   Maximum API pages to fetch (30 listings each).
        scrape_mode: 'feed_window' or 'delta_only'.

    Returns:
        Number of listings collected in this batch.
    """
    logger.info("=" * 65)
    logger.info("EL Pipeline  --  Extract & Load (Time-Series & Change Tracking)")
    logger.info(f"  Category    : {category}")
    logger.info(f"  Province    : {province or 'ALL'}")
    logger.info(f"  Max pages   : {max_pages}  ({max_pages * 30} listings max)")
    logger.info(f"  Scrape mode : {scrape_mode}")
    logger.info("=" * 65)

    # -- Step 1: Discover existing raw files & build historical-ID set -------
    existing_files = sorted(
        set(
            glob.glob(os.path.join(RAW_DATA_DIR, "**", "cars_*.parquet"), recursive=True)
            + glob.glob(os.path.join(RAW_DATA_DIR, "cars_*.parquet"))
            + glob.glob(os.path.join(RAW_DATA_DIR, "khmer24_cars.parquet"))
        )
    )
    historical_ids: set = set()

    for fpath in existing_files:
        try:
            id_col = _detect_id_col_from_schema(fpath)
            if id_col:
                df_part = pd.read_parquet(fpath, columns=[id_col])
            else:
                df_part = pd.read_parquet(fpath)
            col = _detect_id_col(df_part)
            if col:
                historical_ids.update(df_part[col].astype(str))
        except Exception as exc:
            logger.warning(f"  Could not read {fpath}: {exc}")

    if historical_ids:
        logger.info(
            f"  Found {len(historical_ids):,} historical unique listing IDs across "
            f"{len(existing_files)} file(s)."
        )
    else:
        logger.info("  No prior raw files found -- starting initial baseline scrape.")

    # -- Step 2: Scrape active feed -------------------------------------------
    stop_on_seen = (scrape_mode == "delta_only")
    with Khmer24Client(lang="en") as client:
        scraped_listings = client.scrape_category_feed(
            category_slug=category,
            province_slug=province,
            max_pages=max_pages,
            seen_ids=historical_ids,
            stop_on_seen=stop_on_seen,
        )

    if not scraped_listings:
        logger.info("No listings collected in this run.")
        return 0

    # Categorize batch into new discoveries vs. recurring/updated snapshots
    new_items = [item for item in scraped_listings if item.listing_id not in historical_ids]
    recurring_items = [item for item in scraped_listings if item.listing_id in historical_ids]

    logger.info(
        f"Batch summary: {len(scraped_listings):,} total listings collected "
        f"({len(new_items):,} new IDs, {len(recurring_items):,} recurring/tracked IDs)."
    )

    # -- Step 3: Save daily Parquet + CSV sample ------------------------------
    filename     = get_daily_parquet_filename()
    parquet_path = save_to_parquet(scraped_listings, filename, RAW_DATA_DIR)
    csv_60_path  = save_sample_csv(scraped_listings, n=60, directory=RAW_DATA_DIR)

    logger.info(f"Raw Parquet -> {parquet_path}")
    logger.info(f"CSV sample  -> 60 rows : {csv_60_path}")

    # -- Step 4: Data quality summary -----------------------------------------
    _log_quality_summary(scraped_listings, total_historical_unique=len(historical_ids) + len(new_items))

    return len(scraped_listings)


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


def _log_quality_summary(listings, total_historical_unique: int = 0) -> None:
    """Log a quick field-coverage report for the scraped batch."""
    df = pd.DataFrame([item.model_dump() for item in listings])
    n = len(df)
    if n == 0:
        return

    year_col  = "vehicle_model_year" if "vehicle_model_year" in df.columns else None
    n_price   = int(df["price"].notna().sum())
    n_year    = int(df[year_col].notna().sum()) if year_col else 0
    n_brand   = int(df["vehicle_brand"].notna().sum())
    n_prov    = int(df["province"].notna().sum())

    logger.info("-- Data Quality (current batch) ---------------------------------")
    logger.info(f"  Batch listings   : {n:,}")
    logger.info(f"  With price       : {n_price:,}  ({n_price / n * 100:.1f}%)")
    logger.info(f"  With model year  : {n_year:,}  ({n_year  / n * 100:.1f}%)")
    logger.info(f"  With brand       : {n_brand:,}  ({n_brand / n * 100:.1f}%)")
    logger.info(f"  With province    : {n_prov:,}  ({n_prov  / n * 100:.1f}%)")
    if total_historical_unique > 0:
        logger.info(f"  Total Cumulative Unique IDs : {total_historical_unique:,}")

    # Phase 1 gate checks
    ok = True
    if total_historical_unique < 2000 and n < 2000:
        logger.info(f"  Progress toward Phase 1 goal (2,000 unique listings): {total_historical_unique or n:,}/2,000")
    else:
        logger.info("  Phase 1 cumulative volume target met!")

