-- dbt/models/marts/analytics/dim_location.sql
-- Geographic Dimension: Cambodian administrative divisions and regional liquidity tiers.
-- Grain: 1 record per unique Province x District.

{{ config(
    materialized = 'table',
    post_hook    = [
        "COPY {{ this }} TO 'data/gold/dim_location.parquet' (FORMAT PARQUET)"
    ]
) }}

WITH distinct_locations AS (
    SELECT DISTINCT
        province,
        district,
        location_tier
    FROM {{ ref('int_cars_cleaned') }}
    WHERE data_quality_status IN ('VALID', 'WARNING')
      AND province IS NOT NULL
)

SELECT
    MD5(
        LOWER(TRIM(province)) || '||' ||
        LOWER(TRIM(COALESCE(district, 'unspecified')))
    ) AS location_key,
    province,
    district,
    location_tier

FROM distinct_locations
