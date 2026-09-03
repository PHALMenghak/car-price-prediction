-- dbt/models/marts/ml/fct_cars_ml_features.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- GOLD LAYER (ML FEATURE STORE): Feature Engineering & Imputation Matrix
-- ─────────────────────────────────────────────────────────────────────────────
-- Generates the final ML training matrix with hierarchical median imputations,
-- log-transformed target variables, NLP title options, and categorical encoding tiers.
-- Materialization: table with post-hook export to data/gold/

{{ config(
    materialized = 'table',
    post_hook    = [
        "COPY {{ this }} TO 'data/gold/fct_cars_ml_features.parquet' (FORMAT PARQUET)",
        "COPY {{ this }} TO 'data/gold/fct_cars_ml_features.csv' (HEADER, DELIMITER ',')"
    ]
) }}

WITH silver AS (
    SELECT * FROM {{ ref('int_cars_cleaned') }}
),

-- ── Step 1: Hierarchical median imputation via window functions ───────────────
imputed_medians AS (
    SELECT
        *,

        -- Missing indicator flags (capture before imputation)
        CASE WHEN vehicle_mileage_km IS NULL THEN 1 ELSE 0 END   AS is_mileage_missing,
        CASE WHEN vehicle_engine_cc IS NULL THEN 1 ELSE 0 END    AS is_engine_cc_missing,

        -- Year imputation: Brand+Model median -> Brand median -> 2012
        COALESCE(
            vehicle_model_year,
            MEDIAN(vehicle_model_year) OVER (PARTITION BY vehicle_brand, vehicle_model),
            MEDIAN(vehicle_model_year) OVER (PARTITION BY vehicle_brand),
            2012
        ) AS imputed_year,

        -- Mileage imputation: Year+Brand median -> Global median -> 100k
        COALESCE(
            vehicle_mileage_km,
            MEDIAN(vehicle_mileage_km) OVER (PARTITION BY vehicle_model_year, vehicle_brand),
            MEDIAN(vehicle_mileage_km) OVER (),
            100000.0
        ) AS imputed_mileage,

        -- Engine CC imputation: Model median -> Brand median -> 2000 cc
        COALESCE(
            vehicle_engine_cc,
            MEDIAN(vehicle_engine_cc) OVER (PARTITION BY vehicle_model),
            MEDIAN(vehicle_engine_cc) OVER (PARTITION BY vehicle_brand),
            2000.0
        ) AS imputed_engine_cc

    FROM silver
)

SELECT
    -- ── Identifiers ──────────────────────────────────────────────────────────
    listing_id,

    -- ── Regression Targets (Primary Log Target & Raw Dollar Target) ───────────
    price,
    LN(1.0 + price)                                          AS log_price,

    -- ── Core Vehicle Specs & Imputation Flags ─────────────────────────────────
    vehicle_brand,
    vehicle_model,
    CAST(imputed_year AS INTEGER)                            AS vehicle_model_year,
    GREATEST(CAST(date_part('year', CURRENT_DATE) - imputed_year AS INTEGER), 0) AS vehicle_age,
    ROUND(imputed_mileage, 0)                                AS vehicle_mileage_km,
    is_mileage_missing,
    ROUND(imputed_engine_cc, 0)                              AS vehicle_engine_cc,
    is_engine_cc_missing,

    -- ── Powertrain & Physical Appearance ─────────────────────────────────────
    vehicle_fuel_type,
    vehicle_transmission,
    COALESCE(NULLIF(vehicle_color, 'Unknown'), 'White')      AS vehicle_color,

    -- ── Vehicle Condition & Legal Registration Status ────────────────────────
    vehicle_condition,
    CASE WHEN vehicle_tax_type = 'Plate Number' THEN 1 ELSE 0 END AS is_plate_number,

    -- ── Market Segmentation & Geographic Liquidity Tiers ─────────────────────
    {{ classify_brand_tier('vehicle_brand') }}               AS brand_category,
    province,
    CASE
        WHEN province = 'Phnom Penh'                                         THEN 'Tier_1'
        WHEN province IN (
            'Siem Reap', 'Battambang', 'Kandal',
            'Preah Sihanouk', 'Kampong Cham'
        )                                                                    THEN 'Tier_2'
        ELSE                                                                      'Tier_3'
    END                                                      AS location_tier,
    seller_type,

    -- ── Market Dynamics & Longitudinal Signals ───────────────────────────────
    days_on_market,
    initial_price,
    price_drop_amount,
    has_price_drop,
    price_increase_amount,
    has_price_increase,

    -- ── NLP Option Signals (from Listing Title) ───────────────────────────────
    {{ extract_title_options('listing_title') }},

    -- ── Metadata ─────────────────────────────────────────────────────────────
    posted_at,
    scraped_at

FROM imputed_medians
