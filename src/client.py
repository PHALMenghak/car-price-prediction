# src/client.py — Robust HTTP client for the Khmer24 public APIs
# Uses curl_cffi to impersonate Chrome's TLS fingerprint,
# bypassing Cloudflare Bot Management without Playwright/Selenium.

import os
import time
import random
import logging
from typing import Any, Dict, List, Optional

from curl_cffi import requests as cf_requests

from src.config import (
    POSTS_API_BASE, CORE_API_BASE,
    DEFAULT_HEADERS,
    DEFAULT_LANG, DEFAULT_DELAY_SECONDS, DEFAULT_RETRIES, DEFAULT_PAGE_LIMIT,
    DEFAULT_TIMEOUT, RELAY_KEY, ENRICH_DETAILS,
)
from src.schemas import AdListingModel
from src.parsers import (
    extract_brand_model,
    extract_spec_value,
    parse_mileage,
    parse_engine_cc,
    extract_nuxt_hydration_data,
)

logger = logging.getLogger(__name__)

# curl_cffi impersonation target — mimics a real Chrome 120 TLS fingerprint
_IMPERSONATE = "chrome120"


class Khmer24Client:
    """
    Synchronous HTTP client for the Khmer24 public APIs.

    Responsibilities:
    - Paginate the Posts API feed for the ``cars-for-sale`` category.
    - Parse each raw API item into a validated ``AdListingModel``.
    - Handle rate-limiting (HTTP 429) with exponential backoff and jitter.
    - Extract brand & model from listing titles for ML feature use.
    - Optionally enrich listings with detailed specs via individual post endpoints.

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
        timeout: int = DEFAULT_TIMEOUT,
        proxy: Optional[str] = None,
    ):
        self.lang = lang
        self.delay = delay
        self.timeout = timeout
        
        # Check proxy settings (env or parameter)
        proxy_url = (
            proxy
            or os.getenv("KHMER24_PROXY")
            or os.getenv("HTTPS_PROXY")
            or os.getenv("HTTP_PROXY")
        )
        proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
        
        self._session = cf_requests.Session(
            impersonate=_IMPERSONATE,
            timeout=self.timeout,
            proxies=proxies,
        )
        self._session.headers.update(DEFAULT_HEADERS)

        # Inject Cloudflare Worker relay auth header when relay is active.
        if RELAY_KEY:
            self._session.headers["X-Relay-Key"] = RELAY_KEY
            logger.info("Cloudflare Worker relay enabled (POSTS_API_BASE overridden).")

    # ── Internal HTTP helper ───────────────────────────────────────────────────

    def _get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        retries: int = DEFAULT_RETRIES,
    ) -> Optional[Any]:
        """
        Perform a GET request with exponential back-off and jitter on transient failures.

        Returns the ``curl_cffi`` response object on HTTP 200, or None if all
        retries are exhausted or a non-recoverable status code is received.
        """
        for attempt in range(1, retries + 1):
            try:
                res = self._session.get(url, params=params or {})
                if res.status_code == 200:
                    return res
                elif res.status_code == 429:
                    # Exponential backoff with random jitter to prevent thundering herd
                    wait = min(30.0, (2.0 ** attempt) + random.uniform(0.5, 2.0))
                    logger.warning(
                        f"Rate-limited (429). Sleeping {wait:.1f}s… "
                        f"(attempt {attempt}/{retries})"
                    )
                    time.sleep(wait)
                elif res.status_code in (403, 404):
                    logger.error(
                        f"HTTP {res.status_code} for {url} — non-recoverable, stopping."
                    )
                    if res.status_code == 403:
                        logger.error(
                            "  [Hint] HTTP 403 Forbidden usually indicates that Khmer24/Cloudflare blocked the hosting environment's Datacenter IP. "
                            "Consider providing a proxy (KHMER24_PROXY / HTTPS_PROXY) or running via Cloudflare Worker relay."
                        )
                        if res.text:
                            logger.debug(f"Response preview: {res.text[:300]}")
                    break
                else:
                    wait = min(15.0, (1.5 ** attempt) + random.uniform(0.2, 1.0))
                    logger.warning(
                        f"HTTP {res.status_code} for {url} "
                        f"(attempt {attempt}/{retries}). Retrying in {wait:.1f}s…"
                    )
                    time.sleep(wait)
            except Exception as exc:
                wait = min(20.0, (2.0 ** attempt) + random.uniform(0.5, 1.5))
                logger.error(f"Request error on attempt {attempt}: {exc}. Retrying in {wait:.1f}s…")
                time.sleep(wait)
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

    # ── Detail enrichment helper ──────────────────────────────────────────────

    def fetch_post_detail(self, listing_id: str, slug: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Fetch full post details for a single listing from the Posts API or HTML Nuxt fallback.
        Useful for retrieving deep attributes (odometer, engine cc, fuel type, description, images).
        """
        if not listing_id:
            return None

        # 1. Primary: REST post detail endpoint
        url = f"{POSTS_API_BASE}/post/{listing_id}"
        if RELAY_KEY:
            params = {"target": f"https://api-posts.khmer24.com/post/{listing_id}", "lang": self.lang}
            res = self._get(POSTS_API_BASE, params=params)
        else:
            res = self._get(url, params={"lang": self.lang})

        if res and res.status_code == 200:
            try:
                payload = res.json()
                data = payload.get("data")
                if isinstance(data, dict):
                    return data
            except Exception:
                pass

        # 2. Fallback: Nuxt server-rendered HTML page
        page_slug = slug or f"post-adid-{listing_id}"
        page_url = f"https://www.khmer24.com/{self.lang}/{page_slug}.html"
        html_res = self._get(page_url)
        if html_res and html_res.status_code == 200:
            nuxt_data = extract_nuxt_hydration_data(html_res.text)
            if isinstance(nuxt_data, dict):
                return nuxt_data

        return None

    # ── Main scraping method ───────────────────────────────────────────────────

    def scrape_category_feed(
        self,
        category_slug: str,
        province_slug: Optional[str] = None,
        max_pages: int = 10,
        seen_ids: Optional[set] = None,
        stop_on_seen: bool = False,
        enrich_details: bool = ENRICH_DETAILS,
    ) -> List[AdListingModel]:
        """
        Paginate through the Posts API feed for a given category.

        Uses ``fields=all`` to retrieve the complete listing payload, including
        location, user/seller info, phone numbers, and vehicle highlight_specs.

        Args:
            category_slug:  e.g. ``'cars-for-sale'``
            province_slug:  e.g. ``'phnom-penh'``; ``None`` = all provinces
            max_pages:      Maximum number of pages to fetch (30 items each)
            seen_ids:       Set of listing IDs from historical storage.
            stop_on_seen:   If True (delta_only mode), skips historical seen_ids
                            and stops pagination as soon as a full page of already-seen
                            IDs is encountered. If False (default, feed_window mode),
                            scrapes the active feed to capture new listings and
                            updated snapshots (prices, views, renewals) for SCD tracking.
            enrich_details: If True, fetches individual post details for richer specs.

        Returns:
            List of validated ``AdListingModel`` records collected in this run.
        """
        _khmer24_feed_url = "https://api-posts.khmer24.com/feed"
        if RELAY_KEY:
            url = POSTS_API_BASE   # points to Worker relay
        else:
            url = _khmer24_feed_url

        records: List[AdListingModel] = []
        historical_seen = seen_ids or set()
        seen_in_batch: set = set()
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
                "fields": "all",   # enables full nested payload
            }
            if province_slug:
                params["province"] = province_slug

            if RELAY_KEY:
                params["target"] = _khmer24_feed_url

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
                if not item_id:
                    continue

                # 1. Always prevent duplicate items inside the current batch
                if item_id in seen_in_batch:
                    continue

                # 2. If running in strict delta_only mode, skip historical listings
                if stop_on_seen and item_id in historical_seen:
                    continue

                parsed = self._parse_item(item)
                if parsed:
                    # Optional detail enrichment
                    if enrich_details and (parsed.vehicle_mileage_km is None or parsed.vehicle_engine_cc is None):
                        detail = self.fetch_post_detail(parsed.listing_id, item.get("slug"))
                        if detail:
                            parsed = self._enrich_item_with_detail(parsed, detail)

                    records.append(parsed)
                    seen_in_batch.add(item_id)
                    new_on_page += 1

            # If running in strict delta_only mode and the entire page was already known, stop.
            if stop_on_seen and historical_seen and new_on_page == 0:
                logger.info("Full page already in storage — incremental sync complete.")
                break

            # Early exit once all available listings have been collected
            if total_available and len(records) >= total_available:
                logger.info(f"All {total_available} listings collected.")
                break

            offset += limit
            time.sleep(self.delay)

        logger.info(f"Scrape complete. Collected {len(records)} records in this batch.")
        return records

    # ── Item parser ───────────────────────────────────────────────────────────

    def _parse_item(self, item: Dict[str, Any]) -> Optional[AdListingModel]:
        """
        Map a raw API ``data`` dict (from a ``fields=all`` response) to a
        validated ``AdListingModel``.
        """
        try:
            # ── Category ─────────────────────────────────────────────────────
            cat = item.get("category") or {}
            category_name = cat.get("en_name") or cat.get("name") if isinstance(cat, dict) else str(cat)
            category_slug = cat.get("slug") if isinstance(cat, dict) else None

            # ── Location ─────────────────────────────────────────────────────
            loc = item.get("location") or {}
            province      = loc.get("en_name") or loc.get("province") if isinstance(loc, dict) else item.get("province")
            province_slug = loc.get("slug") or loc.get("province_slug") if isinstance(loc, dict) else None
            district      = loc.get("district") if isinstance(loc, dict) else None
            full_location = None
            if isinstance(loc, dict):
                full_location = (
                    loc.get("en_name3")
                    or loc.get("long_location")
                    or loc.get("en_name2")
                )
                en2 = loc.get("en_name2", "")
                if en2 and "," in en2 and not district:
                    district = en2.split(",")[0].strip()

            # ── User / Seller ─────────────────────────────────────────────────
            user = item.get("user") or {}
            seller_id     = str(user.get("id", "")) if isinstance(user, dict) else str(item.get("userid", ""))
            seller_name   = user.get("name") if isinstance(user, dict) else None
            seller_uname  = user.get("username") if isinstance(user, dict) else None
            seller_avatar = user.get("avatar") or user.get("photo") if isinstance(user, dict) else None
            raw_type      = user.get("user_type", "1") if isinstance(user, dict) else "1"
            seller_type   = "store" if str(raw_type) == "2" else "individual"

            # ── Phone numbers ─────────────────────────────────────────────────
            phones: List[str] = []
            phone_field = item.get("phone")
            if isinstance(phone_field, list):
                phones = [str(p).strip() for p in phone_field if p and str(p).strip()]
            elif isinstance(phone_field, str) and phone_field.strip():
                phones = [phone_field.strip()]
            else:
                for i in range(1, 4):
                    p = item.get(f"phone_number_{i}") or item.get(f"phone_{i}")
                    if p and str(p).strip():
                        phones.append(str(p).strip())

            # ── Vehicle specs from highlight_specs ────────────────────────────
            specs: Dict[str, Any] = {}
            car_year = None
            tax_type = None

            highlight_specs = item.get("highlight_specs") or []
            if isinstance(highlight_specs, dict):
                highlight_specs = highlight_specs.values()

            for spec in highlight_specs:
                if not isinstance(spec, dict):
                    continue
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

            # Pre-indexed object_highlight_specs dict
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

            # ── Extract structured fields from specs blob ─────────────────────
            mileage_km   = parse_mileage(extract_spec_value(
                specs, "mileage", "km", "odometer", "car-mileage"
            ))
            fuel_type    = extract_spec_value(
                specs, "fuel-type", "fuel_type", "fuel"
            )
            transmission = extract_spec_value(
                specs, "transmission", "gearbox", "gear-type"
            )
            engine_cc    = parse_engine_cc(extract_spec_value(
                specs, "engine-size", "engine_size", "engine-cc", "displacement"
            ))
            color        = extract_spec_value(specs, "color", "exterior-color", "colour")

            # ── Condition ─────────────────────────────────────────────────────
            cond_raw = item.get("condition")
            car_condition = cond_raw.get("value") if isinstance(cond_raw, dict) else (str(cond_raw) if cond_raw else None)

            # ── Brand / Model from title ──────────────────────────────────────
            title = str(item.get("title", "")).strip()
            vehicle_brand, vehicle_model = extract_brand_model(title)

            # ── Thumbnail, Images & link ──────────────────────────────────────
            thumbnail = item.get("thumbnail") or item.get("photo")
            images_raw = item.get("images") or item.get("photos") or []
            images: List[str] = []
            if isinstance(images_raw, list):
                images = [str(img).strip() for img in images_raw if str(img).strip()]

            link = (
                item.get("link")
                or item.get("short_link")
                or f"https://www.khmer24.com/post-adid-{item.get('id')}"
            )
            description = str(item.get("description") or item.get("content") or "").strip() or None

            return AdListingModel(
                listing_id=str(item["id"]),
                listing_title=title,
                price=item.get("price"),
                currency="USD",
                discount_price=item.get("discount_price"),
                is_premium=item.get("is_premium"),
                is_saved=item.get("is_saved"),
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
                seller_avatar=seller_avatar,
                seller_phones=phones,
                view_count=int(item.get("views") or 0),
                posted_at=item.get("posted_date") or item.get("created_at"),
                renewed_at=item.get("renew_date"),
                thumbnail_url=thumbnail,
                listing_url=link,
                images=images,
                description=description,
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

    def _enrich_item_with_detail(self, model: AdListingModel, detail: Dict[str, Any]) -> AdListingModel:
        """Enrich an existing AdListingModel with additional attributes found in detail JSON."""
        try:
            specs = detail.get("highlight_specs") or detail.get("specs") or {}
            if isinstance(specs, list):
                specs = {s.get("field", ""): s.get("value") for s in specs if isinstance(s, dict)}

            if model.vehicle_mileage_km is None:
                model.vehicle_mileage_km = parse_mileage(extract_spec_value(specs, "mileage", "km", "odometer"))
            if model.vehicle_fuel_type is None:
                model.vehicle_fuel_type = extract_spec_value(specs, "fuel-type", "fuel_type", "fuel")
            if model.vehicle_transmission is None:
                model.vehicle_transmission = extract_spec_value(specs, "transmission", "gearbox")
            if model.vehicle_engine_cc is None:
                model.vehicle_engine_cc = parse_engine_cc(extract_spec_value(specs, "engine-size", "engine_size", "engine-cc"))
            if model.vehicle_color is None:
                model.vehicle_color = extract_spec_value(specs, "color", "exterior-color")
            if not model.description:
                model.description = str(detail.get("description") or detail.get("content") or "").strip() or None
            if not model.images:
                imgs = detail.get("images") or detail.get("photos") or []
                if isinstance(imgs, list):
                    model.images = [str(img).strip() for img in imgs if str(img).strip()]
        except Exception as exc:
            logger.debug(f"Could not enrich item id={model.listing_id}: {exc}")
        return model

    # ── Context manager ───────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the underlying curl_cffi session."""
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

