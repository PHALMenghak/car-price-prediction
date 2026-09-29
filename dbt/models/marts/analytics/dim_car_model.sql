-- dbt/models/marts/analytics/dim_car_model.sql
-- Vehicle Model Dimension: Normalized vehicle identity and market classification.
-- Grain: 1 record per unique Brand x Model x Body Type (unique model_key).

{{ config(
    materialized = 'table',
    post_hook    = [
        "COPY {{ this }} TO 'data/gold/dim_car_model.parquet' (FORMAT PARQUET)"
    ]
) }}

WITH raw_models AS (
    SELECT
        MD5(
            LOWER(TRIM(vehicle_brand)) || '||' ||
            LOWER(TRIM(vehicle_model)) || '||' ||
            LOWER(TRIM(COALESCE(vehicle_body_type, 'unspecified')))
        ) AS model_key,
        -- Canonical casing (prefer capitalized/most frequent representation)
        TRIM(vehicle_brand) AS vehicle_brand,
        TRIM(vehicle_model) AS vehicle_model,
        brand_tier,
        vehicle_body_type   AS body_type,
        ROW_NUMBER() OVER (
            PARTITION BY MD5(
                LOWER(TRIM(vehicle_brand)) || '||' ||
                LOWER(TRIM(vehicle_model)) || '||' ||
                LOWER(TRIM(COALESCE(vehicle_body_type, 'unspecified')))
            )
            ORDER BY scraped_at DESC
        ) AS _recency_rank
    FROM {{ ref('int_cars_cleaned') }}
    WHERE data_quality_status IN ('VALID', 'WARNING')
      AND vehicle_brand IS NOT NULL
      AND vehicle_model IS NOT NULL
)

SELECT
    model_key,
    vehicle_brand,
    vehicle_model,
    brand_tier,
    body_type
FROM raw_models
WHERE _recency_rank = 1
