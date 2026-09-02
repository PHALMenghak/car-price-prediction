-- dbt/models/staging/stg_khmer24_cars.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- BRONZE LAYER (STAGING): Multi-day raw snapshot ingestion & deduplication
-- ─────────────────────────────────────────────────────────────────────────────
-- Reads daily raw Parquet snapshots from data/bronze/cars_*.parquet via DuckDB.
-- Deduplicates listings across scrape dates using latest snapshot.
-- Generates longitudinal time-series market signals:
--   • days_on_market  — how long the listing has been active
--   • initial_price   — first observed price (to detect price drops)
--   • price_drop_amount / has_price_drop — seller negotiation signals
--   • view_velocity   — views/day as a demand proxy
-- Materialization: view (no storage cost, always fresh on query)

WITH raw_snapshots AS (
    SELECT *
    FROM read_parquet('data/bronze/cars_*.parquet', union_by_name=true)
),

ranked_snapshots AS (
    SELECT
        listing_id,
        raw_title,
        TRY_CAST(raw_price AS DOUBLE) AS price,
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
        raw_spec_steering,
        raw_spec_body_type,
        raw_province,
        raw_district,
        seller_id,
        seller_name,
        seller_type_code,
        seller_username,
        seller_phones,
        raw_description,
        thumbnail_url,
        listing_url,
        TRY_CAST(view_count AS BIGINT) AS view_count,
        posted_at,
        scraped_at,
        renewed_at,

        -- ── Deduplication rank: latest snapshot wins ──────────────────────────
        ROW_NUMBER() OVER (
            PARTITION BY listing_id
            ORDER BY scraped_at DESC
        ) AS _row_num,

        -- ── Longitudinal aggregation ──────────────────────────────────────────
        MIN(posted_at) OVER (
            PARTITION BY listing_id
        ) AS _first_posted_at,

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

    -- ── Price & Price-Change Signals ─────────────────────────────────────────
    price,
    _initial_price                                                AS initial_price,
    GREATEST(_initial_price - price, 0.0)                         AS price_drop_amount,
    CASE WHEN (_initial_price - price) > 0 THEN 1 ELSE 0 END      AS has_price_drop,
    GREATEST(price - _initial_price, 0.0)                         AS price_increase_amount,
    CASE WHEN (price - _initial_price) > 0 THEN 1 ELSE 0 END      AS has_price_increase,

    -- ── Specifications ───────────────────────────────────────────────────────
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
    raw_spec_steering,
    raw_spec_body_type,

    -- ── Location & Seller ────────────────────────────────────────────────────
    raw_province,
    raw_district,
    seller_id,
    seller_name,
    CASE WHEN seller_type_code = '2' THEN 'store' ELSE 'individual' END AS seller_type,
    seller_username,
    seller_phones,

    -- ── Content ──────────────────────────────────────────────────────────────
    raw_description,
    thumbnail_url,
    listing_url,

    -- ── Longitudinal Market Dynamics ─────────────────────────────────────────
    ROUND(
        GREATEST(
            DATE_DIFF(
                'second',
                TRY_CAST(_first_posted_at AS TIMESTAMPTZ),
                TRY_CAST(scraped_at AS TIMESTAMPTZ)
            ) / 86400.0,
            0.0
        ),
        1
    )                                                             AS days_on_market,

    ROUND(
        COALESCE(view_count, 0) /
        GREATEST(
            DATE_DIFF(
                'second',
                TRY_CAST(_first_posted_at AS TIMESTAMPTZ),
                TRY_CAST(scraped_at AS TIMESTAMPTZ)
            ) / 86400.0,
            1.0
        ),
        2
    )                                                             AS view_velocity,

    COALESCE(view_count, 0)                                       AS view_count,
    posted_at,
    scraped_at,
    renewed_at

FROM ranked_snapshots
WHERE _row_num = 1
