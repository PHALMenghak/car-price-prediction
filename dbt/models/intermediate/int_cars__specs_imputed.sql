-- dbt/models/intermediate/int_cars__specs_imputed.sql
-- Intermediate Layer: Statistical peer consensus mode imputation & physical specs extraction.
-- Heals missing body_type, fuel_type, and transmission, then extracts mileage and engine CC.
-- Grain: 1 listing_id x 1 scrape_date.

{{ config(materialized = 'view') }}

WITH year_resolved AS (
    SELECT * FROM {{ ref('int_cars__year_healed') }}
),

-- Step 1: Empirical Peer & Model Consensus Imputation
-- Grouped by (vehicle_brand, vehicle_model, vehicle_year) and (vehicle_brand, vehicle_model).
peer_consensus AS (
    SELECT
        vehicle_brand,
        vehicle_model,
        vehicle_year,
        MODE(mapped_body_type)     AS mode_body_bmy,
        MODE(vehicle_fuel_type)    AS mode_fuel_bmy,
        MODE(vehicle_transmission) AS mode_trans_bmy
    FROM year_resolved
    WHERE vehicle_brand IS NOT NULL 
      AND vehicle_model IS NOT NULL 
      AND vehicle_year IS NOT NULL
    GROUP BY 1, 2, 3
),

model_consensus AS (
    SELECT
        vehicle_brand,
        vehicle_model,
        MODE(mapped_body_type)     AS mode_body_bm,
        MODE(vehicle_fuel_type)    AS mode_fuel_bm,
        MODE(vehicle_transmission) AS mode_trans_bm
    FROM year_resolved
    WHERE vehicle_brand IS NOT NULL 
      AND vehicle_model IS NOT NULL
    GROUP BY 1, 2
),

specs_healed AS (
    SELECT
        yr.* EXCLUDE (vehicle_fuel_type, vehicle_transmission),

        -- Pure Data-Driven Body Type (Seed mapped -> Peer mode -> Model mode)
        COALESCE(
            yr.mapped_body_type,
            p.mode_body_bmy,
            m.mode_body_bm
        ) AS vehicle_body_type,

        -- Pure Data-Driven Fuel Type (Seed mapped -> Peer mode -> Model mode)
        COALESCE(
            yr.vehicle_fuel_type,
            p.mode_fuel_bmy,
            m.mode_fuel_bm
        ) AS vehicle_fuel_type,

        -- Data-Driven Transmission (Seed mapped -> Peer mode -> Model mode -> 'Automatic')
        COALESCE(
            yr.vehicle_transmission,
            p.mode_trans_bmy,
            m.mode_trans_bm,
            'Automatic'
        ) AS vehicle_transmission

    FROM year_resolved yr
    LEFT JOIN peer_consensus p
      ON yr.vehicle_brand = p.vehicle_brand
     AND yr.vehicle_model = p.vehicle_model
     AND yr.vehicle_year = p.vehicle_year
    LEFT JOIN model_consensus m
      ON yr.vehicle_brand = m.vehicle_brand
     AND yr.vehicle_model = m.vehicle_model
),

-- Step 2: Physical Specs Extraction (Using precomputed text, healed year, and healed fuel type)
specs_extracted AS (
    SELECT
        sh.*,
        -- EV Detection Flag: Evaluated ONCE per row
        CASE
            WHEN {{ is_ev_vehicle('sh.vehicle_brand', 'sh.vehicle_fuel_type') }} THEN 1
            ELSE 0
        END AS is_electric,
        {{ parse_mileage('sh.raw_spec_mileage', 'sh._precleaned_text', 'sh.vehicle_year', 'sh.vehicle_fuel_type') }} AS _extracted_mileage_km,
        {{ parse_engine_cc('sh.raw_spec_engine_size', 'sh._precleaned_text', 'sh.vehicle_fuel_type', 'sh.vehicle_brand') }} AS _extracted_engine_cc
    FROM specs_healed sh
),

specs_parsed AS (
    SELECT
        se.*,

        -- Multi-source mileage extraction clamped between 0 and 500,000 km
        CASE
            WHEN se._extracted_mileage_km BETWEEN 0 AND 500000
                THEN se._extracted_mileage_km
            ELSE NULL
        END AS vehicle_mileage_km,

        -- Multi-source engine CC clamped between 500 and 7,000 cc; NULL for pure EV (reusing is_electric)
        CASE
            WHEN se.is_electric = 1 THEN NULL
            WHEN se._extracted_engine_cc BETWEEN 500 AND 7000 THEN se._extracted_engine_cc
            ELSE NULL
        END AS vehicle_engine_cc

    FROM specs_extracted se
)

SELECT * FROM specs_parsed
