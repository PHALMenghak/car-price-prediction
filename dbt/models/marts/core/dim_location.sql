-- dbt/models/marts/core/dim_location.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- GOLD LAYER (DIMENSION): Geographic Location Dimension Table
-- ─────────────────────────────────────────────────────────────────────────────

{{ config(
    materialized = 'table',
    post_hook    = [
        "COPY {{ this }} TO 'data/gold/dim_location.parquet' (FORMAT PARQUET)"
    ]
) }}

WITH distinct_locations AS (
    SELECT DISTINCT
        COALESCE(province, 'Phnom Penh') AS province,
        COALESCE(district, 'Unknown') AS district
    FROM {{ ref('int_cars_cleaned') }}
)

SELECT
    MD5(CONCAT(province, '||', district)) AS location_key,
    province,
    district,
    CASE
        WHEN province = 'Phnom Penh' THEN 'Tier_1'
        WHEN province IN ('Siem Reap', 'Battambang', 'Kandal', 'Preah Sihanouk', 'Kampong Cham') THEN 'Tier_2'
        ELSE 'Tier_3'
    END AS location_tier
FROM distinct_locations
