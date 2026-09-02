-- dbt/models/marts/core/fct_car_listings.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- GOLD LAYER (FACT TABLE): Central Star Schema Fact Table for Car Listings
-- ─────────────────────────────────────────────────────────────────────────────

{{ config(
    materialized = 'table',
    post_hook    = [
        "COPY {{ this }} TO 'data/gold/fct_car_listings.parquet' (FORMAT PARQUET)"
    ]
) }}

WITH silver AS (
    SELECT * FROM {{ ref('int_cars_cleaned') }}
)

SELECT
    -- ── Primary Key ──────────────────────────────────────────────────────────
    listing_id,

    -- ── Foreign Keys to Dimension Tables ─────────────────────────────────────
    MD5(CONCAT(COALESCE(CAST(vehicle_brand AS VARCHAR), 'Unknown'), '||', COALESCE(CAST(vehicle_model AS VARCHAR), 'Unknown'), '||', COALESCE(CAST(vehicle_body_type AS VARCHAR), 'Unknown'))) AS model_key,
    MD5(CONCAT(COALESCE(CAST(province AS VARCHAR), 'Phnom Penh'), '||', COALESCE(CAST(district AS VARCHAR), 'Unknown'))) AS location_key,
    MD5(COALESCE(CAST(seller_id AS VARCHAR), 'UNKNOWN')) AS seller_key,
    MD5(CONCAT(COALESCE(CAST(vehicle_fuel_type AS VARCHAR), 'Unknown'), '||', COALESCE(CAST(vehicle_transmission AS VARCHAR), 'Automatic'), '||', CAST(COALESCE(vehicle_engine_cc, 0) AS VARCHAR))) AS powertrain_key,

    -- ── Measures & Pricing Dynamics ──────────────────────────────────────────
    price,
    initial_price,
    price_drop_amount,
    has_price_drop,
    price_increase_amount,
    has_price_increase,

    -- ── Physical & Age Metrics ───────────────────────────────────────────────
    vehicle_model_year,
    vehicle_mileage_km,
    vehicle_color,
    vehicle_condition,
    vehicle_tax_type,

    -- ── Engagement & Market Liquidity ─────────────────────────────────────────
    days_on_market,
    view_count,
    view_velocity,

    -- ── Timestamps ────────────────────────────────────────────────────────────
    posted_at,
    scraped_at

FROM silver
