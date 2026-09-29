-- dbt/models/intermediate/int_cars_cleaned.sql
-- Silver Conformed Model: Integrates conformed specs, longitudinal metrics, and assigns 5-tier quality classification.
-- Consumes modular upstream stages (int_cars__outliers_flagged) and longitudinal tracking (int_listing_history).
-- Grain: 1 listing_id x 1 scrape_date.

{{ config(
    materialized = 'table',
    post_hook    = [
        "COPY {{ this }} TO 'data/silver/cars_cleaned.parquet' (FORMAT PARQUET)",
        "COPY {{ this }} TO 'data/silver/cars_cleaned.csv' (HEADER, DELIMITER ',')"
    ]
) }}

WITH evaluated AS (
    SELECT * FROM {{ ref('int_cars__outliers_flagged') }}
),

history AS (
    SELECT * FROM {{ ref('int_listing_history') }}
)

SELECT
    e.listing_id,
    e.scrape_date,
    e.scraped_at,
    e.posted_at,
    e.listing_url,
    e.thumbnail_url,

    -- Cleaned & Conformed Text Entities
    e.title_clean,

    -- Price (Canonical asking price in USD)
    e.price,

    -- Longitudinal Dynamics & SCD Type 3 (from int_listing_history)
    h.initial_price,
    h.previous_price,
    h.previous_scrape_date,
    h.price_drop_amount,
    h.has_price_drop,
    h.days_on_market,
    h.first_seen_date,
    h.last_seen_date,
    h.observation_sequence,
    h.observation_count,

    -- Vehicle Brand & Model
    e.vehicle_brand,
    e.brand_tier,
    e.vehicle_model,
    e.model_extraction_method,

    -- Vehicle Year & Age
    e.vehicle_year,
    e.vehicle_age,
    e.is_year_healed,

    -- Physical Specs: Body, Mileage, Engine
    e.vehicle_body_type,
    e.vehicle_mileage_km,
    e.vehicle_engine_cc,
    e.is_electric,

    -- Powertrain & Attributes
    e.vehicle_fuel_type,
    e.vehicle_transmission,
    e.vehicle_color,
    e.vehicle_condition,
    e.vehicle_tax_type,

    -- Location & Seller
    e.province,
    e.location_tier,
    e.raw_district                                                          AS district,
    e.seller_id,
    e.seller_name,
    e.seller_type,
    e.seller_username,
    e.seller_phones,

    -- NLP Listing Signals
    e.has_full_option,

    -- Anomaly & Outlier Detection
    e.is_spam,
    e.is_down_payment,
    e.is_price_outlier,
    e.outlier_method,
    e.price_lower_fence,
    e.price_upper_fence,

    -- Canonical 5-Tier Data Quality Status
    CASE
        WHEN e.is_spam = 1 OR e.listing_id IS NULL OR e.price <= 0
            THEN 'QUARANTINED'
        WHEN e.price IS NULL
          OR e.price < 500
          OR e.vehicle_year IS NULL
          OR e.vehicle_year < 1990
          OR e.vehicle_year > (CAST(date_part('year', CURRENT_DATE) AS INTEGER) + 1)
          OR e.vehicle_brand IS NULL
          OR e.vehicle_model IS NULL
            THEN 'INVALID'
        WHEN e.is_down_payment = 1 OR e.is_price_outlier = 1
            THEN 'SUSPICIOUS'
        WHEN e.is_year_healed = 1
          OR e.year_source IN ('title_regex', 'title_2digit')
          OR e.model_extraction_method = 'title_regex'
          OR e.province IS NULL
            THEN 'WARNING'
        ELSE 'VALID'
    END                                                                     AS data_quality_status,

    -- Diagnostic Audit Reason Codes
    CONCAT_WS('|',
        CASE WHEN e.is_spam = 1 THEN 'NON_VEHICLE_SPAM' END,
        CASE WHEN e.price IS NULL THEN 'MISSING_PRICE' END,
        CASE WHEN e.price <= 0 THEN 'INVALID_PRICE' END,
        CASE WHEN e.price < 500 THEN 'PRICE_BELOW_MINIMUM' END,
        CASE WHEN e.vehicle_year IS NULL THEN 'MISSING_YEAR' END,
        CASE WHEN e.vehicle_year < 1990 OR e.vehicle_year > (CAST(date_part('year', CURRENT_DATE) AS INTEGER) + 1) THEN 'INVALID_YEAR' END,
        CASE WHEN e.vehicle_brand IS NULL THEN 'UNKNOWN_BRAND' END,
        CASE WHEN e.vehicle_model IS NULL THEN 'UNKNOWN_MODEL' END,
        CASE WHEN e.is_down_payment = 1 THEN 'DOWN_PAYMENT_PRICE' END,
        CASE WHEN e.is_price_outlier = 1 THEN 'SUSPICIOUS_PRICE_OUTLIER' END,
        CASE WHEN e.outlier_method = 'SEGMENT_IQR' AND e._is_stat_low = 1 THEN 'STATISTICAL_OUTLIER_LOW' END,
        CASE WHEN e.outlier_method = 'SEGMENT_IQR' AND e._is_stat_high = 1 THEN 'STATISTICAL_OUTLIER_HIGH' END,
        CASE WHEN e.outlier_method = 'HEURISTIC_FALLBACK' AND e.is_price_outlier = 1 THEN 'HEURISTIC_PRICE_OUTLIER' END,
        CASE WHEN e.is_year_healed = 1 THEN 'YEAR_INVERSION_HEALED' END,
        CASE WHEN e.year_source = 'title_regex' THEN 'YEAR_FROM_TITLE' END,
        CASE WHEN e.model_extraction_method = 'title_regex' THEN 'MODEL_FROM_TITLE' END,
        CASE WHEN e.province IS NULL THEN 'MISSING_LOCATION' END,
        CASE WHEN e.vehicle_mileage_km IS NULL THEN 'MISSING_MILEAGE' END,
        CASE WHEN e.vehicle_engine_cc IS NULL AND e.is_electric = 0 THEN 'MISSING_ENGINE_CC' END,
        CASE WHEN e.vehicle_fuel_type IS NULL THEN 'MISSING_FUEL_TYPE' END,
        CASE WHEN e.vehicle_transmission IS NULL THEN 'MISSING_TRANSMISSION' END
    )                                                                       AS data_quality_reasons

FROM evaluated e
LEFT JOIN history h
  ON e.listing_id = h.listing_id
 AND e.scrape_date = h.scrape_date
