# src/client.py — Robust HTTP client for the Khmer24 public APIs
# Uses curl_cffi to impersonate Chrome's TLS fingerprint,
# bypassing Cloudflare Bot Management without Playwright/Selenium.

import time
import logging
from typing import Any, Dict, List, Optional

from curl_cffi import requests as cf_requests

from src.config import (
    POSTS_API_BASE, CORE_API_BASE,
    DEFAULT_HEADERS,
    DEFAULT_LANG, DEFAULT_DELAY_SECONDS, DEFAULT_RETRIES, DEFAULT_PAGE_LIMIT,
)
from src.schemas import AdListingModel
from src.parsers import extract_brand_model, extract_spec_value, parse_mileage

logger = logging.getLogger(__name__)

# curl_cffi impersonation target — mimics a real Chrome 120 TLS fingerprint
_IMPERSONATE = "chrome120"


class Khmer24Client:
    """
    Synchronous HTTP client for the Khmer24 public APIs.

    Responsibilities:
    - Paginate the Posts API feed for the ``cars-for-sale`` category.
    - Parse each raw API item into a validated ``AdListingModel``.
    - Handle rate-limiting (HTTP 429) with exponential back-off.
    - Extract brand & model from listing titles for ML feature use.

    Usage::

        with Khmer24Client() as client:
            listings = client.scrape_category_feed(
                category_slug="cars-for-sale",
                max_pages=20,
            )
    """

    def __init__(
        self,
        lang: str = DEFAULT_LANG,
        delay: float = DEFAULT_DELAY_SECONDS,
    ):
        self.lang = lang
        self.delay = delay
        self._session = cf_requests.Session(impersonate=_IMPERSONATE, timeout=20)
        self._session.headers.update(DEFAULT_HEADERS)

    # ── Internal HTTP helper ───────────────────────────────────────────────────

    def _get(
        self,
        url: str,
        params: Dict[str, Any],
        retries: int = DEFAULT_RETRIES,
    ) -> Optional[Any]:
        """
        Perform a GET request with exponential back-off on transient failures.

        Returns the ``curl_cffi`` response object on HTTP 200, or None if all
        retries are exhausted or a non-recoverable status code is received.
        """
        for attempt in range(1, retries + 1):
            try:
                res = self._session.get(url, params=params)
                if res.status_code == 200:
                    return res
                elif res.status_code == 429:
                    wait = attempt * 5
                    logger.warning(
                        f"Rate-limited (429). Sleeping {wait}s… "
                        f"(attempt {attempt}/{retries})"
                    )
                    time.sleep(wait)
                elif res.status_code in (403, 404):
                    logger.error(
                        f"HTTP {res.status_code} for {url} — non-recoverable, stopping."
                    )
                    break
                else:
                    logger.warning(
                        f"HTTP {res.status_code} for {url} "
                        f"(attempt {attempt}/{retries})"
                    )
                    time.sleep(attempt * 1.5)
            except Exception as exc:
                logger.error(f"Request error on attempt {attempt}: {exc}")
                time.sleep(attempt * 2)
        return None

    # ── Taxonomy helpers ──────────────────────────────────────────────────────

    def fetch_categories(self) -> List[Dict[str, Any]]:
        """Fetch the full category tree from the Core API."""
        url = f"{CORE_API_BASE}/api/categories"
        res = self._get(url, params={"lang": self.lang, "v": 1})
        return res.json().get("data", []) if res else []

    def fetch_locations(
        self,
        location_type: str = "province",
        parent: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch provinces or districts from the Core API."""
        url = f"{CORE_API_BASE}/api/locations"
        params: Dict[str, Any] = {"lang": self.lang, "type": location_type}
        if parent:
            params["parent"] = parent
        res = self._get(url, params=params)
        return res.json().get("data", []) if res else []

    # ── Main scraping method ───────────────────────────────────────────────────

    def scrape_category_feed(
        self,
        category_slug: str,
        province_slug: Optional[str] = None,
        max_pages: int = 10,
        seen_ids: Optional[set] = None,
    ) -> List[AdListingModel]:
        """
        Paginate through the Posts API feed for a given category.

        Uses ``fields=all`` to retrieve the complete listing payload, including
        location, user/seller info, phone numbers, and vehicle highlight_specs.

        Args:
            category_slug:  e.g. ``'cars-for-sale'``
            province_slug:  e.g. ``'phnom-penh'``; ``None`` = all provinces
            max_pages:      Maximum number of pages to fetch (30 items each)
            seen_ids:       Set of listing IDs already in storage. When provided,
                            pagination stops as soon as a full page of already-seen
                            IDs is encountered (incremental / delta scraping).

        Returns:
            List of validated ``AdListingModel`` records (new ones only).
        """
        url = f"{POSTS_API_BASE}/feed"
        records: List[AdListingModel] = []
        seen_ids = seen_ids or set()
        offset = 0
        limit = DEFAULT_PAGE_LIMIT
        total_available: Optional[int] = None

        for page in range(1, max_pages + 1):
            params: Dict[str, Any] = {
                "category": category_slug,
                "offset": offset,
                "limit": limit,
                "lang": self.lang,
                "sort": "recent",
                "fields": "all",   # ← enables full nested payload
            }
            if province_slug:
                params["province"] = province_slug

            logger.info(
                f"[{category_slug}] Page {page}/{max_pages}  "
                f"offset={offset}  collected={len(records)}"
                + (f"  total={total_available}" if total_available else "")
            )

            res = self._get(url, params=params)
            if not res:
                logger.warning("No response — stopping pagination.")
                break

            payload = res.json()
            if total_available is None:
                total_available = payload.get("total")

            raw_items: List[Dict[str, Any]] = payload.get("data", []) or []
            if not raw_items:
                logger.info("Empty page — reached end of feed.")
                break

            new_on_page = 0
            for wrapper in raw_items:
                item = wrapper.get("data", wrapper) if isinstance(wrapper, dict) else wrapper
                item_id = str(item.get("id", ""))
                if item_id in seen_ids:
                    continue          # skip already-stored listing
                parsed = self._parse_item(item)
                if parsed:
                    records.append(parsed)
                    seen_ids.add(item_id)
                    new_on_page += 1

            # If the entire page was already known, we've caught up — stop.
            if seen_ids and new_on_page == 0:
                logger.info("Full page already in storage — incremental sync complete.")
                break

            # Early exit once all available listings have been collected
            if total_available and len(records) >= total_available:
                logger.info(f"All {total_available} listings collected.")
                break

            offset += limit
            time.sleep(self.delay)

        logger.info(f"Scrape complete. New records: {len(records)}")
        return records

    # ── Item parser ───────────────────────────────────────────────────────────

    def _parse_item(self, item: Dict[str, Any]) -> Optional[AdListingModel]:
        """
        Map a raw API ``data`` dict (from a ``fields=all`` response) to a
        validated ``AdListingModel``.

        Handles all known nesting patterns including:
        - Nested location / category / user objects
        - highlight_specs and object_highlight_specs variants
        - Legacy flat field names (phone_number_1, province, etc.)
        """
        try:
            # ── Category ─────────────────────────────────────────────────────
            cat = item.get("category") or {}
            category_name = cat.get("en_name") if isinstance(cat, dict) else str(cat)
            category_slug = cat.get("slug")    if isinstance(cat, dict) else None

            # ── Location ─────────────────────────────────────────────────────
            loc = item.get("location") or {}
            province      = loc.get("en_name")  if isinstance(loc, dict) else item.get("province")
            province_slug = loc.get("slug")     if isinstance(loc, dict) else None
            district      = None
            full_location = None
            if isinstance(loc, dict):
                full_location = (
                    loc.get("en_name3")
                    or loc.get("long_location")
                    or loc.get("en_name2")
                )
                en2 = loc.get("en_name2", "")
                if en2 and "," in en2:
                    district = en2.split(",")[0].strip()

            # ── User / Seller ─────────────────────────────────────────────────
            user = item.get("user") or {}
            seller_id    = str(user.get("id", ""))   if isinstance(user, dict) else str(item.get("userid", ""))
            seller_name  = user.get("name")          if isinstance(user, dict) else None
            seller_uname = user.get("username")      if isinstance(user, dict) else None
            raw_type     = user.get("user_type", "1") if isinstance(user, dict) else "1"
            seller_type  = "store" if str(raw_type) == "2" else "individual"

            # ── Phone numbers ─────────────────────────────────────────────────
            phones: List[str] = []
            phone_field = item.get("phone")
            if isinstance(phone_field, list):
                phones = [str(p).strip() for p in phone_field if p]
            elif isinstance(phone_field, str) and phone_field.strip():
                phones = [phone_field.strip()]
            else:
                # Legacy numbered fields
                for i in range(1, 4):
                    p = item.get(f"phone_number_{i}") or item.get(f"phone_{i}")
                    if p and str(p).strip():
                        phones.append(str(p).strip())

            # ── Vehicle specs from highlight_specs ────────────────────────────
            specs: Dict[str, Any] = {}
            car_year = None
            tax_type = None

            for spec in item.get("highlight_specs", []):
                field = spec.get("field", "")
                val   = spec.get("value")
                specs[field] = val
                if field == "car-year" and val:
                    try:
                        car_year = int(val)
                    except (ValueError, TypeError):
                        pass
                elif field == "tax-type":
                    tax_type = str(val) if val else None

            # Also handle pre-indexed object_highlight_specs dict
            obj_specs = item.get("object_highlight_specs", {})
            if isinstance(obj_specs, dict):
                for k, v in obj_specs.items():
                    if isinstance(v, dict):
                        specs[k] = v.get("value")
                if car_year is None and "car-year" in obj_specs:
                    try:
                        car_year = int(obj_specs["car-year"].get("value", 0))
                    except (ValueError, TypeError):
                        pass

            # ── Extract structured fields from specs blob (Fix #5) ────────────
            mileage_km   = parse_mileage(extract_spec_value(
                specs, "mileage", "km", "odometer", "car-mileage"
            ))
            fuel_type    = extract_spec_value(
                specs, "fuel-type", "fuel_type", "fuel"
            )
            transmission = extract_spec_value(
                specs, "transmission", "gearbox", "gear-type"
            )
            raw_engine   = extract_spec_value(
                specs, "engine-size", "engine_size", "engine-cc", "displacement"
            )
            engine_cc: Optional[int] = None
            if raw_engine:
                try:
                    engine_cc = int(float(str(raw_engine).replace(",", "").strip()))
                except (ValueError, TypeError):
                    pass
            color = extract_spec_value(specs, "color", "exterior-color", "colour")

            # ── Condition ─────────────────────────────────────────────────────
            cond_raw = item.get("condition")
            car_condition = cond_raw.get("value") if isinstance(cond_raw, dict) else None

            # ── Brand / Model from title ──────────────────────────────────────
            title = str(item.get("title", "")).strip()
            vehicle_brand, vehicle_model = extract_brand_model(title)

            # ── Thumbnail & link ──────────────────────────────────────────────
            thumbnail = item.get("thumbnail") or item.get("photo")
            link = (
                item.get("link")
                or item.get("short_link")
                or f"https://www.khmer24.com/post-adid-{item.get('id')}"
            )

            return AdListingModel(
                listing_id=str(item["id"]),
                listing_title=title,
                price=item.get("price"),
                currency="USD",
                discount_price=item.get("discount_price"),
                is_premium=item.get("is_premium"),
                category=category_name,
                category_slug=category_slug,
                province=province,
                province_slug=province_slug,
                district=district,
                location_full=full_location,
                seller_id=seller_id or None,
                seller_name=seller_name,
                seller_type=seller_type,
                seller_username=seller_uname,
                seller_phones=phones,
                view_count=int(item.get("views") or 0),
                posted_at=item.get("posted_date") or item.get("created_at"),
                renewed_at=item.get("renew_date"),
                thumbnail_url=thumbnail,
                listing_url=link,
                vehicle_model_year=car_year,
                vehicle_condition=car_condition,
                vehicle_tax_type=tax_type,
                vehicle_brand=vehicle_brand,
                vehicle_model=vehicle_model,
                vehicle_mileage_km=mileage_km,
                vehicle_fuel_type=fuel_type,
                vehicle_transmission=transmission,
                vehicle_engine_cc=engine_cc,
                vehicle_color=color,
                raw_specs=specs if specs else None,
            )

        except Exception as exc:
            logger.warning(f"Skipping item id={item.get('id')}: {exc}")
            return None

    # ── Context manager ───────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the underlying curl_cffi session."""
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
