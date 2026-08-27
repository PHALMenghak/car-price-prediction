-- dbt/models/marts/fct_cars_ml_features.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- GOLD LAYER: ML Feature Store — Imputation, Feature Engineering & Export
-- ─────────────────────────────────────────────────────────────────────────────
-- Reads from Silver layer (int_cars_cleaned) and produces the final ML matrix.
-- After materializing into DuckDB, the post_hook exports a Parquet file to
-- data/processed/fct_cars_ml_features.parquet for direct ML consumption.
-- Materialization: table (persisted in DuckDB at data/processed/khmer24.duckdb)

{{ config(
    materialized = 'table',
    post_hook    = [
        "COPY {{ this }} TO 'data/processed/fct_cars_ml_features.parquet' (FORMAT PARQUET)",
        "COPY {{ this }} TO 'data/processed/fct_cars_ml_features.csv' (HEADER, DELIMITER ',')"
    ]
) }}

WITH silver AS (
    SELECT * FROM {{ ref('int_cars_cleaned') }}
),

-- ── Step 1: Compute hierarchical median imputation via window functions ───────
imputed_medians AS (
    SELECT
        *,

        -- Missing indicator flags (capture before imputation)
        CASE WHEN vehicle_mileage_km IS NULL THEN 1 ELSE 0 END   AS is_mileage_missing,
        CASE WHEN vehicle_engine_cc IS NULL THEN 1 ELSE 0 END    AS is_engine_cc_missing,

        -- ── Year imputation: Brand+Model median → Brand median → 2012 ────
        COALESCE(
            vehicle_model_year,
            MEDIAN(vehicle_model_year) OVER (PARTITION BY vehicle_brand, vehicle_model),
            MEDIAN(vehicle_model_year) OVER (PARTITION BY vehicle_brand),
            2012
        ) AS imputed_year,

        -- ── Mileage imputation: Year+Brand median → Global median → 100k ─
        COALESCE(
            vehicle_mileage_km,
            MEDIAN(vehicle_mileage_km) OVER (PARTITION BY vehicle_model_year, vehicle_brand),
            MEDIAN(vehicle_mileage_km) OVER (),
            100000.0
        ) AS imputed_mileage,

        -- ── Engine CC imputation: Model median → Brand median → 2000 cc ──
        COALESCE(
            vehicle_engine_cc,
            MEDIAN(vehicle_engine_cc) OVER (PARTITION BY vehicle_model),
            MEDIAN(vehicle_engine_cc) OVER (PARTITION BY vehicle_brand),
            2000.0
        ) AS imputed_engine_cc

    FROM silver
)

SELECT
    -- ── Identifiers ───────────────────────────────────────────────────────
    listing_id,

    -- ── Regression Targets (Primary Log Target & Raw Dollar Target) ────────
    price,
    LN(1.0 + price)                                          AS log_price,

    -- ── Core Vehicle Specs & Imputation Flags ──────────────────────────────
    vehicle_brand,
    vehicle_model,
    CAST(imputed_year AS INTEGER)                            AS vehicle_model_year,
    GREATEST(CAST(date_part('year', CURRENT_DATE) - imputed_year AS INTEGER), 0) AS vehicle_age,
    ROUND(imputed_mileage, 0)                                AS vehicle_mileage_km,
    is_mileage_missing,
    ROUND(imputed_engine_cc, 0)                              AS vehicle_engine_cc,
    is_engine_cc_missing,

    -- ── Powertrain & Physical Appearance ──────────────────────────────────
    {{ infer_fuel_type('vehicle_brand', 'vehicle_model', 'listing_title', 'vehicle_fuel_type') }} AS vehicle_fuel_type,
    {{ infer_transmission('listing_title', 'vehicle_transmission') }} AS vehicle_transmission,
    COALESCE(
        NULLIF(vehicle_color, 'Unknown'),
        NULLIF({{ extract_color_from_title('listing_title') }}, 'Unknown'),
        'Unknown'
    )                                                        AS vehicle_color,

    -- ── Vehicle Condition & Legal Registration Status ─────────────────────
    vehicle_condition,
    CASE WHEN vehicle_tax_type = 'Plate Number' THEN 1 ELSE 0 END AS is_plate_number,

    -- ── Market Segmentation & Geographic Liquidity Tiers ──────────────────
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

    -- ── Marketplace Dynamics & NLP Signals ─────────────────────────────────
    initial_price,
    price_drop_amount,
    has_price_drop,
    price_increase_amount,
    has_price_increase,
    ROUND(days_on_market, 1)                                 AS days_on_market,
    ROUND(view_velocity, 2)                                  AS view_velocity,
    {{ extract_title_options('listing_title') }},

    -- ── Metadata / Ingestion Index ─────────────────────────────────────────
    scraped_at

FROM imputed_medians

