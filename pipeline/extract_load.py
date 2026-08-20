# pipeline/extract_load.py
# Extract & Load pipeline for Khmer24 car listings.
#
# Stage : EL only (Extract → raw Parquet & CSV sample)
# Transform stage is handled separately by dbt / feature engineering pipeline.
#
# Entry point : called by main.py
# GitHub CI   : triggered by .github/workflows/daily_scraper.yml

import argparse
from datetime import datetime, timezone
import logging
import os
import time
from typing import Any, Dict, Optional, Union

import pandas as pd

from src.client import Khmer24Client
from src.config import (
    ENRICH_DETAILS,
    MAX_PAGES,
    RAW_DATA_DIR,
    SCRAPE_MODE,
    TARGET_CATEGORY,
    TARGET_PROVINCE,
    get_daily_parquet_filename,
)
from src.storage import (
    get_historical_ids,
    save_run_manifest,
    save_sample_csv,
    save_to_parquet,
)

logger = logging.getLogger(__name__)


def run(
    category: str = TARGET_CATEGORY,
    province: Optional[str] = TARGET_PROVINCE,
    max_pages: int = MAX_PAGES,
    scrape_mode: str = SCRAPE_MODE,
    enrich_details: bool = ENRICH_DETAILS,
    output_dir: str = RAW_DATA_DIR,
) -> Union[int, Dict[str, Any]]:
    """
    Run the Extract-Load pipeline with multi-day change tracking and data quality reporting.

    1. Discover existing raw parquet files and build a historical-ID set
       for change-tracking statistics and deduplication.
    2. Scrape active listings feed from the Khmer24 Posts API:
       - 'feed_window' (default): Scrapes recent active pages, capturing new
         listings as well as updated/renewed listings with current prices & view counts.
       - 'delta_only': Stops pagination once an entire page of previously known IDs is hit.
    3. Save results as a versioned daily Parquet file + CSV sample + ingestion manifest.
    4. Log batch breakdown (new vs. recurring) and data quality report.

    Args:
        category:       Khmer24 category slug (default: cars-for-sale).
        province:       Province slug filter; None = all provinces.
        max_pages:      Maximum API pages to fetch (30 listings each).
        scrape_mode:    'feed_window' or 'delta_only'.
        enrich_details: Whether to fetch individual post detail endpoints.
        output_dir:     Directory to persist raw artifacts.

    Returns:
        Number of listings collected in this batch.
    """
    start_time = time.time()
    run_timestamp = datetime.now(timezone.utc).isoformat()

    logger.info("=" * 65)
    logger.info("EL Pipeline  --  Extract & Load (Time-Series & Change Tracking)")
    logger.info(f"  Category       : {category}")
    logger.info(f"  Province       : {province or 'ALL'}")
    logger.info(f"  Max pages      : {max_pages}  ({max_pages * 30} listings max)")
    logger.info(f"  Scrape mode    : {scrape_mode}")
    logger.info(f"  Enrich details : {enrich_details}")
    logger.info(f"  Output dir     : {output_dir}")
    logger.info("=" * 65)

    # ── Step 1: Discover existing raw files & build historical-ID set ──────────
    historical_ids = get_historical_ids(output_dir)
    if historical_ids:
        logger.info(f"  Found {len(historical_ids):,} historical unique listing IDs in raw storage.")
    else:
        logger.info("  No prior raw files found -- starting initial baseline scrape.")

    # ── Step 2: Scrape active feed ────────────────────────────────────────────
    stop_on_seen = (scrape_mode == "delta_only")
    with Khmer24Client(lang="en") as client:
        scraped_listings = client.scrape_category_feed(
            category_slug=category,
            province_slug=province,
            max_pages=max_pages,
            seen_ids=historical_ids,
            stop_on_seen=stop_on_seen,
            enrich_details=enrich_details,
        )

    duration_seconds = round(time.time() - start_time, 2)

    if not scraped_listings:
        logger.info(f"No listings collected in this run (Duration: {duration_seconds}s).")
        return 0

    # Categorize batch into new discoveries vs. recurring/updated snapshots
    new_items = [item for item in scraped_listings if item.listing_id not in historical_ids]
    recurring_items = [item for item in scraped_listings if item.listing_id in historical_ids]
    cumulative_total = len(historical_ids) + len(new_items)

    logger.info(
        f"Batch summary: {len(scraped_listings):,} total listings collected "
        f"({len(new_items):,} new IDs, {len(recurring_items):,} recurring/tracked IDs)."
    )

    # ── Step 3: Save daily Parquet + CSV sample + Run Manifest ────────────────
    filename     = get_daily_parquet_filename()
    parquet_path = save_to_parquet(scraped_listings, filename, output_dir)
    csv_60_path  = save_sample_csv(scraped_listings, n=60, directory=output_dir)

    # Compute coverage metrics for quality report & manifest
    coverage_report = _compute_quality_metrics(scraped_listings, total_historical_unique=cumulative_total)
    
    manifest_data = {
        "timestamp": run_timestamp,
        "duration_seconds": duration_seconds,
        "category": category,
        "province": province,
        "scrape_mode": scrape_mode,
        "max_pages": max_pages,
        "enrich_details": enrich_details,
        "batch_total": len(scraped_listings),
        "new_ids_count": len(new_items),
        "recurring_ids_count": len(recurring_items),
        "cumulative_unique_ids": cumulative_total,
        "parquet_file": parquet_path,
        "csv_sample_file": csv_60_path,
        "quality_metrics": coverage_report,
    }
    manifest_path = save_run_manifest(manifest_data, directory=output_dir)

    logger.info(f"Raw Parquet -> {parquet_path}")
    logger.info(f"CSV sample  -> 60 rows : {csv_60_path}")
    logger.info(f"Manifest    -> {manifest_path}")

    # ── Step 4: Data quality summary logging ──────────────────────────────────
    _log_quality_summary(coverage_report, cumulative_total)

    return len(scraped_listings)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _compute_quality_metrics(listings, total_historical_unique: int = 0) -> Dict[str, Any]:
    """Compute field-coverage statistics for the scraped batch."""
    df = pd.DataFrame([item.model_dump() for item in listings])
    n = len(df)
    if n == 0:
        return {}

    year_col  = "vehicle_model_year" if "vehicle_model_year" in df.columns else None
    n_price   = int(df["price"].notna().sum()) if "price" in df.columns else 0
    n_year    = int(df[year_col].notna().sum()) if year_col else 0
    n_brand   = int(df["vehicle_brand"].notna().sum()) if "vehicle_brand" in df.columns else 0
    n_model   = int(df["vehicle_model"].notna().sum()) if "vehicle_model" in df.columns else 0
    n_prov    = int(df["province"].notna().sum()) if "province" in df.columns else 0
    n_mileage = int(df["vehicle_mileage_km"].notna().sum()) if "vehicle_mileage_km" in df.columns else 0
    n_fuel    = int(df["vehicle_fuel_type"].notna().sum()) if "vehicle_fuel_type" in df.columns else 0
    n_trans   = int(df["vehicle_transmission"].notna().sum()) if "vehicle_transmission" in df.columns else 0

    return {
        "batch_size": n,
        "price_coverage_pct": round(n_price / n * 100, 1),
        "year_coverage_pct": round(n_year / n * 100, 1),
        "brand_coverage_pct": round(n_brand / n * 100, 1),
        "model_coverage_pct": round(n_model / n * 100, 1),
        "province_coverage_pct": round(n_prov / n * 100, 1),
        "mileage_coverage_pct": round(n_mileage / n * 100, 1),
        "fuel_coverage_pct": round(n_fuel / n * 100, 1),
        "transmission_coverage_pct": round(n_trans / n * 100, 1),
        "cumulative_unique_ids": total_historical_unique,
    }


def _log_quality_summary(metrics: Dict[str, Any], total_historical_unique: int = 0) -> None:
    """Log a quick field-coverage report for the scraped batch."""
    if not metrics:
        return

    n = metrics.get("batch_size", 0)
    logger.info("-- Data Quality (current batch) ---------------------------------")
    logger.info(f"  Batch listings      : {n:,}")
    logger.info(f"  With price          : {metrics.get('price_coverage_pct', 0)}%")
    logger.info(f"  With model year     : {metrics.get('year_coverage_pct', 0)}%")
    logger.info(f"  With brand          : {metrics.get('brand_coverage_pct', 0)}%")
    logger.info(f"  With model name     : {metrics.get('model_coverage_pct', 0)}%")
    logger.info(f"  With province       : {metrics.get('province_coverage_pct', 0)}%")
    logger.info(f"  With mileage (km)   : {metrics.get('mileage_coverage_pct', 0)}%")
    logger.info(f"  With fuel type      : {metrics.get('fuel_coverage_pct', 0)}%")
    logger.info(f"  With transmission   : {metrics.get('transmission_coverage_pct', 0)}%")
    if total_historical_unique > 0:
        logger.info(f"  Total Cumulative Unique IDs : {total_historical_unique:,}")

    # Phase 1 target check
    if total_historical_unique < 2000 and n < 2000:
        logger.info(f"  Progress toward Phase 1 goal (2,000 unique listings): {total_historical_unique or n:,}/2,000")
    else:
        logger.info("  Phase 1 cumulative volume target met (>= 2,000 unique listings)!")


def cli_main() -> None:
    """CLI handler for direct execution of pipeline/extract_load.py."""
    parser = argparse.ArgumentParser(description="Khmer24 Car Listings Extract & Load Pipeline")
    parser.add_argument("--category", default=TARGET_CATEGORY, help="Category slug (e.g. cars-for-sale)")
    parser.add_argument("--province", default=TARGET_PROVINCE, help="Province slug (e.g. phnom-penh)")
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES, help="Max pages to scrape")
    parser.add_argument("--mode", default=SCRAPE_MODE, choices=["feed_window", "delta_only"], help="Scrape mode")
    parser.add_argument("--enrich-details", action="store_true", default=ENRICH_DETAILS, help="Enrich post specs from detail pages")
    parser.add_argument("--output-dir", default=RAW_DATA_DIR, help="Output directory for raw data")

    args = parser.parse_args()
    run(
        category=args.category,
        province=args.province,
        max_pages=args.max_pages,
        scrape_mode=args.mode,
        enrich_details=args.enrich_details,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    cli_main()


