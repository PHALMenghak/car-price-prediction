-- dbt/models/staging/stg_khmer24_cars.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- BRONZE LAYER: Multi-day snapshot ingestion, deduplication & market signals
-- ─────────────────────────────────────────────────────────────────────────────
-- Reads all daily raw Parquet snapshots from data/raw/cars_*.parquet via DuckDB.
-- Deduplicates listings across scrape dates using ROW_NUMBER() window function.
-- Generates longitudinal time-series market signals per listing_id:
--   • days_on_market  — how long the listing has been active
--   • initial_price   — first observed price (to detect price drops)
--   • price_drop_amount / has_price_drop — seller negotiation signals
--   • view_velocity   — views/day as a demand proxy
-- Materialization: view (no storage cost, always fresh on query)

WITH raw_snapshots AS (
    SELECT *
    FROM read_parquet('data/raw/cars_*.parquet')
),

ranked_snapshots AS (
    SELECT
        listing_id,
        listing_title,
        price,
        vehicle_brand,
        vehicle_model,
        vehicle_model_year,
        vehicle_condition,
        vehicle_tax_type,
        vehicle_fuel_type,
        vehicle_transmission,
        vehicle_color,
        vehicle_mileage_km,
        vehicle_engine_cc,
        province,
        seller_type,
        seller_id,
        seller_name,
        view_count,
        posted_at,
        scraped_at,
        renewed_at,

        -- ── Deduplication rank: latest snapshot wins ──────────────────────
        ROW_NUMBER() OVER (
            PARTITION BY listing_id
            ORDER BY scraped_at DESC
        ) AS _row_num,

        -- ── Time-series market dynamics aggregated per listing ────────────
        MIN(posted_at) OVER (
            PARTITION BY listing_id
        ) AS _first_posted_at,

        -- Initial price (oldest observed snapshot)
        FIRST_VALUE(price) OVER (
            PARTITION BY listing_id
            ORDER BY scraped_at ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS _initial_price

    FROM raw_snapshots
    WHERE listing_id IS NOT NULL
)

SELECT
    listing_id,
    listing_title,

    -- ── Price & Price-Drop Signals ────────────────────────────────────────
    TRY_CAST(price AS DOUBLE)                                     AS price,
    TRY_CAST(_initial_price AS DOUBLE)                            AS initial_price,
    GREATEST(
        TRY_CAST(_initial_price AS DOUBLE) - TRY_CAST(price AS DOUBLE),
        0.0
    )                                                             AS price_drop_amount,
    CASE
        WHEN (TRY_CAST(_initial_price AS DOUBLE) - TRY_CAST(price AS DOUBLE)) > 0
        THEN 1 ELSE 0
    END                                                           AS has_price_drop,

    -- ── Temporal Market Signals ───────────────────────────────────────────
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

    -- View velocity: views per day on market (demand proxy)
    ROUND(
        COALESCE(TRY_CAST(view_count AS DOUBLE), 0.0) /
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

    -- ── Vehicle Core Fields (type-cast & default fill) ────────────────────
    TRIM(COALESCE(NULLIF(vehicle_brand, ''), 'Unknown'))          AS vehicle_brand,
    TRIM(COALESCE(NULLIF(vehicle_model, ''), 'Unknown'))          AS vehicle_model,
    TRY_CAST(vehicle_model_year AS INTEGER)                       AS vehicle_model_year,
    LOWER(TRIM(COALESCE(NULLIF(vehicle_condition, ''), 'used')))  AS vehicle_condition,
    TRIM(COALESCE(NULLIF(vehicle_tax_type, ''), 'Unknown'))       AS vehicle_tax_type,
    TRIM(COALESCE(NULLIF(vehicle_fuel_type, ''), 'Unknown'))      AS vehicle_fuel_type,
    TRIM(COALESCE(NULLIF(vehicle_transmission, ''), 'Unknown'))   AS vehicle_transmission,
    TRIM(COALESCE(NULLIF(vehicle_color, ''), 'Unknown'))          AS vehicle_color,
    TRY_CAST(vehicle_mileage_km AS DOUBLE)                        AS vehicle_mileage_km,
    TRY_CAST(vehicle_engine_cc AS DOUBLE)                         AS vehicle_engine_cc,

    -- ── Location & Seller ─────────────────────────────────────────────────
    TRIM(COALESCE(NULLIF(province, ''), 'Unknown'))               AS province,
    LOWER(TRIM(COALESCE(NULLIF(seller_type, ''), 'individual')))  AS seller_type,
    seller_id,
    seller_name,
    COALESCE(TRY_CAST(view_count AS INTEGER), 0)                  AS view_count,

    -- ── Timestamps ────────────────────────────────────────────────────────
    TRY_CAST(posted_at AS TIMESTAMPTZ)                            AS posted_at,
    TRY_CAST(scraped_at AS TIMESTAMPTZ)                           AS scraped_at,
    TRY_CAST(renewed_at AS TIMESTAMPTZ)                           AS renewed_at

FROM ranked_snapshots
WHERE _row_num = 1  -- Keep only the most recent snapshot per listing
