-- dbt/models/staging/stg_khmer24_cars.sql
-- Ingests raw Parquet snapshots from Khmer24 while preserving the historical daily snapshot grain (listing_id + scrape_date).
-- Removes only intra-day duplicate scrapes (same listing on the same date).

WITH raw_snapshots AS (
    SELECT *
    FROM read_parquet('data/bronze/cars_*.parquet', union_by_name=true)
),

ranked_snapshots AS (
    SELECT
        listing_id,
        raw_title,
        TRY_CAST(raw_price AS DOUBLE)                               AS price,
        raw_price                                                   AS price_raw,
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
        posted_at,
        scraped_at,
        TRY_CAST(scraped_at AS DATE)                                AS scrape_date,

        -- Intra-day deduplication: keep latest scrape per day per listing
        ROW_NUMBER() OVER (
            PARTITION BY listing_id, TRY_CAST(scraped_at AS DATE)
            ORDER BY scraped_at DESC
        ) AS _intra_day_row_num,

        -- Longitudinal initial price & first observed post time across all time
        MIN(posted_at) OVER (PARTITION BY listing_id) AS _first_posted_at,
        FIRST_VALUE(TRY_CAST(raw_price AS DOUBLE)) OVER (
            PARTITION BY listing_id
            ORDER BY scraped_at ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS _initial_price

    FROM raw_snapshots
    WHERE listing_id IS NOT NULL
)

SELECT
    listing_id,
    raw_title,
    price,
    price_raw,
    _initial_price                                                  AS initial_price,
    GREATEST(_initial_price - price, 0.0)                           AS price_drop_amount,
    CASE WHEN (_initial_price - price) > 0 THEN 1 ELSE 0 END        AS has_price_drop,

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

    raw_description,
    thumbnail_url,
    listing_url,

    ROUND(
        GREATEST(
            DATE_DIFF('second', TRY_CAST(_first_posted_at AS TIMESTAMPTZ), TRY_CAST(scraped_at AS TIMESTAMPTZ)) / 86400.0,
            0.0
        ),
        1
    ) AS days_on_market,

    posted_at,
    scraped_at,
    scrape_date

FROM ranked_snapshots
WHERE _intra_day_row_num = 1
