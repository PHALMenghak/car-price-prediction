# src/config.py — Settings, API base URLs, and scraper constants
# Loads sensitive values from .env; all other values have safe defaults.

import os
import uuid
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()  # Reads .env file from the project root

# ── API Base URLs ──────────────────────────────────────────────────────────────
# POSTS_API_BASE can be overridden via env var to route through a
# Cloudflare Worker relay (bypasses Cloudflare Bot Management on GitHub Actions).
# Local dev: leave unset → uses the real Khmer24 API directly.
# GitHub Actions: set to https://khmer24-relay.<yourname>.workers.dev
CORE_API_BASE   = os.getenv("CORE_API_BASE", "https://api.khmer24.com")
POSTS_API_BASE  = os.getenv("POSTS_API_BASE", "https://api-posts.khmer24.com")
IMAGES_CDN_BASE = os.getenv("IMAGES_CDN_BASE", "https://images.khmer24.co")

# Cloudflare Worker relay auth key — must match RELAY_KEY set in Worker Settings.
# Leave empty when not using the Worker relay (local dev).
RELAY_KEY = os.getenv("RELAY_KEY", "")

# Device-Id is generated uniquely per session or read from env
DEVICE_ID = os.getenv("KHMER24_DEVICE_ID") or f"web-{uuid.uuid4().hex[:16]}"

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,km;q=0.8",
    "Device-Id": DEVICE_ID,
    "display-type": "desktop",
    "Origin": "https://www.khmer24.com",
    "Referer": "https://www.khmer24.com/",
    "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
}

# ── Scraper Defaults ───────────────────────────────────────────────────────────
DEFAULT_LANG          = "en"
DEFAULT_PAGE_LIMIT    = 30       # Items returned per API page
DEFAULT_DELAY_SECONDS = 0.75     # Polite delay between requests (seconds)
DEFAULT_RETRIES       = 3        # Max HTTP retry attempts per request
DEFAULT_TIMEOUT       = 25       # HTTP request timeout in seconds

# ── Storage Paths ──────────────────────────────────────────────────────────────
RAW_DATA_DIR       = os.path.join("data", "raw")
PROCESSED_DATA_DIR = os.path.join("data", "processed")
LOGS_DIR           = "logs"


def get_daily_parquet_filename(date: datetime | None = None) -> str:
    """Return the daily raw parquet filename: cars_YYYY-MM-DD.parquet."""
    d = date or datetime.now()
    return f"cars_{d.strftime('%Y-%m-%d')}.parquet"


# Alias for backward compatibility
get_next_daily_version_filename = get_daily_parquet_filename

PARQUET_FILENAME = get_daily_parquet_filename()

# ── Scrape Target & Mode ───────────────────────────────────────────────────────
# Override via environment variables for CI/CD flexibility.
TARGET_CATEGORY = os.getenv("TARGET_CATEGORY", "cars-for-sale")
TARGET_PROVINCE = os.getenv("TARGET_PROVINCE") or None   # None = all provinces
MAX_PAGES       = int(os.getenv("MAX_PAGES", "20"))       # 30 items/page → up to 600 listings

# SCRAPE_MODE:
# - 'feed_window' (default): Scrapes the active recent feed (up to MAX_PAGES).
#   Captures new listings + updated/renewed listings for multi-day change tracking.
# - 'delta_only': Stops scraping as soon as an entire page of previously known IDs is hit.
SCRAPE_MODE     = os.getenv("SCRAPE_MODE", "feed_window")

# ENRICH_DETAILS:
# If True, scrapes individual post detail endpoints for listings missing key specs.
ENRICH_DETAILS  = os.getenv("ENRICH_DETAILS", "false").lower() in ("true", "1", "yes")


