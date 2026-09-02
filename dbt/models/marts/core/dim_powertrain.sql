-- dbt/models/marts/core/dim_powertrain.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- GOLD LAYER (DIMENSION): Powertrain & Engine Dimension Table
-- ─────────────────────────────────────────────────────────────────────────────

{{ config(
    materialized = 'table',
    post_hook    = [
        "COPY {{ this }} TO 'data/gold/dim_powertrain.parquet' (FORMAT PARQUET)"
    ]
) }}

WITH distinct_powertrains AS (
    SELECT DISTINCT
        COALESCE(vehicle_fuel_type, 'Unknown') AS fuel_type,
        COALESCE(vehicle_transmission, 'Automatic') AS transmission,
        vehicle_engine_cc
    FROM {{ ref('int_cars_cleaned') }}
)

SELECT
    MD5(CONCAT(fuel_type, '||', transmission, '||', CAST(COALESCE(vehicle_engine_cc, 0) AS VARCHAR))) AS powertrain_key,
    fuel_type,
    transmission,
    vehicle_engine_cc,
    CASE
        WHEN vehicle_engine_cc IS NULL THEN 'Unknown'
        WHEN vehicle_engine_cc < 1500 THEN '< 1.5L'
        WHEN vehicle_engine_cc BETWEEN 1500 AND 2000 THEN '1.5L - 2.0L'
        WHEN vehicle_engine_cc BETWEEN 2001 AND 3000 THEN '2.1L - 3.0L'
        WHEN vehicle_engine_cc BETWEEN 3001 AND 4500 THEN '3.1L - 4.5L'
        ELSE '> 4.5L'
    END AS engine_bracket
FROM distinct_powertrains
