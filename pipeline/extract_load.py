# pipeline/extract_load.py — EL Stage: Ingest raw Khmer24 data directly to Bronze
# ─────────────────────────────────────────────────────────────────────────────
# Extracts raw feed & detail listings from Khmer24 using Khmer24Client.
# Saves structured raw data to data/bronze/cars_YYYY-MM-DD.parquet and khmer24_cars.csv.
# Tracks run metadata in ingestion_manifest.json and logs quality coverage metrics.

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

from src.client import Khmer24Client
from src.config import (
    BRONZE_DATA_DIR,
    ENRICH_DETAILS,
    MAX_PAGES,
    SCRAPE_MODE,
    TARGET_CATEGORY,
    TARGET_PROVINCE,
    get_daily_parquet_filename,
)
from src.schemas import RawCarListing
from src.storage import (
    get_historical_ids,
    save_run_manifest,
    save_to_csv,
    save_to_parquet,
)

logger = logging.getLogger(__name__)


def run(
    category: str = TARGET_CATEGORY,
    province: Optional[str] = TARGET_PROVINCE,
    max_pages: int = MAX_PAGES,
    scrape_mode: str = SCRAPE_MODE,
    enrich_details: bool = ENRICH_DETAILS,
    output_dir: str = BRONZE_DATA_DIR,
) -> int:
    """
    Execute the Extract & Load stage:
      1. Scrape listing feed from Khmer24 API and fetch raw details concurrently.
      2. Discover historical unique listing IDs to compute new vs. recurring metrics.
      3. Save raw records to Bronze Parquet (cars_YYYY-MM-DD.parquet) and full CSV (khmer24_cars.csv).
      4. Log raw data coverage metrics.
    """
    run_timestamp = datetime.now(timezone.utc).isoformat()
    logger.info("=" * 65)
    logger.info(f"Starting Bronze Data Ingestion: {run_timestamp}")
    logger.info(
        f"Config: category={category}, province={province or 'ALL'}, "
        f"max_pages={max_pages}, mode={scrape_mode}, enrich_details={enrich_details}"
    )
    logger.info("=" * 65)

    start_time = time.monotonic()

    # ── Step 1: Discover historical unique listing IDs ────────────────────────
    historical_ids = get_historical_ids(output_dir)
    stop_on_seen = (scrape_mode == "delta_only")

    # ── Step 2: Scrape raw feed and detail payloads ───────────────────────────
    with Khmer24Client(lang="en") as client:
        scraped_listings: List[RawCarListing] = client.scrape_category_feed(
            category_slug=category,
            province_slug=province,
            max_pages=max_pages,
            seen_ids=historical_ids,
            stop_on_seen=stop_on_seen,
            enrich_details=enrich_details,
        )

    duration_seconds = round(time.monotonic() - start_time, 2)

    if not scraped_listings:
        logger.warning("Zero listings were collected in this run. Exiting early.")
        return 0

    logger.info(
        f"Extraction complete in {duration_seconds}s: {len(scraped_listings):,} total listings collected."
    )

    # ── Step 3: Track new vs. recurring listing IDs ───────────────────────────
    new_items = [item for item in scraped_listings if item.listing_id not in historical_ids]
    recurring_items = [item for item in scraped_listings if item.listing_id in historical_ids]
    cumulative_total = len(historical_ids) + len(new_items)

    logger.info(
        f"Batch summary: {len(scraped_listings):,} total listings collected "
        f"({len(new_items):,} new IDs, {len(recurring_items):,} recurring/tracked IDs)."
    )

    # ── Step 3: Save daily Bronze Parquet + Full Run CSV + Run Manifest ───────
    parquet_filename = get_daily_parquet_filename()
    parquet_path = save_to_parquet(scraped_listings, parquet_filename, output_dir)
    csv_path = save_to_csv(scraped_listings, directory=output_dir)

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
        "csv_file": csv_path,
        "quality_metrics": coverage_report,
    }
    manifest_path = save_run_manifest(manifest_data, directory=output_dir)

    logger.info(f"Bronze Parquet -> {parquet_path}")
    logger.info(f"Full Run CSV   -> {csv_path}")
    logger.info(f"Manifest       -> {manifest_path}")

    # ── Step 4: Data quality summary logging ──────────────────────────────────
    _log_quality_summary(coverage_report, cumulative_total)

    return len(scraped_listings)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _compute_quality_metrics(listings, total_historical_unique: int = 0) -> Dict[str, Any]:
    """Compute raw field-coverage statistics for the scraped batch."""
    df = pd.DataFrame([item.model_dump() for item in listings])
    n = len(df)
    if n == 0:
        return {}

    n_price = int(df["raw_price"].notna().sum()) if "raw_price" in df.columns else 0
    n_year = int(df["raw_spec_year"].notna().sum()) if "raw_spec_year" in df.columns else 0
    n_brand = int(df["raw_spec_brand"].notna().sum()) if "raw_spec_brand" in df.columns else 0
    n_model = int(df["raw_spec_model"].notna().sum()) if "raw_spec_model" in df.columns else 0
    n_prov = int(df["raw_province"].notna().sum()) if "raw_province" in df.columns else 0
    n_mileage = int(df["raw_spec_mileage"].notna().sum()) if "raw_spec_mileage" in df.columns else 0
    n_fuel = int(df["raw_spec_fuel_type"].notna().sum()) if "raw_spec_fuel_type" in df.columns else 0
    n_trans = int(df["raw_spec_transmission"].notna().sum()) if "raw_spec_transmission" in df.columns else 0
    n_detail = int(df["has_detail"].sum()) if "has_detail" in df.columns else 0

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
        "detail_enrich_pct": round(n_detail / n * 100, 1),
        "cumulative_unique_ids": total_historical_unique,
    }


def _log_quality_summary(metrics: Dict[str, Any], cumulative_total: int) -> None:
    """Print formatted raw coverage table to logs."""
    if not metrics:
        return

    logger.info("┌" + "─" * 52 + "┐")
    logger.info(f"│  BRONZE INGESTION QUALITY SUMMARY ({metrics.get('batch_size', 0):,} records)".ljust(53) + "│")
    logger.info("├" + "─" * 36 + "┬" + "─" * 15 + "┤")
    logger.info(f"│  Price Field Coverage              │  {metrics.get('price_coverage_pct', 0.0):>5.1f}%       │")
    logger.info(f"│  Brand Field Coverage              │  {metrics.get('brand_coverage_pct', 0.0):>5.1f}%       │")
    logger.info(f"│  Model Field Coverage              │  {metrics.get('model_coverage_pct', 0.0):>5.1f}%       │")
    logger.info(f"│  Year Field Coverage               │  {metrics.get('year_coverage_pct', 0.0):>5.1f}%       │")
    logger.info(f"│  Province Field Coverage           │  {metrics.get('province_coverage_pct', 0.0):>5.1f}%       │")
    logger.info(f"│  Mileage Field Coverage            │  {metrics.get('mileage_coverage_pct', 0.0):>5.1f}%       │")
    logger.info(f"│  Transmission Field Coverage       │  {metrics.get('transmission_coverage_pct', 0.0):>5.1f}%       │")
    logger.info(f"│  Fuel Type Field Coverage          │  {metrics.get('fuel_coverage_pct', 0.0):>5.1f}%       │")
    logger.info(f"│  Detail Enrichment Rate            │  {metrics.get('detail_enrich_pct', 0.0):>5.1f}%       │")
    logger.info("├" + "─" * 36 + "┴" + "─" * 15 + "┤")
    logger.info(f"│  Cumulative Unique Marketplace IDs :  {cumulative_total:<18,d} │")
    logger.info("└" + "─" * 52 + "┘")


def main() -> None:
    """CLI entry point for pipeline/extract_load.py."""
    parser = argparse.ArgumentParser(description="Bronze Raw Extraction Pipeline")
    parser.add_argument("--category", default=TARGET_CATEGORY, help="Category slug")
    parser.add_argument("--province", default=TARGET_PROVINCE, help="Province slug")
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES, help="Max pages")
    parser.add_argument("--mode", default=SCRAPE_MODE, choices=["feed_window", "delta_only"], help="Scrape mode")
    parser.add_argument("--enrich-details", action="store_true", default=ENRICH_DETAILS, help="Enrich details")
    parser.add_argument("--output-dir", default=BRONZE_DATA_DIR, help="Output directory")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-7s] %(message)s")

    try:
        count = run(
            category=args.category,
            province=args.province,
            max_pages=args.max_pages,
            scrape_mode=args.mode,
            enrich_details=args.enrich_details,
            output_dir=args.output_dir,
        )
        logger.info(f"Extraction successful: {count:,} listings processed.")
    except Exception as exc:
        logger.exception(f"Extraction failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
