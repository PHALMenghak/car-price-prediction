-- dbt/models/staging/stg_khmer24_cars.sql
-- Thin Bronze-to-Staging Ingestion Model for Khmer24 Car Listings.
-- Responsibilities: Ingestion, schema casting, timestamp normalization, intra-day deduplication.
-- Preserves all raw source fields without business transformation or longitudinal calculations.
-- Grain: 1 listing_id x 1 scrape_date.

WITH raw_snapshots AS (
    SELECT *
    FROM {{ source('bronze', 'cars') }}
),

ranked_snapshots AS (
    SELECT
        TRIM(CAST(listing_id AS VARCHAR))                               AS listing_id,
        raw_title,
        TRY_CAST(raw_price AS DOUBLE)                                   AS price,
        raw_price                                                       AS price_raw,
        raw_currency,
        raw_spec_brand,
        raw_spec_model,
        raw_spec_year,
        raw_spec_mileage,
        raw_spec_engine_size,
        raw_spec_fuel_type,
        raw_spec_transmission,
        raw_spec_color,
        raw_spec_condition,
        raw_spec_tax_type,
        raw_spec_body_type,
        raw_province,
        raw_district,
        seller_id,
        seller_name,
        CASE WHEN seller_type_code = '2' THEN 'store' ELSE 'individual' END AS seller_type,
        seller_username,
        seller_phones,
        raw_description,
        thumbnail_url,
        listing_url,
        TRY_CAST(posted_at AS TIMESTAMPTZ)                              AS posted_at,
        TRY_CAST(scraped_at AS TIMESTAMPTZ)                             AS scraped_at,
        TRY_CAST(scraped_at AS DATE)                                    AS scrape_date,

        -- Intra-day deduplication: keep latest scrape per day per listing
        ROW_NUMBER() OVER (
            PARTITION BY listing_id, TRY_CAST(scraped_at AS DATE)
            ORDER BY scraped_at DESC
        ) AS _intra_day_row_num

    FROM raw_snapshots
    WHERE listing_id IS NOT NULL
)

SELECT
    listing_id,
    scrape_date,
    scraped_at,
    posted_at,
    price,
    price_raw,
    raw_currency,
    raw_title,
    raw_description,
    raw_spec_brand,
    raw_spec_model,
    raw_spec_year,
    raw_spec_mileage,
    raw_spec_engine_size,
    raw_spec_fuel_type,
    raw_spec_transmission,
    raw_spec_color,
    raw_spec_condition,
    raw_spec_tax_type,
    raw_spec_body_type,
    raw_province,
    raw_district,
    seller_id,
    seller_name,
    seller_type,
    seller_username,
    seller_phones,
    thumbnail_url,
    listing_url

FROM ranked_snapshots
WHERE _intra_day_row_num = 1
