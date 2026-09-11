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
                                    REPLACE(
                                        REPLACE(
                                            REPLACE(
                                                COALESCE(CAST({{ col }} AS VARCHAR), ''),
                                                chr(8203), ''
                                            ),
                                            chr(8205), ''
                                        ),
                                        chr(65279), ''
                                    ),
                                    '&amp;', '&'
                                ),
                                '&#39;', ''''
                            ),
                            '&apos;', ''''
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
    {% set target_text = "REGEXP_REPLACE(LOWER(COALESCE(CAST(" ~ title_col ~ " AS VARCHAR), '') || ' ' || COALESCE(CAST(" ~ desc_col ~ " AS VARCHAR), '')), '(?:ការ)?(?:ធានា|warranty|រោងចក្រ)[^\\n.,;!?:]{0,60}?(?:(?:[0-9]+(?:\\.[0-9]+)?\\s*(?:មុឺន|ម៉ឺន)\\s*(?:គីឡូ(?:ម៉ែត្រ)?|km|kms)?)|(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,6})\\s*(?:km|kms|គីឡូ(?:ម៉ែត្រ)?))', ' ', 'g')" %}
    CASE
        -- 1. Structured spec if valid number
        WHEN {{ raw_mileage_col }} IS NOT NULL
          AND REGEXP_MATCHES(TRIM(CAST({{ raw_mileage_col }} AS VARCHAR)), '^[0-9]+(\.[0-9]+)?$')
          AND TRY_CAST(REGEXP_REPLACE(TRIM(CAST({{ raw_mileage_col }} AS VARCHAR)), '\..*', '') AS BIGINT) BETWEEN 0 AND 500000
            THEN TRY_CAST(REGEXP_REPLACE(TRIM(CAST({{ raw_mileage_col }} AS VARCHAR)), '\..*', '') AS BIGINT)

        -- 2. Khmer miles in Title/Desc: Xមុឺនម៉ាយ / Xម៉ឺនMiles / Xម៉ឺនម៉ាយ (val * 10,000 * 1.60934)
        WHEN REGEXP_MATCHES({{ target_text }}, '([0-9]+(?:\.[0-9]+)?)\s*(?:មុឺន|ម៉ឺន)\s*(?:ម៉ាយ|miles?|mile)')
            THEN TRY_CAST(ROUND(
                TRY_CAST(REGEXP_EXTRACT({{ target_text }}, '([0-9]+(?:\.[0-9]+)?)\s*(?:មុឺន|ម៉ឺន)\s*(?:ម៉ាយ|miles?|mile)', 1) AS DOUBLE)
                * 10000.0 * 1.60934
            ) AS BIGINT)

        -- 3. Khmer km in Title/Desc: Xមុឺនគីឡូ / Xម៉ឺនគីឡូ (val * 10,000)
        WHEN REGEXP_MATCHES({{ target_text }}, '([0-9]+(?:\.[0-9]+)?)\s*(?:មុឺន|ម៉ឺន)\s*(?:គីឡូ(?:ម៉ែត្រ)?|km|kms)')
            THEN TRY_CAST(ROUND(
                TRY_CAST(REGEXP_EXTRACT({{ target_text }}, '([0-9]+(?:\.[0-9]+)?)\s*(?:មុឺន|ម៉ឺន)\s*(?:គីឡូ(?:ម៉ែត្រ)?|km|kms)', 1) AS DOUBLE)
                * 10000.0
            ) AS BIGINT)

        -- 4. English miles with unit: X miles (val * 1.60934)
        WHEN REGEXP_MATCHES({{ target_text }}, '\b([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{2,6})\s*(?:miles?|mile)\b')
            THEN TRY_CAST(ROUND(
                TRY_CAST(REGEXP_REPLACE(REGEXP_EXTRACT({{ target_text }}, '\b([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{2,6})\s*(?:miles?|mile)\b', 1), ',', '', 'g') AS DOUBLE)
                * 1.60934
            ) AS BIGINT)

        -- 5. Explicit odometer km (avoiding EV range by checking context or requiring > 1000 km or odometer keywords)
        WHEN REGEXP_MATCHES({{ target_text }}, '(?:ជិះបាន|ប្រើបាន|odo|km\s*zin|mileage)[^0-9]*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{3,6})\s*(?:km|គីឡូ)?')
            THEN TRY_CAST(REGEXP_REPLACE(REGEXP_EXTRACT({{ target_text }}, '(?:ជិះបាន|ប្រើបាន|odo|km\s*zin|mileage)[^0-9]*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{3,6})\s*(?:km|គីឡូ)?', 1), ',', '', 'g') AS BIGINT)

        -- 6. Direct km (>= 1,500 km, and not pure EV without explicit odo keyword)
        WHEN REGEXP_MATCHES({{ target_text }}, '\b([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,6})\s*(?:km|kms|គីឡូ(?:ម៉ែត្រ)?)\b')
         AND (
             LOWER(COALESCE(CAST({{ fuel_col }} AS VARCHAR), '')) NOT IN ('electric', 'អគ្គិសនី', 'ev')
             OR REGEXP_MATCHES({{ target_text }}, '(?:ជិះបាន|ប្រើបាន|odo|km\s*zin|mileage)')
         )
            THEN TRY_CAST(REGEXP_REPLACE(REGEXP_EXTRACT({{ target_text }}, '\b([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,6})\s*(?:km|kms|គីឡូ(?:ម៉ែត្រ)?)\b', 1), ',', '', 'g') AS BIGINT)

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
          OR (
              {{ brand_col }} IN ('Tesla', 'NIO', 'Zeekr', 'Polestar', 'Rivian', 'Lucid', 'Xiaomi')
              AND COALESCE({{ fuel_col }}, '') NOT IN ('Hybrid', 'Petrol', 'Diesel')
          )
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
              OR (
                  LOWER(COALESCE({{ model_col }}, '')) IN ('prius', 'rx330', 'rx300')
                  AND LOWER(CAST({{ title_col }} AS VARCHAR)) NOT LIKE '%2026%'
              )
              OR (
                  REGEXP_MATCHES(CAST({{ title_col }} AS VARCHAR), '(?i)\b(prius|rx330|rx300|camry)\b.*\b06\b')
                  AND CAST({{ title_col }} AS VARCHAR) NOT LIKE '%2026%'
              )
          )
            THEN 2006

        -- Evidence 2: Spec year 2027 for Prius / Gen 2 models / explicit '2007' or '07' in title
        WHEN TRY_CAST({{ raw_year_col }} AS INTEGER) = 2027
          AND (
              LOWER(CAST({{ title_col }} AS VARCHAR)) LIKE '%2007%'
              OR (
                  LOWER(COALESCE({{ model_col }}, '')) IN ('prius', 'rx330', 'rx300')
                  AND LOWER(CAST({{ title_col }} AS VARCHAR)) NOT LIKE '%2027%'
              )
              OR (
                  REGEXP_MATCHES(CAST({{ title_col }} AS VARCHAR), '(?i)\b(prius|rx330|rx300|camry)\b.*\b07\b')
                  AND CAST({{ title_col }} AS VARCHAR) NOT LIKE '%2027%'
              )
          )
            THEN 2007

        -- Evidence 3: Fallback standard 4-digit cast
        WHEN TRY_CAST({{ raw_year_col }} AS INTEGER) BETWEEN 1990 AND (CAST(date_part('year', CURRENT_DATE) AS INTEGER) + 1)
            THEN TRY_CAST({{ raw_year_col }} AS INTEGER)

        -- Evidence 4: Title 4-digit year fallback if raw_spec_year was null
        WHEN REGEXP_MATCHES(CAST({{ title_col }} AS VARCHAR), '\b(19[9][0-9]|20[0-2][0-9])\b')
            THEN TRY_CAST(REGEXP_EXTRACT(CAST({{ title_col }} AS VARCHAR), '\b(19[9][0-9]|20[0-2][0-9])\b', 1) AS INTEGER)

        -- Evidence 5: Title 2-digit year fallback for classic models when spec year is missing
        WHEN TRY_CAST({{ raw_year_col }} AS INTEGER) IS NULL
         AND REGEXP_MATCHES(CAST({{ title_col }} AS VARCHAR), '(?i)\b(?:prius|camry|corolla|highlander|rav4|cr-?v|rx300|rx330|vitz|morning)\s*0?([0-9])\b')
            THEN 2000 + TRY_CAST(REGEXP_EXTRACT(CAST({{ title_col }} AS VARCHAR), '(?i)\b(?:prius|camry|corolla|highlander|rav4|cr-?v|rx300|rx330|vitz|morning)\s*0?([0-9])\b', 1) AS INTEGER)

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
            REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), '^(?:ប៉ាណាលេង|គ្រឿងបន្លាស់|កង់សាគួ)|លក់កង់សាគួ|លក់គ្រឿងបន្លាស់|លក់កាង|លក់ហ្គាស|លកហ្គាដ|bodykit\s*only')
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
        WHEN (
            REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), 'លក់ស្លាកលេខ|លក់លេខ|plate\s*for\s*sale|plate\s*only')
            AND (
                NOT REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), '\b(?:car|auto)\b')
                OR REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), 'លក់ស្លាកលេខឡាន|លក់លេខឡាន')
            )
        )
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
-- Identifies low-price ($500 - $3,000) listings where price represents down payment.
{% macro detect_down_payment(price_col, year_col, title_col, desc_col) %}
    CASE
        WHEN {{ price_col }} < 3000
          AND ({{ year_col }} >= 2005 OR {{ year_col }} IS NULL)
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
        WHEN LOWER(COALESCE(CAST({{ brand_col }} AS VARCHAR), '')) IN (
            'lexus', 'mercedes-benz', 'bmw', 'porsche', 'land rover',
            'audi', 'cadillac', 'rolls-royce', 'bentley', 'maserati',
            'lamborghini', 'ferrari', 'aston martin', 'genesis', 'volvo',
            'tesla', 'polestar', 'lucid', 'rivian', 'lincoln', 'mclaren'
        ) THEN 'Luxury'
        WHEN LOWER(COALESCE(CAST({{ brand_col }} AS VARCHAR), '')) IN (
            'byd', 'mg', 'geely', 'haval', 'gac', 'jetour', 'changan',
            'denza', 'xpeng', 'nio', 'li auto', 'zeekr', 'chery', 'hongqi', 'tank',
            'avatr', 'aion', 'deepal', 'icar', 'leapmotor', 'gtv', 'bestune',
            'xiaomi', 'aito', 'gwm', 'yangwang', 'ora', 'forthing', 'wuling', 'dfsk', 'kaiyi', 'baic'
        ) THEN 'Chinese_EV'
        WHEN LOWER(COALESCE(CAST({{ brand_col }} AS VARCHAR), '')) IN (
            'toyota', 'ford', 'hyundai', 'mazda', 'kia',
            'honda', 'mitsubishi', 'nissan', 'suzuki', 'isuzu',
            'subaru', 'chevrolet', 'volkswagen', 'jeep', 'peugeot',
            'ssangyong', 'mini', 'renault', 'fiat', 'ram'
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


-- 9. Domain-Grounded Price Outlier Detection
-- Protects legitimate high-end vehicles in Cambodia (Land Cruiser, Alphard, Palisade, Raptor, EV flagships)
-- Accurately identifies actual seller fat-finger typos (e.g. 2004 Highlander for $198,000 or 2014 Windstar for $237,777)
{% macro detect_price_outlier(price_col, brand_col, model_col, year_col) %}
    CASE
        -- Missing or non-positive prices are handled by schema and boundary rules
        WHEN {{ price_col }} IS NULL OR {{ price_col }} <= 0 THEN 0

        -- 1. True Verified Exotic Brands (Rolls-Royce, Bentley, Ferrari, Lamborghini, Maybach)
        -- In Cambodia, these legitimately reach $500,000 - $1,500,000+ due to 130%+ luxury taxes.
        WHEN LOWER(COALESCE(CAST({{ brand_col }} AS VARCHAR), '')) IN ('rolls-royce', 'bentley', 'ferrari', 'lamborghini', 'aston martin', 'mclaren')
             OR (LOWER(COALESCE(CAST({{ brand_col }} AS VARCHAR), '')) = 'mercedes-benz' AND LOWER(COALESCE(CAST({{ model_col }} AS VARCHAR), '')) = 'maybach')
            THEN CASE WHEN {{ price_col }} > 1500000 THEN 1 ELSE 0 END

        -- 2. Fat-Finger Typo Errors on Older Luxury Models (e.g. 2001 RX300 or 2004 C200 typo for $120k+)
        -- Checked BEFORE the general luxury ceiling to catch 10x typos on depreciated luxury cars
        WHEN LOWER(COALESCE(CAST({{ brand_col }} AS VARCHAR), '')) IN ('lexus', 'mercedes-benz', 'bmw')
             AND LOWER(COALESCE(CAST({{ model_col }} AS VARCHAR), '')) IN ('rx300', 'rx330', 'es300', 'es350', 'is250', 'c-class', '3 series', '5 series')
             AND {{ year_col }} < 2008 AND {{ price_col }} > 55000 THEN 1

        -- 3. Standard Luxury Brands (Lexus, Mercedes-Benz, BMW, Porsche, Land Rover, Cadillac, etc.)
        -- Top trims (LX600, Escalade, G-Class) legitimately reach $200,000 - $450,000 in Cambodia.
        WHEN LOWER(COALESCE(CAST({{ brand_col }} AS VARCHAR), '')) IN ('lexus', 'mercedes-benz', 'bmw', 'porsche', 'land rover', 'audi', 'cadillac', 'maserati', 'genesis', 'volvo', 'tesla')
            THEN CASE WHEN {{ price_col }} > 600000 THEN 1 ELSE 0 END

        -- 4. Verified Luxury / Flagship Models from Mass-Market & Tech EV Brands
        -- Genuine high-value vehicles ($60,000 - $300,000+): Land Cruiser, Prado, Alphard, Granvia, Palisade, Raptor, SU7, etc.
        WHEN (
            (LOWER(COALESCE(CAST({{ brand_col }} AS VARCHAR), '')) = 'toyota' AND LOWER(COALESCE(CAST({{ model_col }} AS VARCHAR), '')) IN ('land cruiser', 'land cruiser prado', 'alphard', 'vellfire', 'granvia', 'century', 'tundra', 'sequoia', 'gr supra', 'hiace', 'crown', 'grand highlander', 'hilux revo', 'hilux', 'tacoma', '4runner', 'fortuner'))
            OR (LOWER(COALESCE(CAST({{ brand_col }} AS VARCHAR), '')) = 'ford' AND LOWER(COALESCE(CAST({{ model_col }} AS VARCHAR), '')) IN ('f-150', 'f-150 raptor', 'ranger raptor', 'bronco', 'bronco sport', 'expedition'))
            OR (LOWER(COALESCE(CAST({{ brand_col }} AS VARCHAR), '')) = 'hyundai' AND LOWER(COALESCE(CAST({{ model_col }} AS VARCHAR), '')) IN ('palisade', 'santa fe', 'staria', 'county', 'equus'))
            OR (LOWER(COALESCE(CAST({{ brand_col }} AS VARCHAR), '')) = 'kia' AND LOWER(COALESCE(CAST({{ model_col }} AS VARCHAR), '')) IN ('carnival', 'ev6', 'ev9', 'mohave', 'stinger'))
            OR LOWER(COALESCE(CAST({{ brand_col }} AS VARCHAR), '')) IN ('xiaomi', 'zeekr', 'deepal', 'byd', 'tank', 'denza', 'li auto', 'nio', 'hongqi', 'gwm', 'yangwang', 'aito')
        ) THEN CASE WHEN {{ price_col }} > 350000 THEN 1 ELSE 0 END

        -- 5. Fat-Finger Typo Errors on Budget / Economy Models (older models where seller entered an extra 0)
        WHEN LOWER(COALESCE(CAST({{ model_col }} AS VARCHAR), '')) IN ('prius', 'corolla', 'camry', 'vitz', 'yaris', 'morning', 'ray', 'spark', 'windstar', 'ecosport', 'fit', 'march', 'mira', 'swift')
             AND {{ year_col }} < 2023 AND {{ price_col }} > 45000 THEN 1

        -- 6. Fat-Finger Typo Errors on Older Economy Family Crossovers (pre-2015 Highlander, CR-V, RAV4)
        WHEN LOWER(COALESCE(CAST({{ model_col }} AS VARCHAR), '')) IN ('highlander', 'cr-v', 'rav4', 'tucson', 'sportage', 'duster', 'x-trail')
             AND {{ year_col }} < 2015 AND {{ price_col }} > 50000 THEN 1

        -- 7. Fat-Finger Typo Errors on Compact EVs (e.g. 2018 Model 3 typo for $18,500)
        WHEN LOWER(COALESCE(CAST({{ brand_col }} AS VARCHAR), '')) = 'tesla' AND LOWER(COALESCE(CAST({{ model_col }} AS VARCHAR), '')) = 'model 3'
             AND {{ year_col }} < 2022 AND {{ price_col }} > 60000 THEN 1

        -- 8. Modern New/Near-New Vehicles (2020+) can legitimately cost up to $150,000 in Cambodia
        WHEN {{ year_col }} >= 2020 AND {{ price_col }} <= 150000 THEN 0

        -- 9. Older Mass-Market Vehicles (pre-2018) exceeding realistic market caps
        WHEN {{ year_col }} < 2018 AND {{ price_col }} > 75000 THEN 1

        -- 10. General Extreme Upper Bound for any remaining non-luxury vehicle
        WHEN {{ price_col }} > 300000 THEN 1

        ELSE 0
    END
{% endmacro %}
