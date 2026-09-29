-- dbt/models/intermediate/int_cars_normalized.sql
-- Silver Normalization View: Single-pass text sanitization & controlled vocabulary mapping.
-- Resolves vehicle brand, canonical model, location, and powertrain from seed reference tables.
-- Grain: 1 listing_id x 1 scrape_date.

{{ config(materialized = 'view') }}

WITH staging AS (
    SELECT * FROM {{ ref('stg_khmer24_cars') }}
),

-- Reference Seed Controlled Vocabularies
brand_seeds AS (
    SELECT DISTINCT LOWER(TRIM(raw_value)) AS raw_value, standardized_brand
    FROM {{ ref('seed_brand_mapping') }}
),

model_seeds AS (
    SELECT DISTINCT brand, LOWER(TRIM(raw_alias)) AS raw_alias, standardized_model
    FROM {{ ref('seed_model_alias') }}
),

location_seeds AS (
    SELECT DISTINCT LOWER(TRIM(raw_value)) AS raw_value, standardized_province, location_tier
    FROM {{ ref('seed_location_mapping') }}
),

brand_tier_lookup AS (
    SELECT DISTINCT standardized_brand, brand_tier
    FROM {{ ref('seed_brand_mapping') }}
),

fuel_seeds AS (
    SELECT DISTINCT LOWER(TRIM(raw_value)) AS raw_value, standardized_fuel
    FROM {{ ref('seed_fuel_mapping') }}
),

transmission_seeds AS (
    SELECT DISTINCT LOWER(TRIM(raw_value)) AS raw_value, standardized_transmission
    FROM {{ ref('seed_transmission_mapping') }}
),

tax_seeds AS (
    SELECT DISTINCT LOWER(TRIM(raw_value)) AS raw_value, standardized_tax
    FROM {{ ref('seed_tax_mapping') }}
),

color_seeds AS (
    SELECT DISTINCT LOWER(TRIM(raw_value)) AS raw_value, standardized_color
    FROM {{ ref('seed_color_mapping') }}
),

condition_seeds AS (
    SELECT DISTINCT LOWER(TRIM(raw_value)) AS raw_value, standardized_condition
    FROM {{ ref('seed_condition_mapping') }}
),

body_seeds AS (
    SELECT DISTINCT LOWER(TRIM(raw_value)) AS raw_value, standardized_body_type
    FROM {{ ref('seed_body_type_mapping') }}
),

-- Step 1a: Apply clean_text() ONCE per column — evaluated exactly once per row
text_cleaned AS (
    SELECT
        s.*,
        {{ clean_text('s.raw_title') }}       AS title_clean,
        {{ clean_text('s.raw_description') }} AS description_clean
    FROM staging s
),

-- Step 1b: Build the concatenated search text from already-computed aliases (no re-evaluation)
text_prepped AS (
    SELECT
        *,
        LOWER(
            COALESCE(title_clean, '') || ' ' || COALESCE(description_clean, '')
        ) AS _precleaned_text
    FROM text_cleaned
),

-- Step 2: Vocabulary Normalization (Brand, Province, Powertrain)
standardized AS (
    SELECT
        t.*,

        -- Standardized Brand (Seed join with modular title fallback for 'ផ្សេងៗ' / unmapped)
        COALESCE(
            b.standardized_brand,
            {{ extract_brand_from_title('t.title_clean') }},
            CASE
                WHEN TRIM(t.raw_spec_brand) IN ('ផ្សេងៗ', 'Other', 'Others', '0', 'Plate Number', '2Year+', '212') THEN NULL
                ELSE NULLIF(TRIM(t.raw_spec_brand), '')
            END
        )                                                                   AS vehicle_brand,

        CASE
            WHEN b.standardized_brand IS NOT NULL THEN 'seed_canonical'
            WHEN {{ extract_brand_from_title('t.title_clean') }} IS NOT NULL THEN 'title_regex'
            WHEN NULLIF(TRIM(t.raw_spec_brand), '') IS NOT NULL
              AND TRIM(t.raw_spec_brand) NOT IN ('ផ្សេងៗ', 'Other', 'Others', '0', 'Plate Number', '2Year+', '212')
                THEN 'raw_fallback'
            ELSE 'unresolved'
        END                                                                 AS brand_source,

        -- Standardized Province & Economic Tier (Seed join; NO silent default to Phnom Penh)
        loc.standardized_province                                           AS province,
        loc.location_tier                                                   AS location_tier,

        -- Multilingual Categorical Normalization (NO silent defaults!)
        f.standardized_fuel                                                 AS vehicle_fuel_type,
        tr.standardized_transmission                                        AS vehicle_transmission,
        tx.standardized_tax                                                 AS vehicle_tax_type,
        cond.standardized_condition                                         AS vehicle_condition,
        col.standardized_color                                              AS vehicle_color,
        bt.standardized_body_type                                           AS mapped_body_type

    FROM text_prepped t
    LEFT JOIN brand_seeds b
        ON LOWER(TRIM(CAST(t.raw_spec_brand AS VARCHAR))) = b.raw_value
    LEFT JOIN location_seeds loc
        ON LOWER(TRIM(CAST(t.raw_province AS VARCHAR))) = loc.raw_value
    LEFT JOIN fuel_seeds f
        ON LOWER(TRIM(CAST(t.raw_spec_fuel_type AS VARCHAR))) = f.raw_value
    LEFT JOIN transmission_seeds tr
        ON LOWER(TRIM(CAST(t.raw_spec_transmission AS VARCHAR))) = tr.raw_value
    LEFT JOIN tax_seeds tx
        ON LOWER(TRIM(CAST(t.raw_spec_tax_type AS VARCHAR))) = tx.raw_value
    LEFT JOIN condition_seeds cond
        ON LOWER(TRIM(CAST(t.raw_spec_condition AS VARCHAR))) = cond.raw_value
    LEFT JOIN color_seeds col
        ON LOWER(TRIM(CAST(t.raw_spec_color AS VARCHAR))) = col.raw_value
    LEFT JOIN body_seeds bt
        ON LOWER(TRIM(CAST(t.raw_spec_body_type AS VARCHAR))) = bt.raw_value
),

-- Step 3: Model Candidates & Seed Joins
model_candidates AS (
    SELECT
        st.*,
        m.standardized_model AS seed_model,
        {{ extract_model_from_title('st.vehicle_brand', 'st.title_clean') }} AS title_extracted_model
    FROM standardized st
    LEFT JOIN model_seeds m
        ON st.vehicle_brand = m.brand
       AND LOWER(TRIM(CAST(st.raw_spec_model AS VARCHAR))) = m.raw_alias
),

model_resolved AS (
    SELECT
        mc.*,

        -- Final Resolved Vehicle Model
        COALESCE(
            mc.seed_model,
            mc.title_extracted_model,
            CASE
                WHEN TRIM(mc.raw_spec_model) IN ('ផ្សេងៗ', 'Other', 'Others', '0', 'Auto', 'Manual', 'Diesel', 'Gasoline', 'Hybrid') THEN NULL
                ELSE NULLIF(TRIM(mc.raw_spec_model), '')
            END
        ) AS vehicle_model,

        CASE
            WHEN mc.seed_model IS NOT NULL THEN 'seed_alias'
            WHEN mc.title_extracted_model IS NOT NULL THEN 'title_regex'
            WHEN NULLIF(TRIM(mc.raw_spec_model), '') IS NOT NULL
             AND TRIM(mc.raw_spec_model) NOT IN ('ផ្សេងៗ', 'Other', 'Others', '0', 'Auto', 'Manual', 'Diesel', 'Gasoline', 'Hybrid')
                THEN 'raw_fallback'
            ELSE 'unresolved'
        END AS model_extraction_method

    FROM model_candidates mc
),

tier_resolved AS (
    SELECT
        mr.*,
        -- Pure Data-Driven Brand Tier from Seed Dictionary
        COALESCE(bt.brand_tier, 'Other') AS brand_tier
    FROM model_resolved mr
    LEFT JOIN brand_tier_lookup bt
        ON mr.vehicle_brand = bt.standardized_brand
)

SELECT * FROM tier_resolved
