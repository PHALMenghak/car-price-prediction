-- dbt/models/intermediate/int_cars_cleaned.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- SILVER LAYER: Deterministic sanity filtering & physical spec validation
-- ─────────────────────────────────────────────────────────────────────────────
-- Receives deduplicated Bronze data from stg_khmer24_cars.
-- Applies business rules that enforce data integrity:
--   1. Hard price bounds: $500 ≤ price ≤ $300,000 (drop rows outside range)
--   2. Model year bounds: 1990 ≤ year ≤ current_year+1 (null rows preserved)
--   3. Mileage clamping: outside 0–500,000 km becomes NULL (imputed in Gold)
--   4. Engine CC clamping: outside 500–7,000 cc becomes NULL (imputed in Gold)
--   5. Exports clean un-imputed dataset to data/processed/cars_clean.parquet for EDA
-- Materialization: view (with parquet & csv export post-hooks)

{{ config(
    materialized = 'view',
    post_hook    = [
        "COPY {{ this }} TO 'data/processed/cars_clean.parquet' (FORMAT PARQUET)",
        "COPY {{ this }} TO 'data/processed/cars_clean.csv' (HEADER, DELIMITER ',')"
    ]
) }}

WITH staging AS (
    SELECT * FROM {{ ref('stg_khmer24_cars') }}
)

SELECT
    -- ── Identifiers & Raw Text ────────────────────────────────────────────
    listing_id,
    listing_title,

    -- ── Validated Pricing & Market Time ───────────────────────────────────
    price,
    initial_price,
    price_drop_amount,
    has_price_drop,
    price_increase_amount,
    has_price_increase,
    days_on_market,
    view_velocity,
    view_count,

    -- ── Vehicle Core Specifications (Preserved with authentic NULLs) ──────
    COALESCE(NULLIF(TRIM(vehicle_brand), ''), 'Unknown')          AS vehicle_brand,
    COALESCE(NULLIF(TRIM(vehicle_model), ''), 'Unknown')          AS vehicle_model,
    vehicle_model_year,   -- NULL allowed; hierarchical imputation in Gold

    -- Physical Spec Clamping: out-of-range → NULL (not row-dropped)
    CASE
        WHEN vehicle_mileage_km < 0 OR vehicle_mileage_km > 500000 THEN NULL
        ELSE vehicle_mileage_km
    END                                                           AS vehicle_mileage_km,

    CASE
        WHEN vehicle_engine_cc < 500 OR vehicle_engine_cc > 7000 THEN NULL
        ELSE vehicle_engine_cc
    END                                                           AS vehicle_engine_cc,

    vehicle_fuel_type,
    vehicle_transmission,
    vehicle_color,
    vehicle_condition,
    vehicle_tax_type,

    -- ── Location & Seller ─────────────────────────────────────────────────
    province,
    seller_type,
    seller_id,

    -- ── Timestamps ────────────────────────────────────────────────────────
    posted_at,
    scraped_at

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

