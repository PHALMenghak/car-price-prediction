-- dbt/models/marts/fct_car_listings.sql
-- Analytics Mart: Validated active car listings for dashboards and market intelligence reporting.
-- Grain: 1 record per unique listing_id (latest active snapshot).

{{ config(
    materialized = 'table',
    post_hook    = [
        "COPY {{ this }} TO 'data/gold/fct_car_listings.parquet' (FORMAT PARQUET)"
    ]
) }}

WITH latest_active AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY listing_id
            ORDER BY scraped_at DESC
        ) AS _active_rank
    FROM {{ ref('int_cars_cleaned') }}
    WHERE data_quality_status IN ('VALID', 'WARNING')
)

SELECT
    listing_id,
    vehicle_brand,
    vehicle_model,
    vehicle_year,
    price,
    initial_price,
    price_drop_amount,
    has_price_drop,
    vehicle_mileage_km,
    vehicle_engine_cc,
    vehicle_fuel_type,
    vehicle_transmission,
    vehicle_color,
    vehicle_condition,
    vehicle_tax_type,
    vehicle_body_type,
    province,
    district,
    seller_type,
    seller_name,
    has_full_option,
    is_urgent_sale,
    days_on_market,
    posted_at,
    scraped_at,
    scrape_date,
    data_quality_status,
    data_quality_reasons

FROM latest_active
WHERE _active_rank = 1
