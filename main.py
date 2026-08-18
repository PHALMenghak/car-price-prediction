# main.py -- CLI entry point for the Khmer24 car price data collection pipeline.
#
# This file is intentionally thin. All pipeline logic lives in:
#   pipeline/extract_load.py  -- Extract & Load (EL) stage
#   dbt/                      -- Transform stage (future)
#
# Run locally : python main.py
# Run via CI  : uv run python main.py   (see .github/workflows/daily_scraper.yml)
# Run via uv  : uv run scrape           (see pyproject.toml [project.scripts])

from datetime import datetime
import glob
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
LOGS_DIR = "logs"
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
    """Run the full EL pipeline and exit with a non-zero code on failure."""
    try:
        new_count = run_el()
        logger.info(f"Pipeline complete. {new_count:,} new listings loaded.")
    except Exception as exc:
        logger.exception(f"Pipeline failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
