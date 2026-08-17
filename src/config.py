# src/config.py — Settings, API base URLs, and scraper constants
# Loads sensitive values from .env; all other values have safe defaults.

import glob
import os
import re
import uuid
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()  # Reads .env file from the project root

# ── API Base URLs ──────────────────────────────────────────────────────────────
CORE_API_BASE   = "https://api.khmer24.com"
POSTS_API_BASE  = "https://api-posts.khmer24.com"
IMAGES_CDN_BASE = "https://images.khmer24.co"

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

# ── Storage Paths ──────────────────────────────────────────────────────────────
RAW_DATA_DIR       = os.path.join("data", "raw")
PROCESSED_DATA_DIR = os.path.join("data", "processed")


def get_daily_parquet_filename(date: datetime | None = None, version: int = 1) -> str:
    """Return the versioned daily raw parquet filename: cars_YYYY-MM-DD_v01.parquet"""
    d = date or datetime.now()
    return f"cars_{d.strftime('%Y-%m-%d')}_v{version:02d}.parquet"


def get_next_daily_version_filename(directory: str = RAW_DATA_DIR, date: datetime | None = None) -> str:
    """
    Find the next available version number (v01, v02, ...) for today's scrape in `directory`.
    Example: if cars_2026-08-17_v01.parquet exists, returns cars_2026-08-17_v02.parquet.
    """
    d = date or datetime.now()
    date_str = d.strftime('%Y-%m-%d')
    pattern = os.path.join(directory, f"cars_{date_str}_v*.parquet")
    existing_files = glob.glob(pattern)

    max_v = 0
    for file_path in existing_files:
        match = re.search(r"_v(\d+)\.parquet$", os.path.basename(file_path))
        if match:
            max_v = max(max_v, int(match.group(1)))

    return get_daily_parquet_filename(d, version=max_v + 1)


PARQUET_FILENAME = get_daily_parquet_filename(version=1)

# ── Scrape Target ──────────────────────────────────────────────────────────────
# Override via environment variables for CI/CD flexibility.
TARGET_CATEGORY = os.getenv("TARGET_CATEGORY", "cars-for-sale")
TARGET_PROVINCE = os.getenv("TARGET_PROVINCE") or None   # None = all provinces
MAX_PAGES       = int(os.getenv("MAX_PAGES", "20"))       # 30 items/page → up to 600 listings
