-- dbt/models/marts/fct_cars_ml_features.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- GOLD LAYER: ML Feature Store — Imputation, Feature Engineering & Export
-- ─────────────────────────────────────────────────────────────────────────────
-- Reads from Silver layer (int_cars_cleaned) and produces the final ML matrix:
--   1. Hierarchical window-median imputation for year, mileage, engine_cc
--   2. Non-linear depreciation features: vehicle_age, vehicle_age², mileage/year
--   3. Cambodia automotive brand tier classification (via macro)
--   4. Geographic liquidity tiers (Phnom Penh Tier_1, urban Tier_2, rural Tier_3)
--   5. Multilingual NLP feature extraction from listing titles (via macro)
--   6. Log-transformed regression target: log_price = ln(1 + price)
-- Materialization: table (persisted in DuckDB for direct ML consumption)

WITH silver AS (
    SELECT * FROM {{ ref('int_cars_cleaned') }}
),

-- ── Step 1: Compute hierarchical median imputation via window functions ───────
imputed_medians AS (
    SELECT
        *,

        -- Missing indicator flags (capture before imputation)
        CASE WHEN vehicle_model_year IS NULL THEN 1 ELSE 0 END   AS is_year_missing,
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

        -- ── Engine CC imputation: Model median → 2000 cc ─────────────────
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
    listing_title,

    -- ── Regression Targets ────────────────────────────────────────────────
    price,
    LN(1.0 + price)                                          AS log_price,

    -- ── Core Vehicle Specs (imputed) ──────────────────────────────────────
    vehicle_brand,
    vehicle_model,
    CAST(imputed_year AS INTEGER)                            AS vehicle_model_year,
    is_year_missing,
    ROUND(imputed_mileage, 0)                                AS vehicle_mileage_km,
    is_mileage_missing,
    ROUND(imputed_engine_cc, 0)                              AS vehicle_engine_cc,
    is_engine_cc_missing,
    vehicle_condition,
    vehicle_tax_type,
    vehicle_fuel_type,
    vehicle_transmission,
    vehicle_color,

    -- ── Feature 1: Non-linear Depreciation & Mileage Intensity ───────────
    (date_part('year', CURRENT_DATE) - imputed_year)         AS vehicle_age,
    POWER(
        (date_part('year', CURRENT_DATE) - imputed_year), 2
    )                                                        AS vehicle_age_squared,
    ROUND(
        imputed_mileage / (date_part('year', CURRENT_DATE) - imputed_year + 1),
        1
    )                                                        AS mileage_per_year,

    -- ── Feature 2: Cambodia Brand Tier Classification (via macro) ─────────
    {{ classify_brand_tier('vehicle_brand') }}               AS brand_category,
    CASE WHEN vehicle_brand IN (
        'Lexus', 'Mercedes-Benz', 'BMW', 'Porsche', 'Land Rover',
        'Audi', 'Cadillac', 'Rolls-Royce', 'Bentley', 'Maserati',
        'Lamborghini', 'Ferrari', 'Aston Martin', 'Genesis', 'Volvo'
    ) THEN 1 ELSE 0 END                                      AS is_luxury_brand,
    CASE WHEN vehicle_brand IN (
        'Toyota', 'Ford', 'Hyundai', 'Mazda', 'Kia',
        'Honda', 'Mitsubishi', 'Nissan', 'Suzuki', 'Isuzu',
        'Subaru', 'Chevrolet', 'Volkswagen', 'Jeep'
    ) THEN 1 ELSE 0 END                                      AS is_popular_brand,
    CASE WHEN vehicle_brand IN (
        'BYD', 'MG', 'Geely', 'Haval', 'GAC', 'Jetour', 'Changan',
        'Denza', 'Xpeng', 'NIO', 'Zeekr', 'AVATR', 'Li Auto', 'Chery',
        'Tank', 'Omoda', 'Jaecoo'
    ) THEN 1 ELSE 0 END                                      AS is_chinese_ev_brand,

    -- ── Feature 3: Cambodia Geographic Liquidity Tiers ────────────────────
    province,
    CASE
        WHEN province = 'Phnom Penh'                                         THEN 'Tier_1'
        WHEN province IN (
            'Siem Reap', 'Battambang', 'Kandal',
            'Preah Sihanouk', 'Kampong Cham'
        )                                                                    THEN 'Tier_2'
        ELSE                                                                      'Tier_3'
    END                                                      AS location_tier,
    CASE WHEN province = 'Phnom Penh' THEN 1 ELSE 0 END     AS is_tier_1_loc,

    -- ── Feature 4: Marketplace & Seller Dynamics ──────────────────────────
    seller_type,
    view_count,
    ROUND(days_on_market, 1)                                 AS days_on_market,
    initial_price,
    price_drop_amount,
    has_price_drop,
    view_velocity,

    -- ── Feature 5: Multilingual NLP Title Signals (via macro) ────────────
    {{ extract_title_options('listing_title') }},

    -- ── Metadata ──────────────────────────────────────────────────────────
    scraped_at

FROM imputed_medians
