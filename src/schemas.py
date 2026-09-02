# src/schemas.py — Pydantic v2 data models for Khmer24 raw car listings
# Implements 100% untouched raw data ingestion for Bronze layer storage.

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RawCarListing(BaseModel):
    """
    Structured raw record for a single Khmer24 car listing snapshot.

    Captures untouched raw data directly from both the Feed API and Detail Page
    (REST API or Nuxt HTML fallback) without premature regex cleaning, normalization,
    or type coercion. Downstream cleaning is performed entirely in dbt.
    """

    # ── 1. Identity & Pricing ──────────────────────────────────────────────────
    listing_id: str
    raw_title: Optional[str] = None
    raw_price: Optional[str] = None
    raw_currency: Optional[str] = "USD"

    # ── 2. Raw Vehicle Specs (Direct from Detail Page / Feed Specs) ─────────────
    raw_spec_brand: Optional[str] = None
    raw_spec_model: Optional[str] = None
    raw_spec_year: Optional[str] = None
    raw_spec_mileage: Optional[str] = None
    raw_spec_engine_size: Optional[str] = None
    raw_spec_fuel_type: Optional[str] = None
    raw_spec_transmission: Optional[str] = None
    raw_spec_color: Optional[str] = None
    raw_spec_condition: Optional[str] = None
    raw_spec_tax_type: Optional[str] = None
    raw_spec_steering: Optional[str] = None
    raw_spec_body_type: Optional[str] = None

    # ── 3. Location ─────────────────────────────────────────────────────────────
    raw_province: Optional[str] = None
    raw_district: Optional[str] = None

    # ── 4. Seller & Contact ─────────────────────────────────────────────────────
    seller_id: Optional[str] = None
    seller_name: Optional[str] = None
    seller_type_code: Optional[str] = None     # "1" = individual, "2" = store/business
    seller_username: Optional[str] = None
    seller_phones: List[str] = Field(default_factory=list)

    # ── 5. Content & Media ──────────────────────────────────────────────────────
    raw_description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    listing_url: Optional[str] = None
    images: List[str] = Field(default_factory=list)

    # ── 6. Timestamps & Ingestion Lineage ───────────────────────────────────────
    view_count: int = 0
    posted_at: Optional[str] = None
    renewed_at: Optional[str] = None
    scraped_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    detail_source: Optional[str] = None       # "rest_api" | "nuxt_html" | "none"
    has_detail: bool = False

    # ── 7. Full Audit JSON Blobs (Complete Source Payloads) ─────────────────────
    raw_feed_payload: Optional[str] = None
    raw_detail_payload: Optional[str] = None


# Backward compatibility alias
AdListingModel = RawCarListing
