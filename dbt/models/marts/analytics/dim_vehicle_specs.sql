-- dbt/models/marts/analytics/dim_vehicle_specs.sql
-- Vehicle Specifications Dimension: Standardized powertrain, transmission, tax, and color attributes.
-- Grain: 1 record per unique Fuel x Transmission x Tax Type x Color.

{{ config(
    materialized = 'table',
    post_hook    = [
        "COPY {{ this }} TO 'data/gold/dim_vehicle_specs.parquet' (FORMAT PARQUET)"
    ]
) }}

WITH distinct_specs AS (
    SELECT DISTINCT
        vehicle_fuel_type,
        vehicle_transmission,
        vehicle_tax_type,
        vehicle_color
    FROM {{ ref('int_cars_cleaned') }}
    WHERE data_quality_status IN ('VALID', 'WARNING')
)

SELECT
    MD5(
        LOWER(TRIM(COALESCE(vehicle_fuel_type, 'unspecified'))) || '||' ||
        LOWER(TRIM(COALESCE(vehicle_transmission, 'unspecified'))) || '||' ||
        LOWER(TRIM(COALESCE(vehicle_tax_type, 'unspecified'))) || '||' ||
        LOWER(TRIM(COALESCE(vehicle_color, 'unspecified')))
    ) AS spec_key,
    vehicle_fuel_type,
    vehicle_transmission,
    vehicle_tax_type,
    vehicle_color

FROM distinct_specs
