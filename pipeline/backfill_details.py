# pipeline/backfill_details.py — Historical detail page backfill and spec enrichment

import argparse
import glob
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from src.client import Khmer24Client
from src.config import RAW_DATA_DIR
from src.parsers import (
    normalize_color,
    normalize_fuel_type,
    normalize_transmission,
    parse_engine_cc,
    parse_mileage,
)

logger = logging.getLogger(__name__)

CACHE_FILE_NAME = ".backfill_cache.json"

SPEC_COLS = [
    "vehicle_brand",
    "vehicle_model",
    "vehicle_transmission",
    "vehicle_fuel_type",
    "vehicle_color",
    "vehicle_mileage_km",
    "vehicle_engine_cc",
    "vehicle_tax_type",
    "vehicle_model_year",
    "vehicle_condition",
]


def _get_cache_path(raw_dir: str) -> Path:
    return Path(raw_dir) / CACHE_FILE_NAME


def load_cache(cache_path: Path) -> Dict[str, Dict[str, Any]]:
    """Load cached backfill responses to support resuming interrupted jobs."""
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load backfill cache ({e}); starting fresh.")
    return {}


def save_cache(cache: Dict[str, Dict[str, Any]], cache_path: Path) -> None:
    """Save backfill cache atomically to disk."""
    try:
        tmp_path = cache_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        tmp_path.replace(cache_path)
    except Exception as e:
        logger.warning(f"Failed to persist cache: {e}")


def scan_missing_listings(raw_dir: str) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, int]]:
    """
    Scan all historical Parquet files in raw_dir to find unique listing IDs
    that have missing or null specs.
    """
    files = sorted(glob.glob(os.path.join(raw_dir, "cars_*.parquet")))
    if not files:
        logger.warning(f"No cars_*.parquet files found in {raw_dir}")
        return {}, {}

    missing_candidates: Dict[str, Dict[str, Any]] = {}
    occurrence_counts: Dict[str, int] = {}

    for file_path in files:
        try:
            df = pd.read_parquet(file_path)
        except Exception as exc:
            logger.error(f"Error reading {file_path}: {exc}")
            continue

        if "listing_id" not in df.columns:
            continue

        check_cols = [
            c for c in [
                "vehicle_brand",
                "vehicle_model",
                "vehicle_transmission",
                "vehicle_fuel_type",
                "vehicle_color",
                "vehicle_mileage_km",
            ] if c in df.columns
        ]

        # Vectorized missing-spec detection across all check columns
        _MISSING_VALS = {"", "None", "Unknown", "nan"}

        # Build a boolean mask: True where any check column is null or a missing sentinel
        null_mask = df[check_cols].isnull().any(axis=1)
        sentinel_mask = df[check_cols].apply(
            lambda col: col.astype(str).str.strip().isin(_MISSING_VALS)
        ).any(axis=1)
        is_missing_mask = null_mask | sentinel_mask

        # Track occurrence counts for all IDs (vectorized)
        for lid in df["listing_id"].dropna().astype(str).str.strip():
            if lid and lid not in ("None", "nan"):
                occurrence_counts[lid] = occurrence_counts.get(lid, 0) + 1

        # Only iterate over rows that are missing AND not yet seen
        missing_rows = df[is_missing_mask & df["listing_id"].astype(str).str.strip().apply(
            lambda lid: bool(lid) and lid not in ("None", "nan") and lid not in missing_candidates
        )]
        for _, row in missing_rows.iterrows():
            lid = str(row.get("listing_id", "")).strip()
            if not lid or lid in ("None", "nan"):
                continue
            missing_candidates[lid] = {
                "url": row.get("listing_url") or f"https://www.khmer24.com/post-adid-{lid}",
                "title": row.get("listing_title") or "",
            }

    return missing_candidates, occurrence_counts


def extract_specs_from_detail(detail: Dict[str, Any]) -> Dict[str, Any]:
    """Parse and normalize specs from a raw detail API / Nuxt payload."""
    enriched: Dict[str, Any] = {}
    resolved = detail.get("resolved_specs") or {}

    if resolved:
        # Brand
        raw_b = resolved.get("car-brand") or resolved.get("brand")
        if raw_b:
            enriched["vehicle_brand"] = str(raw_b).strip()

        # Model
        raw_m = resolved.get("car-model") or resolved.get("model")
        if raw_m:
            enriched["vehicle_model"] = str(raw_m).strip()

        # Transmission
        raw_t = resolved.get("transmission") or resolved.get("gearbox") or resolved.get("gear-type")
        if raw_t:
            enriched["vehicle_transmission"] = normalize_transmission(raw_t)

        # Fuel type
        raw_f = resolved.get("engine-type") or resolved.get("fuel-type") or resolved.get("fuel_type")
        if raw_f:
            enriched["vehicle_fuel_type"] = normalize_fuel_type(raw_f)

        # Color
        raw_c = resolved.get("color") or resolved.get("exterior-color") or resolved.get("colour")
        if raw_c:
            enriched["vehicle_color"] = normalize_color(raw_c)

        # Mileage
        raw_km = resolved.get("mileage") or resolved.get("car-mileage") or resolved.get("odometer") or resolved.get("km")
        if raw_km is not None:
            enriched["vehicle_mileage_km"] = parse_mileage(raw_km)

        # Engine cc
        raw_cc = resolved.get("engine-size") or resolved.get("engine_size") or resolved.get("engine-cc") or resolved.get("displacement")
        if raw_cc is not None:
            enriched["vehicle_engine_cc"] = parse_engine_cc(raw_cc)

        # Model Year
        raw_yr = resolved.get("car-year") or resolved.get("year")
        if raw_yr is not None:
            try:
                yr_val = int(str(raw_yr).strip())
                if 1980 <= yr_val <= 2027:
                    enriched["vehicle_model_year"] = yr_val
            except (ValueError, TypeError):
                pass

        # Tax Type
        raw_tax = resolved.get("tax-type")
        if raw_tax:
            enriched["vehicle_tax_type"] = str(raw_tax).strip()

        # Condition
        raw_cond = resolved.get("condition")
        if raw_cond:
            enriched["vehicle_condition"] = str(raw_cond).strip()

    # Legacy specs fallback
    legacy = detail.get("highlight_specs") or detail.get("specs") or {}
    if isinstance(legacy, list):
        legacy = {s.get("field", ""): s.get("value") for s in legacy if isinstance(s, dict)}

    if isinstance(legacy, dict) and legacy:
        if "vehicle_brand" not in enriched:
            b = legacy.get("car-brand") or legacy.get("brand")
            if b:
                enriched["vehicle_brand"] = str(b).strip()
        if "vehicle_model" not in enriched:
            m = legacy.get("car-model") or legacy.get("model")
            if m:
                enriched["vehicle_model"] = str(m).strip()
        if "vehicle_transmission" not in enriched:
            t = legacy.get("transmission") or legacy.get("gearbox")
            if t:
                enriched["vehicle_transmission"] = normalize_transmission(t)
        if "vehicle_fuel_type" not in enriched:
            f = legacy.get("engine-type") or legacy.get("fuel-type") or legacy.get("fuel")
            if f:
                enriched["vehicle_fuel_type"] = normalize_fuel_type(f)
        if "vehicle_color" not in enriched:
            c = legacy.get("color") or legacy.get("exterior-color")
            if c:
                enriched["vehicle_color"] = normalize_color(c)
        if "vehicle_mileage_km" not in enriched:
            km = legacy.get("mileage") or legacy.get("km")
            if km:
                enriched["vehicle_mileage_km"] = parse_mileage(km)
        if "vehicle_engine_cc" not in enriched:
            cc = legacy.get("engine-size") or legacy.get("engine-cc")
            if cc:
                enriched["vehicle_engine_cc"] = parse_engine_cc(cc)

    return enriched


def apply_cache_to_parquets(raw_dir: str, cache: Dict[str, Dict[str, Any]], dry_run: bool = False) -> Dict[str, Any]:
    """
    Apply cached backfill data across all daily Parquet files and the sample CSV in place.
    """
    files = sorted(glob.glob(os.path.join(raw_dir, "cars_*.parquet")))
    total_updated_rows = 0
    file_stats = []

    for file_path in files:
        df = pd.read_parquet(file_path)
        updated_in_file = 0

        for col in SPEC_COLS:
            if col not in df.columns:
                df[col] = None

        for idx, row in df.iterrows():
            lid = str(row.get("listing_id", "")).strip()
            if lid in cache and cache[lid].get("status") == "ok":
                specs = cache[lid].get("specs", {})
                changed = False
                for col, val in specs.items():
                    if val is not None:
                        current_val = row.get(col)
                        is_missing_or_unknown = (
                            pd.isna(current_val) or str(current_val).strip() in ("", "None", "Unknown", "nan", None)
                        )
                        if is_missing_or_unknown:
                            df.at[idx, col] = val
                            changed = True
                        elif col in ("vehicle_brand", "vehicle_model") and val and str(val).strip() != str(current_val).strip():
                            # Authoritative clean dropdown brand/model from detail page
                            df.at[idx, col] = str(val).strip()
                            changed = True
                if changed:
                    updated_in_file += 1

        total_updated_rows += updated_in_file
        file_stats.append((Path(file_path).name, len(df), updated_in_file))

        if not dry_run and updated_in_file > 0:
            df.to_parquet(file_path, index=False)

    csv_sample = os.path.join(raw_dir, "khmer24_cars_sample_60.csv")
    if os.path.exists(csv_sample):
        df_csv = pd.read_csv(csv_sample)
        for col in SPEC_COLS:
            if col not in df_csv.columns:
                df_csv[col] = None
        for idx, row in df_csv.iterrows():
            lid = str(row.get("listing_id", "")).strip()
            if lid in cache and cache[lid].get("status") == "ok":
                specs = cache[lid].get("specs", {})
                for col, val in specs.items():
                    if val is not None:
                        current_val = row.get(col)
                        is_missing_or_unknown = (
                            pd.isna(current_val) or str(current_val).strip() in ("", "None", "Unknown", "nan", None)
                        )
                        if is_missing_or_unknown:
                            df_csv.at[idx, col] = val
                        elif col in ("vehicle_brand", "vehicle_model") and val and str(val).strip() != str(current_val).strip():
                            df_csv.at[idx, col] = str(val).strip()
        if not dry_run:
            df_csv.to_csv(csv_sample, index=False, encoding="utf-8-sig")

    return {"total_updated_rows": total_updated_rows, "file_stats": file_stats}


def compute_dataset_completeness(raw_dir: str) -> Dict[str, float]:
    """Calculate the % completeness of key features across all raw parquet files."""
    files = sorted(glob.glob(os.path.join(raw_dir, "cars_*.parquet")))
    if not files:
        return {}
    dfs = [pd.read_parquet(f) for f in files]
    combined = pd.concat(dfs, ignore_index=True)
    n = len(combined)
    if n == 0:
        return {}

    b_known = (combined["vehicle_brand"].notna() & ~combined["vehicle_brand"].astype(str).str.strip().isin(["Unknown", "", "None", "nan"])).sum() if "vehicle_brand" in combined.columns else 0
    m_known = (combined["vehicle_model"].notna() & ~combined["vehicle_model"].astype(str).str.strip().isin(["Unknown", "", "None", "nan"])).sum() if "vehicle_model" in combined.columns else 0

    return {
        "total_rows": n,
        "brand_pct": (b_known / n) * 100,
        "model_pct": (m_known / n) * 100,
        "transmission_pct": (combined["vehicle_transmission"].notna().sum() / n) * 100 if "vehicle_transmission" in combined.columns else 0.0,
        "fuel_type_pct": (combined["vehicle_fuel_type"].notna().sum() / n) * 100 if "vehicle_fuel_type" in combined.columns else 0.0,
        "color_pct": (combined["vehicle_color"].notna().sum() / n) * 100 if "vehicle_color" in combined.columns else 0.0,
        "mileage_pct": (combined["vehicle_mileage_km"].notna().sum() / n) * 100 if "vehicle_mileage_km" in combined.columns else 0.0,
        "engine_cc_pct": (combined["vehicle_engine_cc"].notna().sum() / n) * 100 if "vehicle_engine_cc" in combined.columns else 0.0,
    }


def run_backfill(
    raw_dir: str = RAW_DATA_DIR,
    limit: Optional[int] = None,
    delay_seconds: float = 0.5,
    clear_cache: bool = False,
    dry_run: bool = False,
    trigger_transform: bool = False,
) -> None:
    """Main execution function for historical detail backfill."""
    cache_path = _get_cache_path(raw_dir)

    if clear_cache and cache_path.exists():
        cache_path.unlink()
        logger.info("Cleared existing backfill cache.")

    cache = load_cache(cache_path)

    logger.info("=" * 65)
    logger.info("Historical Detail Backfill Pipeline")
    logger.info(f"  Raw Directory : {raw_dir}")
    logger.info(f"  Cached items  : {len(cache):,} IDs")
    logger.info(f"  Rate Limit    : {delay_seconds:.2f}s delay per request")
    logger.info("=" * 65)

    before_metrics = compute_dataset_completeness(raw_dir)
    logger.info(f"Before Backfill Completeness (N={before_metrics.get('total_rows', 0):,} total snapshot rows):")
    logger.info(f"  - Brand        : {before_metrics.get('brand_pct', 0.0):.1f}%")
    logger.info(f"  - Model        : {before_metrics.get('model_pct', 0.0):.1f}%")
    logger.info(f"  - Transmission : {before_metrics.get('transmission_pct', 0.0):.1f}%")
    logger.info(f"  - Fuel Type    : {before_metrics.get('fuel_type_pct', 0.0):.1f}%")
    logger.info(f"  - Color        : {before_metrics.get('color_pct', 0.0):.1f}%")
    logger.info(f"  - Mileage      : {before_metrics.get('mileage_pct', 0.0):.1f}%")

    missing_candidates, occurrence_map = scan_missing_listings(raw_dir)
    logger.info(f"Found {len(missing_candidates):,} unique listings with missing specs across all files.")

    to_fetch = {
        lid: info
        for lid, info in missing_candidates.items()
        if lid not in cache
        or cache[lid].get("status") not in ("ok", "404")
        or "vehicle_brand" not in cache[lid].get("specs", {})
    }

    logger.info(f"Unique listings needing network fetch: {len(to_fetch):,} IDs")

    fetch_items = list(to_fetch.items())
    if limit is not None and limit > 0:
        fetch_items = fetch_items[:limit]
        logger.info(f"Limiting fetch to first {len(fetch_items)} listings.")

    if fetch_items:
        logger.info("Starting detail page scraping...")
        success_count = 0
        not_found_count = 0

        with Khmer24Client(delay=delay_seconds) as client:
            for idx, (lid, info) in enumerate(fetch_items, start=1):
                url = info.get("url")
                try:
                    detail = client.fetch_post_detail(lid, url)
                    if detail:
                        specs = extract_specs_from_detail(detail)
                        cache[lid] = {
                            "status": "ok",
                            "specs": specs,
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }
                        success_count += 1
                    else:
                        cache[lid] = {
                            "status": "404",
                            "specs": {},
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }
                        not_found_count += 1
                except Exception as exc:
                    logger.debug(f"Fetch error for {lid}: {exc}")
                    cache[lid] = {
                        "status": "error",
                        "error": str(exc),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }

                if idx % 25 == 0 or idx == len(fetch_items):
                    save_cache(cache, cache_path)
                    pct = (idx / len(fetch_items)) * 100
                    logger.info(
                        f"Progress: [{idx}/{len(fetch_items)}] ({pct:.1f}%) "
                        f"-- Enriched: {success_count}, 404/Expired: {not_found_count}"
                    )

                time.sleep(delay_seconds)

        save_cache(cache, cache_path)
        logger.info(f"Scraping phase finished. Enriched: {success_count}, Expired/404: {not_found_count}.")

    logger.info("Applying cached specs to Parquet files...")
    update_result = apply_cache_to_parquets(raw_dir, cache, dry_run=dry_run)
    logger.info(f"Total row updates across all Parquet files: {update_result['total_updated_rows']:,}")

    after_metrics = compute_dataset_completeness(raw_dir)
    logger.info("=" * 65)
    logger.info("After Backfill Completeness Summary:")
    logger.info(f"  - Brand        : {after_metrics.get('brand_pct', 0.0):.1f}% (was {before_metrics.get('brand_pct', 0.0):.1f}%)")
    logger.info(f"  - Model        : {after_metrics.get('model_pct', 0.0):.1f}% (was {before_metrics.get('model_pct', 0.0):.1f}%)")
    logger.info(f"  - Transmission : {after_metrics.get('transmission_pct', 0.0):.1f}% (was {before_metrics.get('transmission_pct', 0.0):.1f}%)")
    logger.info(f"  - Fuel Type    : {after_metrics.get('fuel_type_pct', 0.0):.1f}% (was {before_metrics.get('fuel_type_pct', 0.0):.1f}%)")
    logger.info(f"  - Color        : {after_metrics.get('color_pct', 0.0):.1f}% (was {before_metrics.get('color_pct', 0.0):.1f}%)")
    logger.info(f"  - Mileage      : {after_metrics.get('mileage_pct', 0.0):.1f}% (was {before_metrics.get('mileage_pct', 0.0):.1f}%)")
    logger.info("=" * 65)

    if trigger_transform and not dry_run:
        logger.info("Triggering dbt transformations...")
        from pipeline.dbt_runner import run_transformation
        dbt_code = run_transformation()
        if dbt_code != 0:
            logger.error("dbt transformation failed after backfill.")
            sys.exit(dbt_code)
        logger.info("dbt models successfully updated with enriched data.")


def main() -> None:
    """CLI entrypoint for backfill."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  [%(levelname)-8s]  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    parser = argparse.ArgumentParser(description="Khmer24 Historical Detail Backfill")
    parser.add_argument("--raw-dir", default=RAW_DATA_DIR, help="Raw data directory")
    parser.add_argument("--limit", type=int, default=None, help="Max unique IDs to fetch in this run")
    parser.add_argument("--delay", type=float, default=0.5, help="Polite delay between requests (seconds)")
    parser.add_argument("--clear-cache", action="store_true", help="Clear existing backfill cache before running")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and cache without modifying parquet files")
    parser.add_argument("--transform", action="store_true", help="Run dbt transformation immediately after backfilling")

    args = parser.parse_args()

    try:
        run_backfill(
            raw_dir=args.raw_dir,
            limit=args.limit,
            delay_seconds=args.delay,
            clear_cache=args.clear_cache,
            dry_run=args.dry_run,
            trigger_transform=args.transform,
        )
    except Exception as exc:
        logger.exception(f"Backfill pipeline failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
