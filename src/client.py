# src/client.py — Robust HTTP client for Khmer24 public APIs
# Uses curl_cffi to impersonate Chrome's TLS fingerprint.
# Pure ELT Extraction: captures 100% untouched raw data from Feed API and Detail Pages.

import json
import logging
import os
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from curl_cffi import requests as cf_requests

from src.config import (
    CORE_API_BASE,
    DEFAULT_DELAY_SECONDS,
    DEFAULT_HEADERS,
    DEFAULT_LANG,
    DEFAULT_PAGE_LIMIT,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT,
    DETAIL_WORKERS,
    ENRICH_DETAILS,
    POSTS_API_BASE,
    RELAY_KEY,
)
from src.schemas import RawCarListing

logger = logging.getLogger(__name__)

_IMPERSONATE = "chrome120"
_NUXT_SPEC_MAP_SIGNATURE: frozenset = frozenset({"engine-type", "transmission", "color"})


# ── Inlined Nuxt HTML Extraction Utilities ────────────────────────────────────

def extract_nuxt_hydration_data(html_content: str) -> Optional[Any]:
    """
    Extract the raw JSON hydration payload embedded inside a Khmer24 Nuxt page.
    Matches either `<script type="application/json">` or `window.__NUXT_DATA__ = [...]`.
    """
    if not html_content:
        return None
    match = re.search(
        r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',
        html_content,
        re.DOTALL,
    )
    if not match:
        match = re.search(
            r'window\.__NUXT_DATA__\s*=\s*(\[.*?\]);', html_content, re.DOTALL
        )
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        logger.debug(f"Failed to decode Nuxt hydration JSON: {exc}")
        return None


def _nuxt_resolve(arr: List[Any], node: Any, _depth: int = 0) -> Any:
    """Recursively dereference integer pointer nodes in a Khmer24 NUXT flat array."""
    if _depth > 30:
        return node
    if isinstance(node, int) and 0 <= node < len(arr):
        return _nuxt_resolve(arr, arr[node], _depth + 1)
    if isinstance(node, dict):
        return {k: _nuxt_resolve(arr, v, _depth + 1) for k, v in node.items()}
    if isinstance(node, list):
        return [_nuxt_resolve(arr, v, _depth + 1) for v in node]
    return node


def resolve_nuxt_specs(arr: Any) -> Optional[Dict[str, Any]]:
    """Resolve vehicle spec fields embedded in a Khmer24 NUXT hydration array."""
    if not isinstance(arr, list):
        return None

    spec_map_node: Optional[Dict[str, Any]] = None
    for item in arr:
        if isinstance(item, dict) and (
            _NUXT_SPEC_MAP_SIGNATURE.issubset(item.keys())
            or len(_NUXT_SPEC_MAP_SIGNATURE.intersection(item.keys())) >= 2
        ):
            spec_map_node = item
            break

    if spec_map_node is None:
        return None

    result: Dict[str, Any] = {}
    for field_key, spec_idx in spec_map_node.items():
        resolved_spec = _nuxt_resolve(arr, spec_idx)
        if not isinstance(resolved_spec, dict):
            continue
        val = resolved_spec.get("display_value") or resolved_spec.get("value")
        if val is not None and not isinstance(val, (dict, list)):
            if field_key in ("car-year", "year"):
                val_str = str(val).strip()
                if not re.match(r'^(19[89]\d|20[012]\d)$', val_str):
                    continue
            result[field_key] = val

    return result or None


def resolve_nuxt_post_detail(arr: Any) -> Optional[Dict[str, Any]]:
    """
    Resolve complete post details (description, specs, photos, phone)
    embedded in a Khmer24 NUXT hydration array without recursive tree blowup.
    """
    if not isinstance(arr, list):
        return None

    post_node: Optional[Dict[str, Any]] = None
    for item in arr:
        if isinstance(item, dict) and "description" in item and ("specs" in item or "photos" in item or "title" in item):
            post_node = item
            break

    if post_node is None:
        for item in arr:
            if isinstance(item, dict) and "description" in item:
                post_node = item
                break

    resolved_post: Dict[str, Any] = {}
    if post_node is not None:
        for key in ("id", "title", "description", "phone", "specs", "photos", "images"):
            if key in post_node:
                val = _nuxt_resolve(arr, post_node[key])
                if val is not None:
                    resolved_post[key] = val

    # Extract server-generated meta keywords if present in nuxt array
    for item in arr:
        if isinstance(item, dict) and "keyword" in item and isinstance(item.get("keyword"), (int, str)):
            kw = _nuxt_resolve(arr, item.get("keyword"))
            if isinstance(kw, str) and kw.strip():
                resolved_post["meta_keywords"] = kw.strip()
                break

    # Also attach resolved specs map
    spec_map = resolve_nuxt_specs(arr)
    if spec_map:
        resolved_post["resolved_specs"] = spec_map

    return resolved_post or None


# ── Khmer24Client ─────────────────────────────────────────────────────────────

class Khmer24Client:
    """
    HTTP client for Khmer24 data extraction.

    Extracts untouched raw data from:
    1. Category feed endpoint (`/feed`)
    2. Individual post detail endpoint (`/post/{id}`) or Nuxt HTML fallback.
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

        if RELAY_KEY:
            self._session.headers["X-Relay-Key"] = RELAY_KEY
            logger.info("Cloudflare Worker relay enabled.")

    def _get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        retries: int = DEFAULT_RETRIES,
        silent_404: bool = False,
    ) -> Optional[Any]:
        """HTTP GET with exponential backoff and jitter for rate limits (429/503)."""
        backoff = 1.5
        for attempt in range(1, retries + 1):
            try:
                res = self._session.get(url, params=params)
                if res.status_code == 200:
                    return res
                if res.status_code == 404:
                    if not silent_404:
                        logger.debug(f"404 Not Found: {url}")
                    return None
                if res.status_code in (429, 503):
                    wait = backoff + random.uniform(0.5, 1.5)
                    logger.warning(
                        f"HTTP {res.status_code} on attempt {attempt}/{retries}. "
                        f"Backing off {wait:.1f}s..."
                    )
                    time.sleep(wait)
                    backoff *= 2
                    continue
                logger.warning(f"HTTP {res.status_code} for {url}")
            except Exception as exc:
                if attempt == retries:
                    logger.error(f"Failed {url} after {retries} attempts: {exc}")
                    return None
                time.sleep(backoff + random.uniform(0.2, 0.8))
                backoff *= 1.5
        return None

    def __enter__(self) -> "Khmer24Client":
        return self

    def __exit__(self, *args: Any) -> None:
        try:
            self._session.close()
        except Exception:
            pass

    # ── Raw Detail Fetching ───────────────────────────────────────────────────

    def fetch_raw_post_detail(
        self, listing_id: str, slug: Optional[str] = None
    ) -> Tuple[Optional[Dict[str, Any]], str, Optional[str]]:
        """
        Fetch untouched raw detail data for a single listing ID.

        Tries:
        1. Posts REST detail endpoint: /post/{listing_id}
        2. Fallback: Nuxt HTML page: /post-adid-{listing_id}.html

        Returns:
            Tuple of (detail_dict, detail_source, raw_detail_json_string)
        """
        if not listing_id:
            return None, "none", None

        # 1. Primary: REST post detail endpoint
        url = f"{POSTS_API_BASE}/post/{listing_id}"
        if RELAY_KEY:
            params = {
                "target": f"https://api-posts.khmer24.com/post/{listing_id}",
                "lang": self.lang,
            }
            res = self._get(POSTS_API_BASE, params=params, silent_404=True)
        else:
            res = self._get(url, params={"lang": self.lang}, silent_404=True)

        if res and res.status_code == 200:
            try:
                payload = res.json()
                data = payload.get("data")
                if isinstance(data, dict):
                    raw_str = json.dumps(data, ensure_ascii=False)
                    return data, "rest_api", raw_str
            except Exception:
                pass

        # 2. Fallback: Nuxt HTML page
        if slug and str(slug).startswith("http"):
            page_url = str(slug)
        elif slug:
            page_url = f"https://www.khmer24.com/{self.lang}/{slug}.html"
        else:
            page_url = f"https://www.khmer24.com/{self.lang}/post-adid-{listing_id}.html"

        if RELAY_KEY:
            params = {"target": page_url}
            html_res = self._get(POSTS_API_BASE, params=params, silent_404=True)
        else:
            html_res = self._get(page_url, silent_404=True)

        if html_res and html_res.status_code == 200:
            nuxt_data = extract_nuxt_hydration_data(html_res.text)
            if isinstance(nuxt_data, list):
                detail_obj = resolve_nuxt_post_detail(nuxt_data)
                if detail_obj:
                    detail_obj["_source"] = "nuxt_html"
                    raw_str = json.dumps(detail_obj, ensure_ascii=False)
                    return detail_obj, "nuxt_html", raw_str
            elif isinstance(nuxt_data, dict):
                raw_str = json.dumps(nuxt_data, ensure_ascii=False)
                return nuxt_data, "nuxt_html", raw_str

        return None, "none", None

    # ── Raw Item Mapping ──────────────────────────────────────────────────────

    def _map_raw_listing(
        self,
        item: Dict[str, Any],
        detail: Optional[Dict[str, Any]] = None,
        detail_source: Optional[str] = "none",
        raw_detail_json: Optional[str] = None,
    ) -> RawCarListing:
        """
        Map raw API/HTML dictionaries directly into a RawCarListing model
        WITHOUT applying regex cleaning, type casting, or normalization.
        """
        listing_id = str(item.get("id", "")) or (str(detail.get("id", "")) if isinstance(detail, dict) else "")
        title = (
            str(item.get("title", "")).strip()
            or (str(detail.get("title", "")).strip() if isinstance(detail, dict) else "")
        ) or None
        raw_price = (
            str(item.get("price"))
            if item.get("price") is not None
            else (str(detail.get("price")) if isinstance(detail, dict) and detail.get("price") is not None else None)
        )
        currency = str(item.get("currency") or (detail.get("currency") if isinstance(detail, dict) else None) or "USD")

        # ── Location ─────────────────────────────────────────────────────────
        loc = item.get("location") or {}
        province = loc.get("en_name") or loc.get("province") if isinstance(loc, dict) else item.get("province")
        district = loc.get("district") if isinstance(loc, dict) else None
        if isinstance(loc, dict) and not district:
            en2 = loc.get("en_name2", "")
            if en2 and "," in en2:
                district = en2.split(",")[0].strip()

        # ── User / Seller ────────────────────────────────────────────────────
        user = item.get("user") or {}
        seller_id = str(user.get("id", "")) if isinstance(user, dict) else str(item.get("userid", ""))
        seller_name = user.get("name") if isinstance(user, dict) else None
        seller_uname = user.get("username") if isinstance(user, dict) else None
        seller_type_code = str(user.get("user_type", "1")) if isinstance(user, dict) else "1"

        # Phone numbers
        phones: List[str] = []
        phone_field = item.get("phone") or (detail.get("phone") if isinstance(detail, dict) else None)
        if isinstance(phone_field, list):
            phones = [str(p).strip() for p in phone_field if p and str(p).strip()]
        elif isinstance(phone_field, str) and phone_field.strip():
            phones = [phone_field.strip()]
        else:
            for i in range(1, 4):
                p = item.get(f"phone_number_{i}") or item.get(f"phone_{i}")
                if p and str(p).strip():
                    phones.append(str(p).strip())

        # ── Raw Specs Extraction (Feed + Detail) ──────────────────────────────
        specs: Dict[str, Any] = {}

        # 1. From Feed highlight_specs
        highlight_specs = item.get("highlight_specs") or []
        if isinstance(highlight_specs, dict):
            highlight_specs = highlight_specs.values()
        for s in highlight_specs:
            if isinstance(s, dict):
                k = s.get("field") or s.get("key") or s.get("title")
                v = s.get("value")
                if k and v is not None:
                    specs[str(k).lower().replace("_", "-")] = str(v)

        obj_specs = item.get("object_highlight_specs", {})
        if isinstance(obj_specs, dict):
            for k, v in obj_specs.items():
                if isinstance(v, dict):
                    specs[str(k).lower().replace("_", "-")] = str(v.get("value", ""))

        # 2. From Detail payload (if present)
        if isinstance(detail, dict):
            if "resolved_specs" in detail and isinstance(detail["resolved_specs"], dict):
                for k, v in detail["resolved_specs"].items():
                    if v is not None:
                        specs[str(k).lower().replace("_", "-")] = str(v)
            if "specs" in detail:
                d_specs = detail["specs"]
                if isinstance(d_specs, dict):
                    for k, v in d_specs.items():
                        if v is not None and not isinstance(v, (dict, list)):
                            specs[str(k).lower().replace("_", "-")] = str(v)
                elif isinstance(d_specs, list):
                    for s in d_specs:
                        if isinstance(s, dict):
                            k = s.get("field") or s.get("key") or s.get("title")
                            v = s.get("display_value") or s.get("value")
                            if k and v is not None and not isinstance(v, (dict, list)):
                                specs[str(k).lower().replace("_", "-")] = str(v)
            if "highlight_specs" in detail:
                d_hs = detail["highlight_specs"]
                if isinstance(d_hs, dict):
                    d_hs = d_hs.values()
                for s in d_hs:
                    if isinstance(s, dict):
                        k = s.get("field") or s.get("key")
                        v = s.get("display_value") or s.get("value")
                        if k and v is not None and not isinstance(v, (dict, list)):
                            specs[str(k).lower().replace("_", "-")] = str(v)

        def _get_spec(*keys: str) -> Optional[str]:
            for key in keys:
                norm_key = key.lower().replace("_", "-")
                if norm_key in specs and specs[norm_key]:
                    return str(specs[norm_key]).strip()
            return None

        raw_spec_brand = _get_spec("car-brand", "brand")
        raw_spec_model = _get_spec("car-model", "model")
        
        # ── Year: Detail specs -> Feed highlight_specs -> Detail meta_keywords ──
        raw_year_candidate = _get_spec("car-year", "year")
        if raw_year_candidate and re.match(r'^(19[89]\d|20[012]\d)$', str(raw_year_candidate).strip()):
            raw_spec_year = str(raw_year_candidate).strip()
        else:
            meta_kw = ""
            if isinstance(detail, dict):
                meta_kw = str(detail.get("meta_keywords") or detail.get("keyword") or "")
            m_kw = re.search(r'(?:^|,|\s)(19[89]\d|20[012]\d)(?:$|,|\s)', meta_kw)
            raw_spec_year = m_kw.group(1) if m_kw else None

        raw_spec_mileage = _get_spec("mileage", "km", "odometer", "car-mileage")
        raw_spec_engine_size = _get_spec("engine-size", "engine_size", "engine-cc", "displacement")
        raw_spec_fuel_type = _get_spec("engine-type", "fuel-type", "fuel_type", "fuel")
        raw_spec_transmission = _get_spec("transmission", "gearbox", "gear-type")
        raw_spec_color = _get_spec("color", "exterior-color", "colour")
        
        # ── Tax Type: Feed highlight_specs / Detail specs ───────────────────────
        raw_spec_tax_type = _get_spec("tax-type", "tax_type") or (
            item.get("tax_type") or (detail.get("tax_type") if isinstance(detail, dict) else None)
        )
        raw_spec_steering = _get_spec("steering", "wheel")
        raw_spec_body_type = _get_spec("body-type", "body_type")

        # Condition
        cond_raw = item.get("condition") or (detail.get("condition") if isinstance(detail, dict) else None)
        raw_spec_condition = (
            cond_raw.get("value") or cond_raw.get("display_value")
            if isinstance(cond_raw, dict)
            else (str(cond_raw) if cond_raw else None)
        ) or _get_spec("condition")

        # ── Content & Media ──────────────────────────────────────────────────
        raw_thumb = item.get("thumbnail") or item.get("photo")
        if isinstance(raw_thumb, dict):
            thumbnail = raw_thumb.get("url") or raw_thumb.get("src") or raw_thumb.get("link")
        else:
            thumbnail = str(raw_thumb).strip() if raw_thumb else None

        images_raw = (
            item.get("images")
            or item.get("photos")
            or (detail.get("photos") if isinstance(detail, dict) else None)
            or (detail.get("images") if isinstance(detail, dict) else None)
            or []
        )
        images: List[str] = []
        if isinstance(images_raw, list):
            for img in images_raw:
                if isinstance(img, dict):
                    u = img.get("url") or img.get("src") or img.get("link")
                    if u:
                        images.append(str(u).strip())
                elif isinstance(img, str) and img.strip():
                    images.append(img.strip())

        listing_url = (
            item.get("link")
            or item.get("short_link")
            or f"https://www.khmer24.com/post-adid-{listing_id}"
        )

        raw_description = None
        if isinstance(detail, dict) and detail.get("description"):
            raw_description = str(detail.get("description")).strip()
        elif item.get("description") or item.get("content"):
            raw_description = str(item.get("description") or item.get("content")).strip()

        # ── Timestamps ───────────────────────────────────────────────────────
        posted_at = str(item.get("posted_date") or item.get("created_at") or "") or None
        renewed_at = str(item.get("renew_date") or "") or None
        view_count = int(item.get("views") or 0)

        raw_feed_payload = json.dumps(item, ensure_ascii=False)

        return RawCarListing(
            listing_id=listing_id,
            raw_title=title,
            raw_price=raw_price,
            raw_currency=currency,
            raw_spec_brand=raw_spec_brand,
            raw_spec_model=raw_spec_model,
            raw_spec_year=raw_spec_year,
            raw_spec_mileage=raw_spec_mileage,
            raw_spec_engine_size=raw_spec_engine_size,
            raw_spec_fuel_type=raw_spec_fuel_type,
            raw_spec_transmission=raw_spec_transmission,
            raw_spec_color=raw_spec_color,
            raw_spec_condition=raw_spec_condition,
            raw_spec_tax_type=raw_spec_tax_type,
            raw_spec_steering=raw_spec_steering,
            raw_spec_body_type=raw_spec_body_type,
            raw_province=province,
            raw_district=district,
            seller_id=seller_id or None,
            seller_name=seller_name,
            seller_type_code=seller_type_code,
            seller_username=seller_uname,
            seller_phones=phones,
            raw_description=raw_description,
            thumbnail_url=thumbnail,
            listing_url=listing_url,
            images=images,
            view_count=view_count,
            posted_at=posted_at,
            renewed_at=renewed_at,
            detail_source=detail_source,
            has_detail=bool(detail),
            raw_feed_payload=raw_feed_payload,
            raw_detail_payload=raw_detail_json,
        )

    # ── Main Scraping Pipeline ─────────────────────────────────────────────────

    def scrape_category_feed(
        self,
        category_slug: str = "cars-for-sale",
        province_slug: Optional[str] = None,
        max_pages: int = 10,
        seen_ids: Optional[Set[str]] = None,
        stop_on_seen: bool = False,
        enrich_details: bool = ENRICH_DETAILS,
        *,
        category: Optional[str] = None,
        province: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> List[RawCarListing]:
        """
        Paginate through the Posts API feed and scrape fresh detail pages for all listings.
        """
        if category is not None:
            category_slug = category
        if province is not None:
            province_slug = province
        if mode == "delta_only":
            stop_on_seen = True
        _khmer24_feed_url = "https://api-posts.khmer24.com/feed"
        url = POSTS_API_BASE if RELAY_KEY else _khmer24_feed_url

        records: List[RawCarListing] = []
        historical_seen = seen_ids or set()
        seen_in_batch: Set[str] = set()
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
                "fields": "all",
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

            page_items_to_process: List[Dict[str, Any]] = []
            new_on_page = 0

            for wrapper in raw_items:
                item = wrapper.get("data", wrapper) if isinstance(wrapper, dict) else wrapper
                item_id = str(item.get("id", ""))
                if not item_id or item_id in seen_in_batch:
                    continue

                if stop_on_seen and item_id in historical_seen:
                    continue

                seen_in_batch.add(item_id)
                page_items_to_process.append(item)
                new_on_page += 1

            # Fetch detail pages concurrently for all listings in this page batch
            if enrich_details and page_items_to_process:
                logger.info(
                    f"Fetching details concurrently for {len(page_items_to_process)} listings "
                    f"(workers={DETAIL_WORKERS})..."
                )
                with ThreadPoolExecutor(max_workers=DETAIL_WORKERS) as executor:
                    futures = {
                        executor.submit(
                            self.fetch_raw_post_detail,
                            str(item.get("id")),
                            item.get("link") or item.get("slug"),
                        ): item
                        for item in page_items_to_process
                    }
                    for fut in as_completed(futures):
                        item = futures[fut]
                        detail_data, detail_source, raw_detail_json = fut.result()
                        raw_record = self._map_raw_listing(
                            item=item,
                            detail=detail_data,
                            detail_source=detail_source,
                            raw_detail_json=raw_detail_json,
                        )
                        records.append(raw_record)
            else:
                for item in page_items_to_process:
                    raw_record = self._map_raw_listing(item=item)
                    records.append(raw_record)

            if stop_on_seen and historical_seen and new_on_page == 0:
                logger.info("Full page already in storage — incremental sync complete.")
                break

            if total_available and len(records) >= total_available:
                logger.info(f"All {total_available} listings collected.")
                break

            offset += limit
            time.sleep(self.delay)

        logger.info(f"Scrape complete. Collected {len(records)} records in this batch.")
        return records
