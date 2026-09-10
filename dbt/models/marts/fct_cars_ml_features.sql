-- dbt/models/marts/fct_cars_ml_features.sql
-- ML Feature Store: Day-0 appraisal features & log-stabilized price target for ML price prediction.
-- Leakage-Free Design: Excludes future market dynamics (days_on_market, price_drop_amount, initial_price).
-- Grain: 1 record per unique listing_id (latest snapshot).

{{ config(
    materialized = 'table',
    post_hook    = [
        "COPY {{ this }} TO 'data/gold/fct_cars_ml_features.parquet' (FORMAT PARQUET)",
        "COPY {{ this }} TO 'data/gold/fct_cars_ml_features.csv' (HEADER, DELIMITER ',')"
    ]
) }}

WITH latest_clean_cars AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY listing_id
            ORDER BY scraped_at DESC
        ) AS _active_rank
    FROM {{ ref('int_cars_cleaned') }}
    WHERE data_quality_status IN ('VALID', 'WARNING')
      AND price >= 500
      AND vehicle_year IS NOT NULL
      AND vehicle_brand IS NOT NULL
      AND vehicle_brand NOT IN ('ផ្សេងៗ', 'Other', 'Others')
      AND vehicle_model IS NOT NULL
      AND vehicle_model NOT IN ('ផ្សេងៗ', 'Other', 'Others')
)

SELECT
    listing_id,

    -- Target Variables
    price,
    LN(1.0 + price)                                                         AS log_price,

    -- Specifications & Age (Day-0 appraisal features)
    vehicle_brand,
    vehicle_model,
    vehicle_year                                                            AS vehicle_model_year,
    GREATEST(CAST(date_part('year', scrape_date) - vehicle_year AS INTEGER), 0) AS vehicle_age,

    -- Physical Specs & Explicit Missingness Indicators (no global train-test leakage imputation)
    vehicle_mileage_km,
    CASE WHEN vehicle_mileage_km IS NULL THEN 1 ELSE 0 END                  AS is_mileage_missing,

    vehicle_engine_cc,
    CASE WHEN vehicle_engine_cc IS NULL THEN 1 ELSE 0 END                   AS is_engine_cc_missing,

    -- Powertrain & Attributes
    vehicle_body_type,
    vehicle_fuel_type,
    vehicle_transmission,
    vehicle_color,
    vehicle_condition,
    CASE WHEN vehicle_tax_type = 'Plate Number' THEN 1 ELSE 0 END          AS is_plate_number,

    -- Market Segmentation
    brand_tier                                                              AS brand_category,
    province,
    CASE
        WHEN province = 'Phnom Penh' THEN 'Tier_1'
        WHEN province IN ('Siem Reap', 'Battambang', 'Kandal', 'Preah Sihanouk', 'Kampong Cham') THEN 'Tier_2'
        WHEN province IS NOT NULL THEN 'Tier_3'
        ELSE 'Unknown'
    END                                                                     AS location_tier,
    seller_type,

    -- Day-0 Listing NLP Signals
    has_full_option,
    is_urgent_sale,

    -- Metadata
    posted_at,
    scraped_at,
    scrape_date

FROM latest_clean_cars
WHERE _active_rank = 1
