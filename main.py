# main.py -- CLI entry point for the Khmer24 car price data collection pipeline.
#
# This file is intentionally thin. All pipeline logic lives in:
#   pipeline/extract_load.py  -- Extract & Load (EL) stage
#   dbt/                      -- Transform stage
#
# Run locally : python main.py
# Run with args: python main.py --max-pages 20 --mode feed_window --enrich-details
# Run via CI  : uv run python main.py   (see .github/workflows/daily_scraper.yml)
# Run via uv  : uv run scrape           (see pyproject.toml [project.scripts])

import argparse
from datetime import datetime
import glob
import logging
import os
import sys

# Force UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError for Khmer)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from pipeline.extract_load import run as run_el
from src.config import (
    ENRICH_DETAILS,
    LOGS_DIR,
    MAX_PAGES,
    RAW_DATA_DIR,
    SCRAPE_MODE,
    TARGET_CATEGORY,
    TARGET_PROVINCE,
)

# ── Logging setup ─────────────────────────────────────────────────────────────
os.makedirs(LOGS_DIR, exist_ok=True)

# Generate daily dated log filename: logs/scraper_YYYY-MM-DD.log
today_str = datetime.now().strftime("%Y-%m-%d")
daily_log_path = os.path.join(LOGS_DIR, f"scraper_{today_str}.log")
latest_log_path = os.path.join(LOGS_DIR, "scraper.log")


def _cleanup_old_logs(logs_dir: str = LOGS_DIR, keep_days: int = 30) -> None:
    """Automatically prune log files older than `keep_days` to manage disk space."""
    try:
        now = datetime.now().timestamp()
        cutoff = keep_days * 86400  # seconds in keep_days
        for log_file in glob.glob(os.path.join(logs_dir, "scraper_*.log")):
            if os.path.isfile(log_file) and (now - os.path.getmtime(log_file)) > cutoff:
                os.remove(log_file)
    except Exception:
        pass


_cleanup_old_logs()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)-8s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(daily_log_path, encoding="utf-8"),
        logging.FileHandler(latest_log_path, encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Run the full EL pipeline with optional CLI argument overrides."""
    parser = argparse.ArgumentParser(description="Khmer24 Data Ingestion Pipeline")
    parser.add_argument("--category", default=TARGET_CATEGORY, help="Category slug (default: cars-for-sale)")
    parser.add_argument("--province", default=TARGET_PROVINCE, help="Province slug (e.g. phnom-penh)")
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES, help="Max pages to scrape")
    parser.add_argument("--mode", default=SCRAPE_MODE, choices=["feed_window", "delta_only"], help="Scrape mode")
    parser.add_argument("--enrich-details", action="store_true", default=ENRICH_DETAILS, help="Enrich post specs from detail pages")
    parser.add_argument("--transform", action="store_true", default=False, help="Run dbt transformations immediately after scraping")
    parser.add_argument("--dbt-test", action="store_true", default=False, help="Run dbt tests after transformation")
    parser.add_argument("--output-dir", default=RAW_DATA_DIR, help="Output directory for raw data")

    args = parser.parse_args()

    try:
        result_count = run_el(
            category=args.category,
            province=args.province,
            max_pages=args.max_pages,
            scrape_mode=args.mode,
            enrich_details=args.enrich_details,
            output_dir=args.output_dir,
        )
        logger.info(f"EL stage complete. {result_count:,} listings processed in this batch.")

        if args.transform:
            logger.info("Triggering dbt transformations...")
            from pipeline.dbt_runner import run_dbt_command, run_transformation
            if args.dbt_test:
                dbt_code = run_transformation()
            else:
                dbt_code = run_dbt_command("run")

            if dbt_code != 0:
                logger.error("dbt transformation failed.")
                sys.exit(dbt_code)
            logger.info("End-to-end ELT pipeline complete.")

    except Exception as exc:
        logger.exception(f"Pipeline failed: {exc}")
        sys.exit(1)


def run_full_pipeline() -> None:
    """Run scrape with detail enrichment + dbt transformation in a single call."""
    if "--enrich-details" not in sys.argv:
        sys.argv.append("--enrich-details")
    if "--transform" not in sys.argv:
        sys.argv.append("--transform")
    if "--dbt-test" not in sys.argv:
        sys.argv.append("--dbt-test")
    main()


if __name__ == "__main__":
    main()

