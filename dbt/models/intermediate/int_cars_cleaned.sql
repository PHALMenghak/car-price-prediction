-- dbt/models/intermediate/int_cars_cleaned.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- SILVER LAYER: Deterministic cleaning, regex parsing, & physical spec validation
-- ─────────────────────────────────────────────────────────────────────────────
-- Transforms raw Bronze staging data into clean, validated vehicle records.
-- Applies:
--   1. Regex brand and canonical model matching from raw specs and title
--   2. Multilingual spec normalization (Khmer + English -> standardized tokens)
--   3. Unit parsing (mileage km, engine cc) with physical clamping
--   4. Hard price bounds: $500 ≤ price ≤ $300,000
--   5. Model year sanity bounds: 1990 ≤ year ≤ current_year+1
-- Materialization: view with post-hook export to data/silver/cars_cleaned.parquet

{{ config(
    materialized = 'view',
    post_hook    = [
        "COPY {{ this }} TO 'data/silver/cars_cleaned.parquet' (FORMAT PARQUET)",
        "COPY {{ this }} TO 'data/silver/cars_cleaned.csv' (HEADER, DELIMITER ',')"
    ]
) }}

WITH staging AS (
    SELECT * FROM {{ ref('stg_khmer24_cars') }}
),

parsed_entities AS (
    SELECT
        listing_id,
        raw_title AS listing_title,
        price,
        initial_price,
        price_drop_amount,
        has_price_drop,
        price_increase_amount,
        has_price_increase,
        days_on_market,

        -- ── Brand & Model ─────────────────────────────────────────────────────
        {{ extract_brand_from_raw('raw_spec_brand', 'raw_title') }} AS vehicle_brand,

        -- Model Year
        COALESCE(
            TRY_CAST(raw_spec_year AS INTEGER),
            TRY_CAST(REGEXP_EXTRACT(raw_title, '\b(19[9][0-9]|20[0-2][0-9])\b', 1) AS INTEGER)
        ) AS vehicle_model_year,

        -- ── Spec Parsers ──────────────────────────────────────────────────────
        {{ parse_raw_mileage('raw_spec_mileage') }} AS _parsed_mileage,
        {{ parse_raw_engine_cc('raw_spec_engine_size', 'raw_title') }} AS _parsed_engine_cc,
        {{ normalize_raw_color('raw_spec_color', 'raw_title') }} AS vehicle_color,
        {{ normalize_raw_transmission('raw_spec_transmission', 'raw_title') }} AS vehicle_transmission,
        {{ normalize_raw_tax_type('raw_spec_tax_type') }} AS vehicle_tax_type,
        {{ normalize_raw_condition('raw_spec_condition') }} AS vehicle_condition,
        raw_spec_body_type,

        -- ── Location & Seller ─────────────────────────────────────────────────
        COALESCE(NULLIF(TRIM(raw_province), ''), 'Phnom Penh') AS province,
        raw_district AS district,
        seller_type,
        seller_id,
        seller_name,
        seller_username,
        seller_phones,

        -- ── Content & Timestamps ──────────────────────────────────────────────
        raw_description AS description,
        thumbnail_url,
        listing_url,
        posted_at,
        scraped_at,
        renewed_at,
        raw_spec_model,
        raw_spec_fuel_type,
        raw_title

    FROM staging
),

conformed AS (
    SELECT
        listing_id,
        listing_title,
        price,
        initial_price,
        price_drop_amount,
        has_price_drop,
        price_increase_amount,
        has_price_increase,
        days_on_market,

        -- Final brand & model
        vehicle_brand,
        {{ extract_model_from_raw('raw_spec_model', 'raw_title', 'vehicle_brand') }} AS vehicle_model,
        vehicle_model_year,

        -- Physical spec clamping
        CASE
            WHEN _parsed_mileage < 0 OR _parsed_mileage > 500000 THEN NULL
            ELSE _parsed_mileage
        END AS vehicle_mileage_km,

        CASE
            WHEN _parsed_engine_cc < 500 OR _parsed_engine_cc > 7000 THEN NULL
            ELSE _parsed_engine_cc
        END AS vehicle_engine_cc,

        raw_spec_fuel_type,
        vehicle_transmission,
        vehicle_color,
        vehicle_condition,
        vehicle_tax_type,
        raw_spec_body_type AS vehicle_body_type,

        province,
        district,
        seller_type,
        seller_id,
        seller_name,
        seller_username,
        seller_phones,
        description,
        thumbnail_url,
        listing_url,
        posted_at,
        scraped_at,
        renewed_at

    FROM parsed_entities
)

SELECT
    listing_id,
    listing_title,
    price,
    initial_price,
    price_drop_amount,
    has_price_drop,
    price_increase_amount,
    has_price_increase,
    days_on_market,
    vehicle_brand,
    vehicle_model,
    vehicle_model_year,
    vehicle_mileage_km,
    vehicle_engine_cc,
    {{ normalize_raw_fuel_type('raw_spec_fuel_type', 'listing_title', 'vehicle_brand', 'vehicle_model') }} AS vehicle_fuel_type,
    vehicle_transmission,
    vehicle_color,
    vehicle_condition,
    vehicle_tax_type,
    vehicle_body_type,
    province,
    district,
    seller_type,
    seller_id,
    seller_name,
    seller_username,
    seller_phones,
    description,
    thumbnail_url,
    listing_url,
    posted_at,
    scraped_at,
    renewed_at

FROM conformed
WHERE
    -- Rule 1: Price must be valid Cambodian automotive range
    price IS NOT NULL
    AND price >= 500
    AND price <= 300000
    -- Rule 2: Model year either null (hierarchically imputed in Gold) or plausible
    AND (
        vehicle_model_year IS NULL
        OR vehicle_model_year BETWEEN 1990 AND (date_part('year', CURRENT_DATE) + 1)
    )
