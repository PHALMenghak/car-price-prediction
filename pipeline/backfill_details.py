# pipeline/backfill_details.py — Historical detail page backfill for Bronze raw snapshots

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from src.config import BRONZE_DATA_DIR, DETAIL_WORKERS

logger = logging.getLogger(__name__)


def _build_item_dict_from_row(row: pd.Series, listing_id: str) -> Dict[str, Any]:
    """Construct an item dictionary from an existing parquet row to preserve all feed metadata."""
    phones: List[str] = []
    p_raw = row.get("seller_phones")
    if isinstance(p_raw, (list, tuple)):
        phones = [str(p).strip() for p in p_raw if str(p).strip()]
    elif isinstance(p_raw, str) and p_raw.strip():
        phones = [p_raw.strip()]

    images: List[str] = []
    img_raw = row.get("images")
    if isinstance(img_raw, (list, tuple)):
        images = [str(u).strip() for u in img_raw if str(u).strip()]
    elif isinstance(img_raw, str) and img_raw.strip():
        images = [img_raw.strip()]

    return {
        "id": listing_id,
        "title": row.get("raw_title") or row.get("listing_title", ""),
        "price": row.get("raw_price") or row.get("price"),
        "currency": row.get("raw_currency", "USD"),
        "location": {
            "en_name": row.get("raw_province"),
            "province": row.get("raw_province"),
            "district": row.get("raw_district"),
        },
        "user": {
            "id": row.get("seller_id"),
            "name": row.get("seller_name"),
            "username": row.get("seller_username"),
            "user_type": str(row.get("seller_type_code", "1")),
        },
        "phone": phones,
        "thumbnail": row.get("thumbnail_url"),
        "link": row.get("listing_url"),
        "photos": images,
        "posted_date": row.get("posted_at"),
        "renew_date": row.get("renewed_at"),
        "highlight_specs": [
            {"field": "brand", "value": row.get("raw_spec_brand")},
            {"field": "model", "value": row.get("raw_spec_model")},
            {"field": "year", "value": row.get("raw_spec_year")},
            {"field": "mileage", "value": row.get("raw_spec_mileage")},
            {"field": "engine-size", "value": row.get("raw_spec_engine_size")},
            {"field": "fuel-type", "value": row.get("raw_spec_fuel_type")},
            {"field": "transmission", "value": row.get("raw_spec_transmission")},
            {"field": "color", "value": row.get("raw_spec_color")},
            {"field": "condition", "value": row.get("raw_spec_condition")},
            {"field": "tax-type", "value": row.get("raw_spec_tax_type")},
            {"field": "body-type", "value": row.get("raw_spec_body_type")},
        ],
    }


def backfill_bronze_file(
    file_path: str,
    max_items: Optional[int] = None,
    workers: int = DETAIL_WORKERS,
) -> int:
    """
    Scan a Bronze Parquet file and enrich rows that are missing raw detail payloads.
    Fetches detail pages concurrently while preserving all original feed metadata.
    """
    logger.info(f"Checking {file_path} for missing details...")
    if not os.path.isfile(file_path):
        logger.error(f"File not found: {file_path}")
        return 0

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

    total_to_enrich = len(missing_indices)
    logger.info(f"Enriching {total_to_enrich:,} listings in {file_path} (workers={workers})...")
    enriched_count = 0

    with Khmer24Client(lang="en") as client:
        # Prepare lookup dictionary of items to fetch
        tasks: List[Tuple[int, str, Optional[str], Dict[str, Any]]] = []
        for idx in missing_indices:
            row = df.loc[idx]
            listing_id = str(row["listing_id"])
            link = str(row.get("listing_url", "")) if "listing_url" in row and pd.notna(row["listing_url"]) else None
            item_dict = _build_item_dict_from_row(row, listing_id)
            tasks.append((idx, listing_id, link, item_dict))

        # Fetch concurrently in thread pool
        if workers > 1 and len(tasks) > 1:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_task = {
                    executor.submit(client.fetch_raw_post_detail, listing_id, link): (idx, listing_id, item_dict)
                    for idx, listing_id, link, item_dict in tasks
                }

                completed = 0
                for fut in as_completed(future_to_task):
                    idx, listing_id, item_dict = future_to_task[fut]
                    completed += 1
                    try:
                        detail_data, detail_source, raw_detail_json = fut.result()
                    except Exception as e:
                        logger.warning(f"Failed to fetch detail for {listing_id}: {e}")
                        detail_data, detail_source, raw_detail_json = None, "none", None

                    if detail_data:
                        mapped = client._map_raw_listing(
                            item=item_dict,
                            detail=detail_data,
                            detail_source=detail_source,
                            raw_detail_json=raw_detail_json,
                        )
                        mapped_dict = mapped.model_dump()
                        for k, v in mapped_dict.items():
                            if k in df.columns:
                                if v is not None or pd.isna(df.at[idx, k]):
                                    df.at[idx, k] = v
                        df.at[idx, "has_detail"] = True
                        df.at[idx, "detail_source"] = detail_source
                        enriched_count += 1

                    if completed % 100 == 0 or completed == total_to_enrich:
                        logger.info(
                            f"Progress [{os.path.basename(file_path)}]: {completed}/{total_to_enrich} processed "
                            f"({enriched_count} enriched)..."
                        )
        else:
            # Sequential execution (for workers=1 or single items)
            for completed, (idx, listing_id, link, item_dict) in enumerate(tasks, 1):
                try:
                    detail_data, detail_source, raw_detail_json = client.fetch_raw_post_detail(listing_id, slug=link)
                except Exception as e:
                    logger.warning(f"Failed to fetch detail for {listing_id}: {e}")
                    detail_data, detail_source, raw_detail_json = None, "none", None

                if detail_data:
                    mapped = client._map_raw_listing(
                        item=item_dict,
                        detail=detail_data,
                        detail_source=detail_source,
                        raw_detail_json=raw_detail_json,
                    )
                    mapped_dict = mapped.model_dump()
                    for k, v in mapped_dict.items():
                        if k in df.columns:
                            if v is not None or pd.isna(df.at[idx, k]):
                                df.at[idx, k] = v
                    df.at[idx, "has_detail"] = True
                    df.at[idx, "detail_source"] = detail_source
                    enriched_count += 1

                if completed % 100 == 0 or completed == total_to_enrich:
                    logger.info(
                        f"Progress [{os.path.basename(file_path)}]: {completed}/{total_to_enrich} processed "
                        f"({enriched_count} enriched)..."
                    )

    for col in ("seller_phones", "images", "raw_specs"):
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: json.dumps(x) if isinstance(x, (list, dict)) else x
            )

    df.to_parquet(file_path, index=False)
    logger.info(f"Backfill complete for {file_path}. Enriched {enriched_count}/{total_to_enrich} rows.")
    return enriched_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Bronze Parquet Details")
    parser.add_argument("--directory", default=BRONZE_DATA_DIR, help="Bronze directory")
    parser.add_argument("--date", type=str, default=None, help="Target specific date (YYYY-MM-DD), e.g. 2026-09-01")
    parser.add_argument("--file", type=str, default=None, help="Target specific Parquet file path")
    parser.add_argument("--max-items", type=int, default=None, help="Max items to enrich")
    parser.add_argument("--workers", type=int, default=DETAIL_WORKERS, help="Number of concurrent workers")
    args = parser.parse_args()

    # Force UTF-8 output on Windows
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  [%(levelname)-8s]  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if args.file:
        files = [args.file]
    elif args.date:
        target_file = os.path.join(args.directory, f"cars_{args.date}.parquet")
        files = [target_file]
    else:
        files = sorted(glob.glob(os.path.join(args.directory, "cars_*.parquet")))

    logger.info(f"Found {len(files)} Bronze snapshot file(s) to inspect.")
    for f in files:
        backfill_bronze_file(f, max_items=args.max_items, workers=args.workers)


if __name__ == "__main__":
    main()
