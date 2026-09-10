-- dbt/models/intermediate/int_cars_cleaned.sql
-- Silver Layer: Cleans, standardizes, validates, and quality-flags vehicle listings.
-- Preserves raw values, historical snapshot grain, and assigns explicit quality statuses & reasons.
-- Strictly avoids arbitrary defaults (never fills NULL with Petrol, Automatic, White, or Phnom Penh).

{{ config(
    materialized = 'table',
    post_hook    = [
        "COPY {{ this }} TO 'data/silver/cars_cleaned.parquet' (FORMAT PARQUET)",
        "COPY {{ this }} TO 'data/silver/cars_cleaned.csv' (HEADER, DELIMITER ',')"
    ]
) }}

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
    SELECT DISTINCT LOWER(TRIM(raw_value)) AS raw_value, standardized_province
    FROM {{ ref('seed_location_mapping') }}
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

-- Step 1: Text & Entity Standardization
standardized AS (
    SELECT
        s.*,
        {{ clean_text('s.raw_title') }}                                     AS title_clean,
        {{ clean_text('s.raw_description') }}                               AS description_clean,

        -- Standardized Brand (Seed join with regex title fallback for 'ផ្សេងៗ' / unmapped)
        NULLIF(
            NULLIF(
                NULLIF(
                    COALESCE(
                        b.standardized_brand,
                        CASE
                            WHEN LOWER(s.raw_title) LIKE '%toyota%' OR LOWER(s.raw_title) LIKE '%តូយ៉ូតា%' THEN 'Toyota'
                            WHEN LOWER(s.raw_title) LIKE '%lexus%' OR LOWER(s.raw_title) LIKE '%ឡិចស៊ីស%' THEN 'Lexus'
                            WHEN LOWER(s.raw_title) LIKE '%mercedes%' OR LOWER(s.raw_title) LIKE '%benz%' OR LOWER(s.raw_title) LIKE '%ប៊េន%' THEN 'Mercedes-Benz'
                            WHEN LOWER(s.raw_title) LIKE '%bmw%' OR LOWER(s.raw_title) LIKE '%ប៊ីអឹម%' THEN 'BMW'
                            WHEN LOWER(s.raw_title) LIKE '%ford%' OR LOWER(s.raw_title) LIKE '%ហ្វត%' THEN 'Ford'
                            WHEN LOWER(s.raw_title) LIKE '%hyundai%' OR LOWER(s.raw_title) LIKE '%ហ៊ីយ៉ាន់ដាយ%' THEN 'Hyundai'
                            WHEN LOWER(s.raw_title) LIKE '%kia%' OR LOWER(s.raw_title) LIKE '%គីអា%' THEN 'Kia'
                            WHEN LOWER(s.raw_title) LIKE '%mazda%' OR LOWER(s.raw_title) LIKE '%ម៉ាសដា%' THEN 'Mazda'
                            WHEN LOWER(s.raw_title) LIKE '%mitsubishi%' OR LOWER(s.raw_title) LIKE '%មីស៊ូប៊ីស៊ី%' THEN 'Mitsubishi'
                            WHEN LOWER(s.raw_title) LIKE '%nissan%' OR LOWER(s.raw_title) LIKE '%នីសាន់%' THEN 'Nissan'
                            WHEN LOWER(s.raw_title) LIKE '%honda%' THEN 'Honda'
                            WHEN LOWER(s.raw_title) LIKE '%byd%' OR LOWER(s.raw_title) LIKE '%ប៊ីវ៉ាយឌី%' THEN 'BYD'
                            WHEN LOWER(s.raw_title) LIKE '%avatr%' OR LOWER(s.raw_title) LIKE '%អាវ៉ាតា%' THEN 'AVATR'
                            WHEN LOWER(s.raw_title) LIKE '%aion%' THEN 'Aion'
                            WHEN LOWER(s.raw_title) LIKE '%deepal%' THEN 'Deepal'
                            WHEN LOWER(s.raw_title) LIKE '%xiaomi%' OR LOWER(s.raw_title) LIKE '%ស្ដេចបច្ចេកវិទ្យា%' THEN 'Xiaomi'
                            WHEN LOWER(s.raw_title) LIKE '%mg%' THEN 'MG'
                            WHEN LOWER(s.raw_title) LIKE '%geely%' OR LOWER(s.raw_title) LIKE '%ជីលី%' THEN 'Geely'
                            WHEN LOWER(s.raw_title) LIKE '%rolls-royce%' OR LOWER(s.raw_title) LIKE '%rolls royce%' THEN 'Rolls-Royce'
                            WHEN LOWER(s.raw_title) LIKE '%land rover%' OR LOWER(s.raw_title) LIKE '%range rover%' THEN 'Land Rover'
                            WHEN LOWER(s.raw_title) LIKE '%porsche%' THEN 'Porsche'
                            WHEN LOWER(s.raw_title) LIKE '%cadillac%' THEN 'Cadillac'
                            WHEN LOWER(s.raw_title) LIKE '%audi%' THEN 'Audi'
                            WHEN LOWER(s.raw_title) LIKE '%jeep%' THEN 'Jeep'
                            WHEN LOWER(s.raw_title) LIKE '%volkswagen%' OR LOWER(s.raw_title) LIKE '%vw%' THEN 'Volkswagen'
                            WHEN LOWER(s.raw_title) LIKE '%suzuki%' THEN 'Suzuki'
                            WHEN LOWER(s.raw_title) LIKE '%isuzu%' THEN 'Isuzu'
                            WHEN LOWER(s.raw_title) LIKE '%subaru%' THEN 'Subaru'
                            WHEN LOWER(s.raw_title) LIKE '%chevrolet%' OR LOWER(s.raw_title) LIKE '%chevy%' THEN 'Chevrolet'
                            WHEN TRIM(s.raw_spec_brand) IN ('ផ្សេងៗ', 'Other', 'Others') THEN NULL
                            ELSE NULLIF(TRIM(s.raw_spec_brand), '')
                        END
                    ),
                    'ផ្សេងៗ'
                ),
                'Other'
            ),
            'Others'
        )                                                                   AS vehicle_brand,

        -- Standardized Province (Seed join; NO silent default to Phnom Penh)
        loc.standardized_province                                           AS province,

        -- Multilingual Categorical Normalization (NO silent defaults!)
        f.standardized_fuel                                                 AS vehicle_fuel_type,
        tr.standardized_transmission                                        AS vehicle_transmission,
        tx.standardized_tax                                                 AS vehicle_tax_type,
        cond.standardized_condition                                         AS vehicle_condition,
        col.standardized_color                                              AS vehicle_color,
        bt.standardized_body_type                                           AS mapped_body_type

    FROM staging s
    LEFT JOIN brand_seeds b
        ON LOWER(TRIM(CAST(s.raw_spec_brand AS VARCHAR))) = b.raw_value
    LEFT JOIN location_seeds loc
        ON LOWER(TRIM(CAST(s.raw_province AS VARCHAR))) = loc.raw_value
    LEFT JOIN fuel_seeds f
        ON LOWER(TRIM(CAST(s.raw_spec_fuel_type AS VARCHAR))) = f.raw_value
    LEFT JOIN transmission_seeds tr
        ON LOWER(TRIM(CAST(s.raw_spec_transmission AS VARCHAR))) = tr.raw_value
    LEFT JOIN tax_seeds tx
        ON LOWER(TRIM(CAST(s.raw_spec_tax_type AS VARCHAR))) = tx.raw_value
    LEFT JOIN condition_seeds cond
        ON LOWER(TRIM(CAST(s.raw_spec_condition AS VARCHAR))) = cond.raw_value
    LEFT JOIN color_seeds col
        ON LOWER(TRIM(CAST(s.raw_spec_color AS VARCHAR))) = col.raw_value
    LEFT JOIN body_seeds bt
        ON LOWER(TRIM(CAST(s.raw_spec_body_type AS VARCHAR))) = bt.raw_value
),

-- Step 2: Model & Year Resolution
model_resolved AS (
    SELECT
        st.*,

        -- Model Resolution (Seed alias first, then brand-specific regex extraction for 'ផ្សេងៗ'/unmatched)
        NULLIF(
            NULLIF(
                NULLIF(
                    COALESCE(
                        m.standardized_model,
                        CASE
                WHEN st.vehicle_brand = 'Toyota' AND REGEXP_MATCHES(LOWER(st.title_clean), '\bprius\b') THEN 'Prius'
                WHEN st.vehicle_brand = 'Toyota' AND REGEXP_MATCHES(LOWER(st.title_clean), '\bcamry\b') THEN 'Camry'
                WHEN st.vehicle_brand = 'Toyota' AND REGEXP_MATCHES(LOWER(st.title_clean), '\bcorolla\s*cross\b') THEN 'Corolla Cross'
                WHEN st.vehicle_brand = 'Toyota' AND REGEXP_MATCHES(LOWER(st.title_clean), '\bcorolla\b') THEN 'Corolla'
                WHEN st.vehicle_brand = 'Toyota' AND REGEXP_MATCHES(LOWER(st.title_clean), 'land\s*cruiser\s*prado|prado') THEN 'Land Cruiser Prado'
                WHEN st.vehicle_brand = 'Toyota' AND REGEXP_MATCHES(LOWER(st.title_clean), 'land\s*cruiser|\blc\b|lc200|lc300') THEN 'Land Cruiser'
                WHEN st.vehicle_brand = 'Toyota' AND REGEXP_MATCHES(LOWER(st.title_clean), 'hilux\s*revo|revo') THEN 'Hilux Revo'
                WHEN st.vehicle_brand = 'Toyota' AND REGEXP_MATCHES(LOWER(st.title_clean), 'hilux\s*vigo|vigo') THEN 'Hilux Vigo'
                WHEN st.vehicle_brand = 'Toyota' AND REGEXP_MATCHES(LOWER(st.title_clean), '\bhilux\b') THEN 'Hilux'
                WHEN st.vehicle_brand = 'Toyota' AND REGEXP_MATCHES(LOWER(st.title_clean), '\braize\b') THEN 'Raize'
                WHEN st.vehicle_brand = 'Toyota' AND REGEXP_MATCHES(LOWER(st.title_clean), '\bfortuner\b') THEN 'Fortuner'
                WHEN st.vehicle_brand = 'Toyota' AND REGEXP_MATCHES(LOWER(st.title_clean), '\bhighlander\b') THEN 'Highlander'
                WHEN st.vehicle_brand = 'Toyota' AND REGEXP_MATCHES(LOWER(st.title_clean), '\brav4\b|rav\s*4') THEN 'RAV4'
                WHEN st.vehicle_brand = 'Toyota' AND REGEXP_MATCHES(LOWER(st.title_clean), '\balphard\b') THEN 'Alphard'
                WHEN st.vehicle_brand = 'Toyota' AND REGEXP_MATCHES(LOWER(st.title_clean), '\bvellfire\b') THEN 'Vellfire'
                WHEN st.vehicle_brand = 'Toyota' AND REGEXP_MATCHES(LOWER(st.title_clean), '\byaris\s*cross\b') THEN 'Yaris Cross'
                WHEN st.vehicle_brand = 'Toyota' AND REGEXP_MATCHES(LOWER(st.title_clean), '\byaris\b') THEN 'Yaris'
                WHEN st.vehicle_brand = 'Toyota' AND REGEXP_MATCHES(LOWER(st.title_clean), '\bwigo\b') THEN 'Wigo'
                WHEN st.vehicle_brand = 'Toyota' AND REGEXP_MATCHES(LOWER(st.title_clean), '\bveloz\b') THEN 'Veloz'

                WHEN st.vehicle_brand = 'Lexus' AND REGEXP_MATCHES(LOWER(st.title_clean), 'rx\s*300|rx300') THEN 'RX300'
                WHEN st.vehicle_brand = 'Lexus' AND REGEXP_MATCHES(LOWER(st.title_clean), 'rx\s*330|rx330') THEN 'RX330'
                WHEN st.vehicle_brand = 'Lexus' AND REGEXP_MATCHES(LOWER(st.title_clean), 'rx\s*350|rx350') THEN 'RX350'
                WHEN st.vehicle_brand = 'Lexus' AND REGEXP_MATCHES(LOWER(st.title_clean), 'rx\s*450|rx450') THEN 'RX450h'
                WHEN st.vehicle_brand = 'Lexus' AND REGEXP_MATCHES(LOWER(st.title_clean), 'lx\s*570|lx570') THEN 'LX570'
                WHEN st.vehicle_brand = 'Lexus' AND REGEXP_MATCHES(LOWER(st.title_clean), 'lx\s*600|lx600') THEN 'LX600'
                WHEN st.vehicle_brand = 'Lexus' AND REGEXP_MATCHES(LOWER(st.title_clean), 'lx\s*700|lx700h') THEN 'LX700h'
                WHEN st.vehicle_brand = 'Lexus' AND REGEXP_MATCHES(LOWER(st.title_clean), 'nx\s*200t|nx200t') THEN 'NX200t'
                WHEN st.vehicle_brand = 'Lexus' AND REGEXP_MATCHES(LOWER(st.title_clean), 'nx\s*300|nx300') THEN 'NX300'
                WHEN st.vehicle_brand = 'Lexus' AND REGEXP_MATCHES(LOWER(st.title_clean), 'gx\s*460|gx460') THEN 'GX460'
                WHEN st.vehicle_brand = 'Lexus' AND REGEXP_MATCHES(LOWER(st.title_clean), 'gx\s*470|gx470') THEN 'GX470'
                WHEN st.vehicle_brand = 'Lexus' AND REGEXP_MATCHES(LOWER(st.title_clean), '\blm\b|lm350|lm300') THEN 'LM'

                WHEN st.vehicle_brand = 'Ford' AND REGEXP_MATCHES(LOWER(st.title_clean), 'ranger\s*raptor|\braptor\b') THEN 'Ranger Raptor'
                WHEN st.vehicle_brand = 'Ford' AND REGEXP_MATCHES(LOWER(st.title_clean), 'ranger\s*wildtrak|\bwildtrak\b') THEN 'Ranger Wildtrak'
                WHEN st.vehicle_brand = 'Ford' AND REGEXP_MATCHES(LOWER(st.title_clean), '\branger\b') THEN 'Ranger'
                WHEN st.vehicle_brand = 'Ford' AND REGEXP_MATCHES(LOWER(st.title_clean), '\beverest\b') THEN 'Everest'
                WHEN st.vehicle_brand = 'Ford' AND REGEXP_MATCHES(LOWER(st.title_clean), '\bterritory\b') THEN 'Territory'
                WHEN st.vehicle_brand = 'Ford' AND REGEXP_MATCHES(LOWER(st.title_clean), 'f\-?150') THEN 'F-150'

                WHEN st.vehicle_brand = 'Hyundai' AND REGEXP_MATCHES(LOWER(st.title_clean), 'starex|\bh1\b|\bh\-1\b') THEN 'Starex'
                WHEN st.vehicle_brand = 'Hyundai' AND REGEXP_MATCHES(LOWER(st.title_clean), 'santa\s*fe|santafe') THEN 'Santa Fe'
                WHEN st.vehicle_brand = 'Hyundai' AND REGEXP_MATCHES(LOWER(st.title_clean), '\btucson\b') THEN 'Tucson'
                WHEN st.vehicle_brand = 'Hyundai' AND REGEXP_MATCHES(LOWER(st.title_clean), '\bpalisade\b') THEN 'Palisade'

                WHEN st.vehicle_brand = 'Kia' AND REGEXP_MATCHES(LOWER(st.title_clean), '\bmorning\b') THEN 'Morning'
                WHEN st.vehicle_brand = 'Kia' AND REGEXP_MATCHES(LOWER(st.title_clean), '\bcarnival\b') THEN 'Carnival'
                WHEN st.vehicle_brand = 'Kia' AND REGEXP_MATCHES(LOWER(st.title_clean), '\bsorento\b') THEN 'Sorento'
                WHEN st.vehicle_brand = 'Kia' AND REGEXP_MATCHES(LOWER(st.title_clean), '\bsportage\b') THEN 'Sportage'
                WHEN st.vehicle_brand = 'Kia' AND REGEXP_MATCHES(LOWER(st.title_clean), '\bev5\b') THEN 'EV5'

                WHEN st.vehicle_brand = 'BYD' AND REGEXP_MATCHES(LOWER(st.title_clean), 'atto\s*3|atto3') THEN 'Atto 3'
                WHEN st.vehicle_brand = 'BYD' AND REGEXP_MATCHES(LOWER(st.title_clean), '\bdolphin\b') THEN 'Dolphin'
                WHEN st.vehicle_brand = 'BYD' AND REGEXP_MATCHES(LOWER(st.title_clean), '\bseal\b') THEN 'Seal'

                WHEN st.vehicle_brand = 'Xiaomi' AND REGEXP_MATCHES(LOWER(st.title_clean), 'su7') THEN 'SU7'
                WHEN st.vehicle_brand = 'Xiaomi' AND REGEXP_MATCHES(LOWER(st.title_clean), 'yu7') THEN 'YU7'

                WHEN st.vehicle_brand = 'AVATR' AND REGEXP_MATCHES(LOWER(st.title_clean), '07|\b07\b') THEN 'AVATR 07'
                WHEN st.vehicle_brand = 'AVATR' AND REGEXP_MATCHES(LOWER(st.title_clean), '11|\b11\b') THEN 'AVATR 11'
                WHEN st.vehicle_brand = 'AVATR' AND REGEXP_MATCHES(LOWER(st.title_clean), '12|\b12\b') THEN 'AVATR 12'

                WHEN st.vehicle_brand = 'Geely' AND REGEXP_MATCHES(LOWER(st.title_clean), '\bmonjaro\b') THEN 'Monjaro'
                WHEN st.vehicle_brand = 'Geely' AND REGEXP_MATCHES(LOWER(st.title_clean), '\bcoolray\b') THEN 'Coolray'

                WHEN st.vehicle_brand = 'Mercedes-Benz' AND REGEXP_MATCHES(LOWER(st.title_clean), '\bmaybach\b|s580|s680') THEN 'Maybach'
                WHEN st.vehicle_brand = 'Mercedes-Benz' AND REGEXP_MATCHES(LOWER(st.title_clean), 's\-?class|s400|s500') THEN 'S-Class'
                WHEN st.vehicle_brand = 'Mercedes-Benz' AND REGEXP_MATCHES(LOWER(st.title_clean), 'c\-?class|c200|c300') THEN 'C-Class'
                WHEN st.vehicle_brand = 'Mercedes-Benz' AND REGEXP_MATCHES(LOWER(st.title_clean), 'e\-?class|e200|e300') THEN 'E-Class'
                WHEN st.vehicle_brand = 'Mercedes-Benz' AND REGEXP_MATCHES(LOWER(st.title_clean), '\bglc\b') THEN 'GLC'

                WHEN st.vehicle_brand = 'Rolls-Royce' AND REGEXP_MATCHES(LOWER(st.title_clean), '\bcullinan\b') THEN 'Cullinan'

                WHEN TRIM(st.raw_spec_model) IN ('ផ្សេងៗ', 'Other', 'Others') THEN NULL
                ELSE NULLIF(TRIM(st.raw_spec_model), '')
            END
        ),
        'ផ្សេងៗ'
    ),
    'Other'
),
'Others'
)                                                                   AS vehicle_model,

        CASE
            WHEN m.standardized_model IS NOT NULL AND m.standardized_model NOT IN ('ផ្សេងៗ', 'Other', 'Others') THEN 'seed_alias'
            WHEN NULLIF(TRIM(st.raw_spec_model), '') IS NOT NULL AND TRIM(st.raw_spec_model) NOT IN ('ផ្សេងៗ', 'Other', 'Others') THEN 'raw_spec'
            ELSE 'title_extracted'
        END                                                                 AS model_extraction_method

    FROM standardized st
    LEFT JOIN model_seeds m
        ON  st.vehicle_brand = m.brand
        AND LOWER(TRIM(CAST(st.raw_spec_model AS VARCHAR))) = m.raw_alias
),

-- Step 3: Year Inversion Healing & Standardization
year_resolved AS (
    SELECT
        mr.*,

        -- Evidence-Based Year Inversion Healing & Standardization
        {{ heal_chronological_inversion('mr.raw_spec_year', 'mr.title_clean', 'mr.vehicle_model') }} AS vehicle_year,

        CASE
            WHEN TRY_CAST(mr.raw_spec_year AS INTEGER) IN (2026, 2027)
             AND {{ heal_chronological_inversion('mr.raw_spec_year', 'mr.title_clean', 'mr.vehicle_model') }} IN (2006, 2007)
                THEN 1
            ELSE 0
        END                                                                 AS is_year_healed,

        CASE
            WHEN TRY_CAST(mr.raw_spec_year AS INTEGER) IS NOT NULL THEN 'raw_spec'
            WHEN REGEXP_MATCHES(CAST(mr.title_clean AS VARCHAR), '\b(19[9][0-9]|20[0-2][0-9])\b') THEN 'title_regex'
            ELSE NULL
        END                                                                 AS year_source

    FROM model_resolved mr
),

-- Step 4: Physical Specs Parsing & Clamping (NLP from title & description)
specs_parsed AS (
    SELECT
        yr.*,

        -- Normalized Body Type (Seed mapping first, then verified model fallback when missing/ផ្សេងៗ)
        COALESCE(
            yr.mapped_body_type,
            CASE
                WHEN yr.vehicle_model IN ('Prius', 'Yaris', 'Swift', 'Fit', 'Jazz') THEN 'Hatchback'
                WHEN yr.vehicle_model IN ('Camry', 'Corolla', 'Civic', 'Accord', 'ES350', 'ES300', 'ES300h', 'C-Class', 'E-Class', 'S-Class', '3 Series', '5 Series', '7 Series', 'Morning', 'K5') THEN 'Sedan'
                WHEN yr.vehicle_model IN ('Hilux', 'Hilux Revo', 'Hilux Vigo', 'Ranger', 'Ranger Raptor', 'Ranger Wildtrak', 'F-150', 'Tacoma', 'Tundra', 'Navara', 'Triton', 'D-Max', 'BT-50') THEN 'Pickup'
                WHEN yr.vehicle_model IN ('Alphard', 'Vellfire', 'Starex', 'H1', 'Carnival', 'Sienna', 'Custin', 'LM', 'Avanza') THEN 'MPV'
                WHEN yr.vehicle_model IN ('RAV4', 'CR-V', 'RX300', 'RX330', 'RX350', 'RX450h', 'NX200t', 'NX300', 'LX570', 'LX600', 'LX470', 'GX460', 'GX470', 'Land Cruiser', 'Land Cruiser Prado', 'Fortuner', 'Highlander', 'Everest', 'Explorer', 'Santa Fe', 'Tucson', 'Palisade', 'Sorento', 'Sportage', 'X5', 'X6', 'X7', 'X3', 'GLC', 'GLE', 'Atto 3', 'Monjaro', 'Coolray', 'Raize', 'Rush', 'Corolla Cross', 'Yaris Cross', 'Territory') THEN 'SUV'
                ELSE NULL
            END
        )                                                                   AS vehicle_body_type,

        -- Multi-source mileage extraction clamped between 0 and 500,000 km
        CASE
            WHEN {{ parse_mileage('yr.raw_spec_mileage', 'yr.title_clean', 'yr.description_clean', 'yr.vehicle_fuel_type') }} BETWEEN 0 AND 500000
                THEN {{ parse_mileage('yr.raw_spec_mileage', 'yr.title_clean', 'yr.description_clean', 'yr.vehicle_fuel_type') }}
            ELSE NULL
        END                                                                 AS vehicle_mileage_km,

        CASE
            WHEN yr.raw_spec_mileage IS NOT NULL AND TRY_CAST(yr.raw_spec_mileage AS BIGINT) IS NOT NULL THEN 'raw_spec'
            WHEN {{ parse_mileage('yr.raw_spec_mileage', 'yr.title_clean', 'yr.description_clean', 'yr.vehicle_fuel_type') }} IS NOT NULL THEN 'nlp_text'
            ELSE NULL
        END                                                                 AS mileage_source,

        -- Multi-source engine CC clamped between 500 and 7,000 cc (0 for EV)
        CASE
            WHEN {{ parse_engine_cc('yr.raw_spec_engine_size', 'yr.title_clean', 'yr.description_clean', 'yr.vehicle_fuel_type', 'yr.vehicle_brand') }} = 0
                THEN 0
            WHEN {{ parse_engine_cc('yr.raw_spec_engine_size', 'yr.title_clean', 'yr.description_clean', 'yr.vehicle_fuel_type', 'yr.vehicle_brand') }} BETWEEN 500 AND 7000
                THEN {{ parse_engine_cc('yr.raw_spec_engine_size', 'yr.title_clean', 'yr.description_clean', 'yr.vehicle_fuel_type', 'yr.vehicle_brand') }}
            ELSE NULL
        END                                                                 AS vehicle_engine_cc,

        CASE
            WHEN yr.vehicle_fuel_type = 'Electric'
              OR (yr.vehicle_brand IN ('Tesla', 'NIO', 'Zeekr', 'Polestar', 'Rivian', 'Lucid') AND COALESCE(yr.vehicle_fuel_type, '') NOT IN ('Hybrid', 'Petrol', 'Diesel'))
                THEN 'ev_zero_cc'
            WHEN yr.raw_spec_engine_size IS NOT NULL THEN 'raw_spec'
            WHEN {{ parse_engine_cc('yr.raw_spec_engine_size', 'yr.title_clean', 'yr.description_clean', 'yr.vehicle_fuel_type', 'yr.vehicle_brand') }} IS NOT NULL THEN 'nlp_text'
            ELSE NULL
        END                                                                 AS engine_source,

        -- Title NLP features
        {{ extract_nlp_signals('yr.title_clean') }},

        -- Non-vehicle spam detection
        {{ detect_non_vehicle_spam('yr.title_clean', 'yr.description_clean', 'yr.price') }} AS is_spam,

        -- Financing down-payment detection
        {{ detect_down_payment('yr.price', 'yr.vehicle_year', 'yr.title_clean', 'yr.description_clean') }} AS is_down_payment

    FROM year_resolved yr
),

-- Step 5: Outlier Detection & Quality Classification
evaluated AS (
    SELECT
        p.*,
        {{ classify_brand_tier('p.vehicle_brand') }} AS brand_tier,

        -- Domain-Grounded Price Outlier Detection
        {{ detect_price_outlier('p.price', 'p.vehicle_brand', 'p.vehicle_model', 'p.vehicle_year') }} AS is_price_outlier

    FROM specs_parsed p
)

SELECT
    listing_id,
    scrape_date,
    scraped_at,
    posted_at,
    listing_url,
    thumbnail_url,

    -- Cleaned & Conformed Text Entities
    title_clean,
    description_clean,

    -- Validated Price & Currency
    price,
    initial_price,
    price_drop_amount,
    has_price_drop,
    'USD'                                                                   AS currency,

    -- Standardized Vehicle Specs (100% Typed & Conformed)
    vehicle_brand,
    brand_tier,
    vehicle_model,
    model_extraction_method,
    vehicle_year,
    year_source,
    is_year_healed,
    vehicle_body_type,
    vehicle_mileage_km,
    mileage_source,
    vehicle_engine_cc,
    engine_source,
    vehicle_fuel_type,
    vehicle_transmission,
    vehicle_color,
    vehicle_condition,
    vehicle_tax_type,

    -- Location & Seller
    province,
    raw_district                                                            AS district,
    seller_id,
    seller_name,
    seller_type,
    seller_username,
    seller_phones,

    -- Market Dynamics
    has_full_option,
    is_urgent_sale,
    days_on_market,

    -- Anomaly Detection Flags
    is_spam,
    is_down_payment,
    is_price_outlier,

    -- 5-Tier Data Quality Classification (QUARANTINED > INVALID > SUSPICIOUS > WARNING > VALID)
    CASE
        WHEN is_spam = 1 OR listing_id IS NULL OR price IS NULL OR price <= 0
            THEN 'QUARANTINED'
        WHEN vehicle_year < 1990
          OR vehicle_year > (CAST(date_part('year', CURRENT_DATE) AS INTEGER) + 1)
          OR price < 500
            THEN 'INVALID'
        WHEN is_down_payment = 1 OR is_price_outlier = 1
            THEN 'SUSPICIOUS'
        WHEN vehicle_brand IS NULL
          OR vehicle_model IS NULL
          OR vehicle_mileage_km IS NULL
          OR vehicle_fuel_type IS NULL
          OR vehicle_transmission IS NULL
          OR vehicle_engine_cc IS NULL
          OR province IS NULL
            THEN 'WARNING'
        ELSE 'VALID'
    END                                                                     AS data_quality_status,

    -- Diagnostic Audit Reason Codes
    CONCAT_WS('|',
        CASE WHEN is_spam = 1 THEN 'NON_VEHICLE_SPAM' END,
        CASE WHEN price IS NULL THEN 'MISSING_PRICE' END,
        CASE WHEN price <= 0 THEN 'INVALID_PRICE' END,
        CASE WHEN price < 500 THEN 'PRICE_BELOW_MINIMUM' END,
        CASE WHEN is_down_payment = 1 THEN 'DOWN_PAYMENT_PRICE' END,
        CASE WHEN is_price_outlier = 1 THEN 'SUSPICIOUS_PRICE_OUTLIER' END,
        CASE WHEN vehicle_year < 1990 OR vehicle_year > (CAST(date_part('year', CURRENT_DATE) AS INTEGER) + 1) THEN 'INVALID_YEAR' END,
        CASE WHEN is_year_healed = 1 THEN 'YEAR_INVERSION_HEALED' END,
        CASE WHEN vehicle_brand IS NULL THEN 'UNKNOWN_BRAND' END,
        CASE WHEN vehicle_model IS NULL THEN 'UNKNOWN_MODEL' END,
        CASE WHEN province IS NULL THEN 'MISSING_LOCATION' END,
        CASE WHEN vehicle_mileage_km IS NULL THEN 'MISSING_MILEAGE' END,
        CASE WHEN vehicle_engine_cc IS NULL THEN 'MISSING_ENGINE_CC' END,
        CASE WHEN vehicle_fuel_type IS NULL THEN 'MISSING_FUEL_TYPE' END,
        CASE WHEN vehicle_transmission IS NULL THEN 'MISSING_TRANSMISSION' END
    )                                                                       AS data_quality_reasons

FROM evaluated
