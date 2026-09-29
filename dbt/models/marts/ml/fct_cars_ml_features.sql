-- dbt/models/marts/ml/fct_cars_ml_features.sql
-- Canonical ML Feature Store: Day-0 appraisal features, log-stabilized price target, and temporal split metadata.
-- Leakage-Free Design:
--   1. Excludes future market dynamics (days_on_market, price_drop_amount, initial_price).
--   2. Strict deduplication to 1 record per unique listing_id prevents cross-split data leakage.
--   3. Chronological split assignment (train / validation / test) by observation date.
-- Feature Reduction:
--   - vehicle_year is DROPPED to eliminate exact mathematical collinearity with vehicle_age (r = -1.000).
-- Grain: 1 record per unique listing_id (enriched with canonical vehicle deduplication flag).

{{ config(
    materialized = 'table',
    post_hook    = [
        "COPY {{ this }} TO 'data/gold/fct_cars_ml_features.parquet' (FORMAT PARQUET)",
        "COPY {{ this }} TO 'data/gold/fct_cars_ml_features.csv' (HEADER, DELIMITER ',')"
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
      AND price >= 500
      AND is_price_outlier = 0
      AND is_down_payment = 0
      AND is_spam = 0
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
    -- =========================================================================
    -- 1. IDENTIFIERS & METADATA (Never fed into ML estimators as features)
    -- =========================================================================
    listing_id,
    scrape_date,
    posted_at,

    -- Chronological train/validation/test split for temporal cross-validation (70% train / 15% val / 15% test)
    CASE
        WHEN PERCENT_RANK() OVER (ORDER BY scrape_date ASC, posted_at ASC, listing_id ASC) <= 0.70 THEN 'train'
        WHEN PERCENT_RANK() OVER (ORDER BY scrape_date ASC, posted_at ASC, listing_id ASC) <= 0.85 THEN 'validation'
        ELSE 'test'
    END AS split_group,

    -- =========================================================================
    -- 2. TARGET VARIABLES (Explicit regression targets; excluded from X matrix)
    -- =========================================================================
    price,
    LN(price)                                                               AS log_price,

    -- =========================================================================
    -- 3. SPECIFICATIONS & AGE (vehicle_year dropped to eliminate exact collinearity)
    -- =========================================================================
    vehicle_brand,
    vehicle_model,
    vehicle_age,

    -- =========================================================================
    -- 4. POWERTRAIN & BODY ATTRIBUTES
    -- =========================================================================
    vehicle_body_type,
    vehicle_fuel_type,
    vehicle_transmission,
    vehicle_color,
    vehicle_condition,
    CASE
        WHEN vehicle_tax_type = 'Plate Number' THEN 1
        WHEN vehicle_tax_type = 'Tax Paper' THEN 0
        ELSE NULL
    END                                                                     AS is_plate_number,

    -- =========================================================================
    -- 5. MARKET SEGMENTATION
    -- =========================================================================
    brand_tier                                                              AS brand_category,

    -- =========================================================================
    -- 6. DAY-0 LISTING NLP SIGNALS
    -- =========================================================================
    has_full_option,

    -- =========================================================================
    -- 7. DEDUPLICATION METADATA (100% Unique Canonical Vehicles)
    -- =========================================================================
    repost_count,
    1                                                                       AS is_canonical_vehicle

FROM vehicle_clusters
WHERE _vehicle_rank = 1
