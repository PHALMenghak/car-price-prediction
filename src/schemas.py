# src/schemas.py — Pydantic v2 data-validation models for Khmer24 car listings

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class CategoryModel(BaseModel):
    id: Optional[str] = None
    en_name: Optional[str] = None
    slug: Optional[str] = None


class LocationModel(BaseModel):
    id: Optional[str] = None
    en_name: Optional[str] = None        # Province  (e.g. "Phnom Penh")
    en_name2: Optional[str] = None       # "District, Province"
    en_name3: Optional[str] = None       # "Commune, District, Province"
    slug: Optional[str] = None


class UserModel(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    username: Optional[str] = None
    user_type: Optional[str] = None      # "1" = individual, "2" = store/business


class AdListingModel(BaseModel):
    """
    Validated record for a single Khmer24 car listing.

    All fields needed for downstream ML modeling are captured here.
    The `raw_specs` dict stores the raw highlight_specs payload so future
    feature engineering can extract additional structured fields without
    re-scraping.
    """

    listing_id: str
    listing_title: str
    price: Optional[float] = None
    currency: str = "USD"
    discount_price: Optional[float] = None
    is_premium: Optional[bool] = None

    # ── Category ──────────────────────────────────────────────────────────────
    category: Optional[str] = None
    category_slug: Optional[str] = None

    # ── Location ──────────────────────────────────────────────────────────────
    province: Optional[str] = None
    province_slug: Optional[str] = None
    district: Optional[str] = None
    location_full: Optional[str] = None

    # ── Seller ────────────────────────────────────────────────────────────────
    seller_id: Optional[str] = None
    seller_name: Optional[str] = None
    seller_type: Optional[str] = None    # "individual" | "store"
    seller_username: Optional[str] = None

    # ── Contact ───────────────────────────────────────────────────────────────
    seller_phones: List[str] = Field(default_factory=list)

    # ── Listing metadata ──────────────────────────────────────────────────────
    view_count: int = 0
    posted_at: Optional[str] = None
    renewed_at: Optional[str] = None
    thumbnail_url: Optional[str] = None
    listing_url: Optional[str] = None

    # ── Vehicle-specific fields (parsed from highlight_specs) ─────────────────
    vehicle_model_year: Optional[int] = None
    vehicle_condition: Optional[str] = None   # "used" | "new"
    vehicle_tax_type: Optional[str] = None    # "Imported" | "Local" | ...
    vehicle_brand: Optional[str] = None
    vehicle_model: Optional[str] = None

    # ── Extra specs extracted from highlight_specs blob ───────────────────────
    vehicle_mileage_km: Optional[int] = None      # odometer reading in km
    vehicle_fuel_type: Optional[str] = None       # "Petrol" | "Diesel" | "Electric" | ...
    vehicle_transmission: Optional[str] = None    # "Automatic" | "Manual"
    vehicle_engine_cc: Optional[int] = None       # engine displacement in cc
    vehicle_color: Optional[str] = None           # exterior color

    # ── Raw specs dict — full API payload for future extension ────────────────
    raw_specs: Optional[Dict[str, Any]] = Field(default=None)

    # ── Scrape timestamp (Fix #5) ─────────────────────────────────────────────
    scraped_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # ── Validators ────────────────────────────────────────────────────────────

    @field_validator("price", "discount_price", mode="before")
    @classmethod
    def clean_price(cls, v):
        """Strip currency symbols and coerce to float; returns None for zero/empty."""
        if v is None or v == "" or v == "0.00":
            return None
        if isinstance(v, (int, float)):
            return float(v) if float(v) > 0 else None
        s = str(v).replace("$", "").replace(",", "").strip()
        try:
            val = float(s)
            return val if val > 0 else None
        except ValueError:
            return None

    @field_validator("vehicle_model_year", mode="before")
    @classmethod
    def clean_year(cls, v):
        """Coerce year strings to int; reject implausible values."""
        if v is None:
            return None
        try:
            year = int(str(v).strip())
            return year if 1980 <= year <= 2027 else None
        except (ValueError, TypeError):
            return None

    @field_validator("vehicle_mileage_km", "vehicle_engine_cc", mode="before")
    @classmethod
    def clean_int_spec(cls, v):
        """Coerce integer spec values; return None on failure."""
        if v is None:
            return None
        try:
            return int(float(str(v).replace(",", "").strip()))
        except (ValueError, TypeError):
            return None
