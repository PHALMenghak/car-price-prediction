-- dbt/models/intermediate/int_cars_cleaned.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- SILVER LAYER: Deterministic sanity filtering & physical spec validation
-- ─────────────────────────────────────────────────────────────────────────────
-- Receives deduplicated Bronze data from stg_khmer24_cars.
-- Applies business rules that enforce data integrity for ML model training:
--   1. Hard price bounds: $500 ≤ price ≤ $300,000 (drop rows outside range)
--   2. Model year bounds: 1990 ≤ year ≤ current_year+1 (null rows preserved)
--   3. Mileage clamping: outside 0–500,000 km becomes NULL (imputed in Gold)
--   4. Engine CC clamping: outside 500–7,000 cc becomes NULL (imputed in Gold)
--   5. Final categorical nullability guard for all string dimensions
-- Materialization: view (chained from staging view — no redundant storage)

WITH staging AS (
    SELECT * FROM {{ ref('stg_khmer24_cars') }}
)

SELECT
    -- ── Identifiers & Raw Text ────────────────────────────────────────────
    listing_id,
    listing_title,

    -- ── Price Signals (pass-through; filtering in WHERE clause) ──────────
    price,
    initial_price,
    price_drop_amount,
    has_price_drop,

    -- ── Temporal Market Signals ───────────────────────────────────────────
    days_on_market,
    view_velocity,
    view_count,

    -- ── Vehicle Dimensions ────────────────────────────────────────────────
    COALESCE(NULLIF(TRIM(vehicle_brand), ''), 'Unknown')          AS vehicle_brand,
    COALESCE(NULLIF(TRIM(vehicle_model), ''), 'Unknown')          AS vehicle_model,
    vehicle_model_year,   -- NULL allowed; hierarchical imputation in Gold
    vehicle_condition,
    vehicle_tax_type,
    vehicle_fuel_type,
    vehicle_transmission,
    vehicle_color,

    -- ── Physical Spec Clamping: out-of-range → NULL (not row-dropped) ─────
    -- Mileage: physically impossible values (negative or > 500,000 km) → NULL
    CASE
        WHEN vehicle_mileage_km < 0 OR vehicle_mileage_km > 500000 THEN NULL
        ELSE vehicle_mileage_km
    END AS vehicle_mileage_km,

    -- Engine CC: implausible values (< 500 or > 7,000 cc) → NULL
    CASE
        WHEN vehicle_engine_cc < 500 OR vehicle_engine_cc > 7000 THEN NULL
        ELSE vehicle_engine_cc
    END AS vehicle_engine_cc,

    -- ── Location & Seller ─────────────────────────────────────────────────
    province,
    seller_type,
    seller_id,
    seller_name,

    -- ── Timestamps ────────────────────────────────────────────────────────
    posted_at,
    scraped_at,
    renewed_at

FROM staging
WHERE
    -- Rule 1: Price must exist and be within the realistic Cambodian market range
    price IS NOT NULL
    AND price >= 500
    AND price <= 300000
    -- Rule 2: Model year either null (will be imputed) or within plausible vehicle age
    AND (
        vehicle_model_year IS NULL
        OR vehicle_model_year BETWEEN 1990 AND (date_part('year', CURRENT_DATE) + 1)
    )
