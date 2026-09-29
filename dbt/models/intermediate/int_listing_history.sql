-- dbt/models/intermediate/int_listing_history.sql
-- Dedicated longitudinal tracking and lifecycle metrics for Cambodian car listings.
-- Grain: 1 listing_id x 1 scrape_date.
-- Strictly leakage-free: Point-in-time calculation ensures historical records remain historically accurate.

{{ config(materialized = 'view') }}

WITH staging AS (
    SELECT
        listing_id,
        scrape_date,
        scraped_at,
        posted_at,
        price
    FROM {{ ref('stg_khmer24_cars') }}
),

ordered_history AS (
    SELECT
        listing_id,
        scrape_date,
        scraped_at,
        posted_at,
        price,

        -- Earliest and latest observed dates across the whole lifecycle
        MIN(scrape_date) OVER (PARTITION BY listing_id)                                 AS first_seen_date,
        MAX(scrape_date) OVER (PARTITION BY listing_id)                                 AS last_seen_date,

        -- Cumulative observation count at point of scrape
        ROW_NUMBER() OVER (
            PARTITION BY listing_id
            ORDER BY scrape_date ASC, scraped_at ASC
        )                                                                               AS observation_sequence,
        COUNT(*) OVER (PARTITION BY listing_id)                                         AS observation_count,

        -- Initial price: First price observed for this listing
        FIRST_VALUE(price IGNORE NULLS) OVER (
            PARTITION BY listing_id
            ORDER BY scrape_date ASC, scraped_at ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        )                                                                               AS initial_price,

        -- Latest price across all observed snapshots
        FIRST_VALUE(price IGNORE NULLS) OVER (
            PARTITION BY listing_id
            ORDER BY scrape_date DESC, scraped_at DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        )                                                                               AS latest_price,

        -- Earliest known timestamp (posted_at if available, else first scraped_at)
        MIN(COALESCE(posted_at, scraped_at)) OVER (PARTITION BY listing_id)            AS _earliest_seen_at

    FROM staging
)

SELECT
    listing_id,
    scrape_date,
    scraped_at,
    posted_at,
    price,
    first_seen_date,
    last_seen_date,
    observation_sequence,
    observation_count,
    initial_price,
    latest_price,

    -- SCD Type 3: Previous historical price state (prior scrape event)
    LAG(price) OVER (
        PARTITION BY listing_id
        ORDER BY scrape_date ASC, scraped_at ASC
    )                                                                                   AS previous_price,
    LAG(scrape_date) OVER (
        PARTITION BY listing_id
        ORDER BY scrape_date ASC, scraped_at ASC
    )                                                                                   AS previous_scrape_date,

    -- Price drop metrics relative to initial listing price
    CASE
        WHEN price IS NULL OR initial_price IS NULL THEN 0.0
        ELSE GREATEST(initial_price - price, 0.0)
    END                                                                                 AS price_drop_amount,
    CASE WHEN (initial_price - price) > 0 THEN 1 ELSE 0 END                             AS has_price_drop,

    -- Days on market at this specific scrape observation
    ROUND(
        GREATEST(
            DATE_DIFF('second', _earliest_seen_at, scraped_at) / 86400.0,
            0.0
        ),
        1
    )                                                                                   AS days_on_market

FROM ordered_history
