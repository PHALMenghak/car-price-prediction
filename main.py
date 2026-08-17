# main.py -- CLI entry point for the Khmer24 car price data collection pipeline.
#
# This file is intentionally thin. All pipeline logic lives in:
#   pipeline/extract_load.py  -- Extract & Load (EL) stage
#   dbt/                      -- Transform stage (future)
#
# Run locally : python main.py
# Run via CI  : uv run python main.py   (see .github/workflows/daily_scraper.yml)
# Run via uv  : uv run scrape           (see pyproject.toml [project.scripts])

import logging
import os
import sys

# Force UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError for Khmer)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pipeline.extract_load import run as run_el

# -- Logging setup ------------------------------------------------------------
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)-8s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join("logs", "scraper.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Run the full EL pipeline and exit with a non-zero code on failure."""
    try:
        new_count = run_el()
        logger.info(f"Pipeline complete. {new_count:,} new listings loaded.")
    except Exception as exc:
        logger.exception(f"Pipeline failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
