# pipeline/backfill_details.py — Historical detail page backfill for Bronze raw snapshots

import argparse
import glob
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from src.client import Khmer24Client
from src.config import BRONZE_DATA_DIR

logger = logging.getLogger(__name__)


def backfill_bronze_file(file_path: str, max_items: Optional[int] = None) -> int:
    """
    Scan a Bronze Parquet file and enrich rows that are missing raw detail payloads.
    """
    logger.info(f"Checking {file_path} for missing details...")
    df = pd.read_parquet(file_path)

    if "listing_id" not in df.columns:
        logger.warning(f"No listing_id column in {file_path}")
        return 0

    has_detail_col = "has_detail" in df.columns
    if has_detail_col:
        missing_mask = ~df["has_detail"].fillna(False).astype(bool)
    else:
        missing_mask = df["raw_description"].isna() if "raw_description" in df.columns else pd.Series(True, index=df.index)

    missing_indices = df[missing_mask].index.tolist()
    if not missing_indices:
        logger.info(f"All records in {file_path} already have details.")
        return 0

    if max_items:
        missing_indices = missing_indices[:max_items]

    logger.info(f"Enriching {len(missing_indices)} listings in {file_path}...")
    enriched_count = 0

    with Khmer24Client(lang="en") as client:
        for idx in missing_indices:
            row = df.loc[idx]
            listing_id = str(row["listing_id"])
            link = str(row.get("listing_url", "")) if "listing_url" in row else None

            detail_data, detail_source, raw_detail_json = client.fetch_raw_post_detail(listing_id, slug=link)
            if detail_data:
                item_dict = {
                    "id": listing_id,
                    "title": row.get("raw_title") or row.get("listing_title", ""),
                    "price": row.get("raw_price") or row.get("price"),
                    "views": row.get("view_count", 0),
                    "posted_date": row.get("posted_at"),
                    "renew_date": row.get("renewed_at"),
                }
                mapped = client._map_raw_listing(
                    item=item_dict,
                    detail=detail_data,
                    detail_source=detail_source,
                    raw_detail_json=raw_detail_json,
                )
                for k, v in mapped.model_dump().items():
                    if k in df.columns:
                        df.at[idx, k] = v
                enriched_count += 1
            time.sleep(0.3)

    df.to_parquet(file_path, index=False)
    logger.info(f"Backfill complete for {file_path}. Enriched {enriched_count} rows.")
    return enriched_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Bronze Parquet Details")
    parser.add_argument("--directory", default=BRONZE_DATA_DIR, help="Bronze directory")
    parser.add_argument("--max-items", type=int, default=None, help="Max items to enrich")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  [%(levelname)-8s]  %(message)s",
    )

    files = sorted(glob.glob(os.path.join(args.directory, "cars_*.parquet")))
    for f in files:
        backfill_bronze_file(f, max_items=args.max_items)


if __name__ == "__main__":
    main()
