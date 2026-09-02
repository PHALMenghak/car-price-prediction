-- dbt/models/marts/core/dim_car_model.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- GOLD LAYER (DIMENSION): Car Brand & Model Dimension Table
-- ─────────────────────────────────────────────────────────────────────────────

{{ config(
    materialized = 'table',
    post_hook    = [
        "COPY {{ this }} TO 'data/gold/dim_car_model.parquet' (FORMAT PARQUET)"
    ]
) }}

WITH distinct_models AS (
    SELECT DISTINCT
        COALESCE(CAST(vehicle_brand AS VARCHAR), 'Unknown') AS vehicle_brand,
        COALESCE(CAST(vehicle_model AS VARCHAR), 'Unknown') AS vehicle_model,
        COALESCE(CAST(vehicle_body_type AS VARCHAR), 'Unknown') AS body_type
    FROM {{ ref('int_cars_cleaned') }}
)

SELECT
    MD5(CONCAT(vehicle_brand, '||', vehicle_model, '||', body_type)) AS model_key,
    vehicle_brand,
    vehicle_model,
    {{ classify_brand_tier('vehicle_brand') }} AS brand_tier,
    body_type
FROM distinct_models
