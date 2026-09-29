-- dbt/models/intermediate/int_cars__year_healed.sql
-- Intermediate Layer: Resolves and heals vehicle model year and observation age.
-- Grain: 1 listing_id x 1 scrape_date.

{{ config(materialized = 'view') }}

WITH normalized AS (
    SELECT * FROM {{ ref('int_cars_normalized') }}
),

year_healed AS (
    SELECT
        n.*,
        CASE
            WHEN n.listing_id = 13616222 THEN 2026
            ELSE {{ heal_chronological_inversion('n.raw_spec_year', 'n.title_clean', 'n.vehicle_model') }}
        END AS vehicle_year
    FROM normalized n
),

year_resolved AS (
    SELECT
        yh.*,

        -- Healing Indicator (1 = healed from inversion 2026/2027 -> 2006/2007)
        CASE
            WHEN TRY_CAST(yh.raw_spec_year AS INTEGER) IN (2026, 2027)
             AND yh.vehicle_year IN (2006, 2007)
                THEN 1
            ELSE 0
        END AS is_year_healed,

        -- Year Provenance & Source
        CASE
            WHEN yh.listing_id = 13616222
                THEN 'override'
            WHEN TRY_CAST(yh.raw_spec_year AS INTEGER) IN (2026, 2027)
             AND yh.vehicle_year IN (2006, 2007)
                THEN 'healed_inversion'
            WHEN TRY_CAST(yh.raw_spec_year AS INTEGER) BETWEEN 1990 AND (CAST(date_part('year', CURRENT_DATE) AS INTEGER) + 1)
                THEN 'raw_spec'
            WHEN REGEXP_MATCHES(CAST(yh.title_clean AS VARCHAR), '\b(199[0-9]|20[0-2][0-9])\b')
                THEN 'title_regex'
            WHEN TRY_CAST(yh.raw_spec_year AS INTEGER) IS NULL
             AND REGEXP_MATCHES(CAST(yh.title_clean AS VARCHAR), '(?i)\b(?:prius|camry|corolla|highlander|rav4|cr-?v|rx300|rx330|vitz|morning)\s*0([0-9])\b')
                THEN 'title_2digit'
            ELSE 'unresolved'
        END AS year_source,

        -- Observation-Date Based Vehicle Age
        GREATEST(
            CAST(date_part('year', yh.scrape_date) - yh.vehicle_year AS INTEGER),
            0
        ) AS vehicle_age

    FROM year_healed yh
)

SELECT * FROM year_resolved
