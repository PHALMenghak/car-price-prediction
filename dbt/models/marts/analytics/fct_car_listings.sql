-- dbt/models/marts/analytics/fct_car_listings.sql
-- Analytics Mart: Curated active car listings for dashboards, BI, and market intelligence reporting.
-- Grain: 1 record per unique listing_id (latest clean active snapshot), enriched with canonical vehicle deduplication.

{{ config(
    materialized = 'table',
    post_hook    = [
        "COPY {{ this }} TO 'data/gold/fct_car_listings.parquet' (FORMAT PARQUET)"
    ]
) }}

WITH ranked_snapshots AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY listing_id
            ORDER BY scraped_at DESC
        ) AS _snapshot_recency_rank
    FROM {{ ref('int_cars_cleaned') }}
    WHERE data_quality_status IN ('VALID', 'WARNING')
),

latest_listings AS (
    SELECT * FROM ranked_snapshots WHERE _snapshot_recency_rank = 1
),

vehicle_clusters AS (
    SELECT
        *,
        COUNT(*) OVER (
            PARTITION BY COALESCE(NULLIF(seller_phones, ''), NULLIF(seller_name, ''), listing_id), vehicle_brand, vehicle_model, vehicle_year, price
        ) AS repost_count,
        ROW_NUMBER() OVER (
            PARTITION BY COALESCE(NULLIF(seller_phones, ''), NULLIF(seller_name, ''), listing_id), vehicle_brand, vehicle_model, vehicle_year, price
            ORDER BY posted_at DESC, scraped_at DESC
        ) AS _vehicle_rank
    FROM latest_listings
)

SELECT
    listing_id,

    -- Dimensional Foreign Keys (Star Schema)
    MD5(
        LOWER(TRIM(vehicle_brand)) || '||' ||
        LOWER(TRIM(vehicle_model)) || '||' ||
        LOWER(TRIM(COALESCE(vehicle_body_type, 'unspecified')))
    ) AS model_key,
    MD5(
        LOWER(TRIM(province)) || '||' ||
        LOWER(TRIM(COALESCE(district, 'unspecified')))
    ) AS location_key,
    MD5(
        COALESCE(
            NULLIF(TRIM(seller_phones), ''),
            NULLIF(TRIM(seller_name), ''),
            'unspecified'
        )
    ) AS seller_key,
    MD5(
        LOWER(TRIM(COALESCE(vehicle_fuel_type, 'unspecified'))) || '||' ||
        LOWER(TRIM(COALESCE(vehicle_transmission, 'unspecified'))) || '||' ||
        LOWER(TRIM(COALESCE(vehicle_tax_type, 'unspecified'))) || '||' ||
        LOWER(TRIM(COALESCE(vehicle_color, 'unspecified')))
    ) AS spec_key,

    -- Degenerate Attributes & Descriptive Context (Hybrid Star Schema)
    vehicle_brand,
    brand_tier,
    vehicle_model,
    vehicle_year,
    vehicle_age,
    price,
    initial_price,
    price_drop_amount,
    has_price_drop,
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
    days_on_market,
    posted_at,
    scrape_date,
    scraped_at,
    data_quality_status,
    data_quality_reasons,
    repost_count,
    1 AS is_canonical_vehicle

FROM vehicle_clusters
WHERE _vehicle_rank = 1
