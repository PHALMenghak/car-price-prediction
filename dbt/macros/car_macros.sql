-- dbt/macros/car_macros.sql
-- Production vehicle data transformation macros for DuckDB.

-- 1. Text Cleaning: Whitespace normalization, HTML unescaping, zero-width space removal
{% macro clean_text(col) %}
NULLIF(
    TRIM(
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                REGEXP_REPLACE(
                    REGEXP_REPLACE(
                        REPLACE(
                            REPLACE(
                                REPLACE(
                                    COALESCE(CAST({{ col }} AS VARCHAR), ''),
                                    chr(8203), ''
                                ),
                                chr(65279), ''
                            ),
                            '&amp;', '&'
                        ),
                        '&nbsp;|&quot;|&lt;|&gt;', ' ', 'g'
                    ),
                    '[\x{1F000}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}\x{FE00}-\x{FE0F}\x{FFFC}]', ' ', 'g'
                ),
                '[*=_~-]{3,}', ' ', 'g'
            ),
            '\s+', ' ', 'g'
        )
    ),
    ''
)
{% endmacro %}


-- 2. Multi-Source Mileage Parsing (returns integer km or NULL)
-- Inspects raw spec column first, then extracts from title and description.
-- Distinguishes Khmer miles (មុឺនម៉ាយ/ម៉ឺនMiles) vs kilometers (មុឺនគីឡូ/km).
-- Prevents mistaking EV battery range (e.g. 520km range) for odometer distance.
{% macro parse_mileage(raw_mileage_col, title_col, desc_col, fuel_col) %}
    CASE
        -- 1. Structured spec if valid number
        WHEN {{ raw_mileage_col }} IS NOT NULL
          AND REGEXP_MATCHES(TRIM(CAST({{ raw_mileage_col }} AS VARCHAR)), '^[0-9]+(\.[0-9]+)?$')
          AND TRY_CAST(REGEXP_REPLACE(TRIM(CAST({{ raw_mileage_col }} AS VARCHAR)), '\..*', '') AS BIGINT) BETWEEN 0 AND 500000
            THEN TRY_CAST(REGEXP_REPLACE(TRIM(CAST({{ raw_mileage_col }} AS VARCHAR)), '\..*', '') AS BIGINT)

        -- 2. Khmer miles in Title/Desc: Xមុឺនម៉ាយ / Xម៉ឺនMiles / Xម៉ឺនម៉ាយ (val * 10,000 * 1.60934)
        WHEN REGEXP_MATCHES(LOWER(COALESCE(CAST({{ title_col }} AS VARCHAR), '') || ' ' || COALESCE(CAST({{ desc_col }} AS VARCHAR), '')), '([0-9]+(?:\.[0-9]+)?)\s*(?:មុឺន|ម៉ឺន)\s*(?:ម៉ាយ|miles?|mile)')
            THEN TRY_CAST(ROUND(
                TRY_CAST(REGEXP_EXTRACT(LOWER(COALESCE(CAST({{ title_col }} AS VARCHAR), '') || ' ' || COALESCE(CAST({{ desc_col }} AS VARCHAR), '')), '([0-9]+(?:\.[0-9]+)?)\s*(?:មុឺន|ម៉ឺន)\s*(?:ម៉ាយ|miles?|mile)', 1) AS DOUBLE)
                * 10000.0 * 1.60934
            ) AS BIGINT)

        -- 3. Khmer km in Title/Desc: Xមុឺនគីឡូ / Xម៉ឺនគីឡូ (val * 10,000)
        WHEN REGEXP_MATCHES(LOWER(COALESCE(CAST({{ title_col }} AS VARCHAR), '') || ' ' || COALESCE(CAST({{ desc_col }} AS VARCHAR), '')), '([0-9]+(?:\.[0-9]+)?)\s*(?:មុឺន|ម៉ឺន)\s*(?:គីឡូ|km)?')
            THEN TRY_CAST(ROUND(
                TRY_CAST(REGEXP_EXTRACT(LOWER(COALESCE(CAST({{ title_col }} AS VARCHAR), '') || ' ' || COALESCE(CAST({{ desc_col }} AS VARCHAR), '')), '([0-9]+(?:\.[0-9]+)?)\s*(?:មុឺន|ម៉ឺន)\s*(?:គីឡូ|km)?', 1) AS DOUBLE)
                * 10000.0
            ) AS BIGINT)

        -- 4. English miles with unit: X miles (val * 1.60934)
        WHEN REGEXP_MATCHES(LOWER(COALESCE(CAST({{ title_col }} AS VARCHAR), '') || ' ' || COALESCE(CAST({{ desc_col }} AS VARCHAR), '')), '\b([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{2,6})\s*(?:miles?|mile)\b')
            THEN TRY_CAST(ROUND(
                TRY_CAST(REGEXP_REPLACE(REGEXP_EXTRACT(LOWER(COALESCE(CAST({{ title_col }} AS VARCHAR), '') || ' ' || COALESCE(CAST({{ desc_col }} AS VARCHAR), '')), '\b([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{2,6})\s*(?:miles?|mile)\b', 1), ',', '', 'g') AS DOUBLE)
                * 1.60934
            ) AS BIGINT)

        -- 5. Explicit odometer km (avoiding EV range by checking context or requiring > 1000 km or odometer keywords)
        WHEN REGEXP_MATCHES(LOWER(COALESCE(CAST({{ title_col }} AS VARCHAR), '') || ' ' || COALESCE(CAST({{ desc_col }} AS VARCHAR), '')), '(?:ជិះបាន|ប្រើបាន|odo|km\s*zin|mileage)[^0-9]*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{3,6})\s*(?:km|គីឡូ)?')
            THEN TRY_CAST(REGEXP_REPLACE(REGEXP_EXTRACT(LOWER(COALESCE(CAST({{ title_col }} AS VARCHAR), '') || ' ' || COALESCE(CAST({{ desc_col }} AS VARCHAR), '')), '(?:ជិះបាន|ប្រើបាន|odo|km\s*zin|mileage)[^0-9]*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{3,6})\s*(?:km|គីឡូ)?', 1), ',', '', 'g') AS BIGINT)

        -- 6. Direct km (>= 1,500 km to avoid EV battery ranges like 520km, 650km)
        WHEN REGEXP_MATCHES(LOWER(COALESCE(CAST({{ title_col }} AS VARCHAR), '') || ' ' || COALESCE(CAST({{ desc_col }} AS VARCHAR), '')), '\b([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,6})\s*(?:km|kms|គីឡូ)\b')
            THEN TRY_CAST(REGEXP_REPLACE(REGEXP_EXTRACT(LOWER(COALESCE(CAST({{ title_col }} AS VARCHAR), '') || ' ' || COALESCE(CAST({{ desc_col }} AS VARCHAR), '')), '\b([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,6})\s*(?:km|kms|គីឡូ)\b', 1), ',', '', 'g') AS BIGINT)

        ELSE NULL
    END
{% endmacro %}


-- 3. Multi-Source Engine CC Parsing (returns integer cc or NULL)
-- Sets 0 cc for pure Electric Vehicles.
-- Parses decimal litres (e.g. 1.8L -> 1800cc) and explicit CC (e.g. 3500cc).
{% macro parse_engine_cc(raw_engine_col, title_col, desc_col, fuel_col, brand_col) %}
    CASE
        -- 1. Pure Electric Vehicles have 0 cc displacement
        WHEN LOWER(COALESCE(CAST({{ fuel_col }} AS VARCHAR), '')) IN ('electric', 'អគ្គិសនី', 'ev')
          OR {{ brand_col }} IN ('BYD', 'AVATR', 'Aion', 'Deepal', 'Zeekr', 'NIO', 'Xpeng', 'Tesla')
            THEN 0

        -- 2. Structured raw engine spec in litres (e.g. '1.8L', '2.5 L')
        WHEN REGEXP_MATCHES(LOWER(TRIM(COALESCE(CAST({{ raw_engine_col }} AS VARCHAR), ''))), '^[0-9]\.[0-9]\s*l?$')
            THEN TRY_CAST(ROUND(TRY_CAST(REGEXP_REPLACE(LOWER(TRIM(CAST({{ raw_engine_col }} AS VARCHAR))), '[^0-9\.]', '', 'g') AS DOUBLE) * 1000.0) AS INTEGER)

        -- 3. Structured raw engine spec in CC (e.g. '1800', '2000cc')
        WHEN REGEXP_MATCHES(LOWER(TRIM(COALESCE(CAST({{ raw_engine_col }} AS VARCHAR), ''))), '^[0-9]{3,4}\s*(cc)?$')
            THEN TRY_CAST(REGEXP_REPLACE(LOWER(TRIM(CAST({{ raw_engine_col }} AS VARCHAR))), '[^0-9]', '', 'g') AS INTEGER)

        -- 4. Explicit litres in Title/Desc: 1.8L, 2.5L, 3.5 L
        WHEN REGEXP_MATCHES(LOWER(COALESCE(CAST({{ title_col }} AS VARCHAR), '') || ' ' || COALESCE(CAST({{ desc_col }} AS VARCHAR), '')), '\b([1-6]\.[0-9])\s*(?:l|litre)\b')
            THEN TRY_CAST(ROUND(TRY_CAST(REGEXP_EXTRACT(LOWER(COALESCE(CAST({{ title_col }} AS VARCHAR), '') || ' ' || COALESCE(CAST({{ desc_col }} AS VARCHAR), '')), '\b([1-6]\.[0-9])\s*(?:l|litre)\b', 1) AS DOUBLE) * 1000.0) AS INTEGER)

        -- 5. Khmer engine keyword: ម៉ាស៊ីន 1.8 / ម៉ាសុីន 2.5
        WHEN REGEXP_MATCHES(LOWER(COALESCE(CAST({{ title_col }} AS VARCHAR), '') || ' ' || COALESCE(CAST({{ desc_col }} AS VARCHAR), '')), '(?:ម៉ាស៊ីន|ម៉ាសុីន|engine)\s*([1-6]\.[0-9])')
            THEN TRY_CAST(ROUND(TRY_CAST(REGEXP_EXTRACT(LOWER(COALESCE(CAST({{ title_col }} AS VARCHAR), '') || ' ' || COALESCE(CAST({{ desc_col }} AS VARCHAR), '')), '(?:ម៉ាស៊ីន|ម៉ាសុីន|engine)\s*([1-6]\.[0-9])', 1) AS DOUBLE) * 1000.0) AS INTEGER)

        -- 6. Explicit CC in Title/Desc: 1800cc, 2000 cc, 3500cc (MUST have 'cc' suffix to avoid mistaking model years)
        WHEN REGEXP_MATCHES(LOWER(COALESCE(CAST({{ title_col }} AS VARCHAR), '') || ' ' || COALESCE(CAST({{ desc_col }} AS VARCHAR), '')), '\b([1-6][0-9]{2,3})\s*cc\b')
            THEN TRY_CAST(REGEXP_EXTRACT(LOWER(COALESCE(CAST({{ title_col }} AS VARCHAR), '') || ' ' || COALESCE(CAST({{ desc_col }} AS VARCHAR), '')), '\b([1-6][0-9]{2,3})\s*cc\b', 1) AS INTEGER)

        ELSE NULL
    END
{% endmacro %}


-- 4. Evidence-Based Chronological Inversion Healing
-- Heals 2026/2027 years back to 2006/2007 ONLY with specific evidence (Prius, RX330, Camry 02-06, or title tokens).
-- Preserves legitimate modern 2026/2027 vehicles (Toyota Raize, AVATR 07, Aion, Fortuner 2026).
{% macro heal_chronological_inversion(raw_year_col, title_col, model_col) %}
    CASE
        -- Evidence 1: Spec year 2026 for Prius / Gen 2 models / explicit '2006' or '06' in title
        WHEN TRY_CAST({{ raw_year_col }} AS INTEGER) = 2026
          AND (
              LOWER(CAST({{ title_col }} AS VARCHAR)) LIKE '%2006%'
              OR LOWER(CAST({{ title_col }} AS VARCHAR)) LIKE '% 06%'
              OR LOWER(CAST({{ title_col }} AS VARCHAR)) LIKE '%06 %'
              OR LOWER(COALESCE({{ model_col }}, '')) IN ('prius', 'rx330', 'rx300')
          )
            THEN 2006

        -- Evidence 2: Spec year 2027 for Prius / Gen 2 models / explicit '2007' or '07' in title
        WHEN TRY_CAST({{ raw_year_col }} AS INTEGER) = 2027
          AND (
              LOWER(CAST({{ title_col }} AS VARCHAR)) LIKE '%2007%'
              OR LOWER(CAST({{ title_col }} AS VARCHAR)) LIKE '% 07%'
              OR LOWER(CAST({{ title_col }} AS VARCHAR)) LIKE '%07 %'
              OR LOWER(COALESCE({{ model_col }}, '')) IN ('prius', 'rx330', 'rx300')
          )
            THEN 2007

        -- Evidence 3: Fallback standard 4-digit cast
        WHEN TRY_CAST({{ raw_year_col }} AS INTEGER) BETWEEN 1990 AND (CAST(date_part('year', CURRENT_DATE) AS INTEGER) + 1)
            THEN TRY_CAST({{ raw_year_col }} AS INTEGER)

        -- Evidence 4: Title 4-digit year fallback if raw_spec_year was null
        WHEN REGEXP_MATCHES(CAST({{ title_col }} AS VARCHAR), '\b(19[9][0-9]|20[0-2][0-9])\b')
            THEN TRY_CAST(REGEXP_EXTRACT(CAST({{ title_col }} AS VARCHAR), '\b(19[9][0-9]|20[0-2][0-9])\b', 1) AS INTEGER)

        ELSE NULL
    END
{% endmacro %}


-- 5. Non-Vehicle / Accessory / Spam Detection
-- Identifies spare tires, wheels, grilles, license plates, rentals, and non-car ads posted under car listings.
-- Strictly avoids false positives on:
--   - Dealership plate bonuses (e.g. Free plate number, ថែមស្លាកលេខ)
--   - Maintenance notes (e.g. ប្តូរប្រេងទៀងទាត់ / regularly changed oil)
--   - Factory features (e.g. Four-wheel drive, 18-inch sport rims)
--   - Rental disclaimers (e.g. មិនធ្លាប់ជួល / never used as rental)
--   - Model names containing 'rent' (e.g. Kia Sorento)
{% macro detect_non_vehicle_spam(title_col, desc_col, price_col) %}
    CASE
        -- 1. Standalone Auto Accessories / Body Parts (Grilles, Spare Tires, Bumpers, LPG kits)
        WHEN (
            REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), '^(?:ប៉ាណាលេង|គ្រឿងបន្លាស់|កង់សាគួ)\b|លក់កង់សាគួ|លក់គ្រឿងបន្លាស់|លក់កាង\b|លក់ហ្គាស|លកហ្គាដ|bodykit\s*only')
            OR (
                REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), 'ប៉ាណាលេង|កង់សាគួ|spare\s*tire')
                AND ({{ price_col }} IS NULL OR {{ price_col }} < 3000)
            )
        )
        THEN 1

        -- 2. Non-Passenger Vehicles / Stolen Vehicle Reports / Community Alerts
        WHEN REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), '三轮|បោកឡាន|បាត់ឡាន|ជួយផ្សាយ')
        THEN 1

        -- 3. Standalone License Plate Sales (and NOT car registered with plate or dealer plate bonus)
        WHEN REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), 'លក់ស្លាកលេខ|លក់លេខ\b|plate\s*for\s*sale|plate\s*only')
         AND NOT REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), 'ឡាន|car|auto')
        THEN 1

        -- 4. Dedicated Rental Services (and NOT private cars with rental history disclaimers or Sorento)
        WHEN (
            REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), '\b(car\s*for\s*rent|rent\s*a\s*car|rental\s*service)\b|^ឡានជួល\b|^ជួលឡាន\b')
            OR (
                REGEXP_MATCHES(LOWER(CAST({{ desc_col }} AS VARCHAR)), '\b(car\s*for\s*rent|rent\s*a\s*car)\b')
                AND REGEXP_MATCHES(LOWER(CAST({{ desc_col }} AS VARCHAR)), '\b(\$\s*[0-9]+|\b[0-9]+\$)\s*(?:/|\bper\b)\s*(?:day|month|week|ថ្ងៃ|ខែ)\b')
                AND NOT REGEXP_MATCHES(LOWER(CAST({{ desc_col }} AS VARCHAR)), 'មិនធ្លាប់ជួល|គ្មានប្រវត្តិជួល|មិនដែលជួល|មិនជួល')
            )
        )
        THEN 1

        ELSE 0
    END
{% endmacro %}


-- 6. Disguised Financing Down Payment Detection
-- Identifies low-price ($500 - $3,000) listings for modern cars (2005+) where price represents down payment.
{% macro detect_down_payment(price_col, year_col, title_col, desc_col) %}
    CASE
        WHEN {{ price_col }} < 3000
          AND {{ year_col }} >= 2005
          AND REGEXP_MATCHES(
              LOWER(COALESCE(CAST({{ title_col }} AS VARCHAR), '') || ' ' || COALESCE(CAST({{ desc_col }} AS VARCHAR), '')),
              'បង់មុន|រំលស់សុទ្ធ|រំលស់|បង់\s*[0-9]+\$|/ខែ|down\s*payment|installment'
          ) THEN 1
        ELSE 0
    END
{% endmacro %}


-- 7. Automotive Market Brand Tier Classification
{% macro classify_brand_tier(brand_col) %}
    CASE
        WHEN {{ brand_col }} IN (
            'Lexus', 'Mercedes-Benz', 'BMW', 'Porsche', 'Land Rover',
            'Audi', 'Cadillac', 'Rolls-Royce', 'Bentley', 'Maserati',
            'Lamborghini', 'Ferrari', 'Aston Martin', 'Genesis', 'Volvo'
        ) THEN 'Luxury'
        WHEN {{ brand_col }} IN (
            'BYD', 'MG', 'Geely', 'Haval', 'GAC', 'Jetour', 'Changan',
            'Denza', 'Xpeng', 'NIO', 'Li Auto', 'Zeekr', 'Chery', 'Hongqi', 'Tank',
            'AVATR', 'Aion', 'Deepal', 'iCar', 'Leapmotor', 'GTV', 'Bestune'
        ) THEN 'Chinese_EV'
        WHEN {{ brand_col }} IN (
            'Toyota', 'Ford', 'Hyundai', 'Mazda', 'Kia',
            'Honda', 'Mitsubishi', 'Nissan', 'Suzuki', 'Isuzu',
            'Subaru', 'Chevrolet', 'Volkswagen', 'Jeep', 'Peugeot'
        ) THEN 'Mass_Market'
        ELSE 'Other'
    END
{% endmacro %}


-- 8. NLP Option Signals (full option & urgent sale flags)
{% macro extract_nlp_signals(title_col) %}
    CASE
        WHEN REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), 'full\s*option|option\s*[34]|f[\-\s]*sport')
             OR CAST({{ title_col }} AS VARCHAR) LIKE '%ហ្វូល%'
             OR CAST({{ title_col }} AS VARCHAR) LIKE '%អប់សិនពេញ%'
        THEN 1 ELSE 0
    END AS has_full_option,

    CASE
        WHEN REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), 'urgent|negotiable|below\s*market')
             OR CAST({{ title_col }} AS VARCHAR) LIKE '%លក់ប្រញាប់%'
             OR CAST({{ title_col }} AS VARCHAR) LIKE '%ធូរថ្លៃ%'
             OR CAST({{ title_col }} AS VARCHAR) LIKE '%ចរចា%'
             OR CAST({{ title_col }} AS VARCHAR) LIKE '%ចចារ%'
        THEN 1 ELSE 0
    END AS is_urgent_sale
{% endmacro %}
