-- dbt/macros/parsing/parse_mileage.sql
-- Multi-source mileage parsing (returns integer km or NULL).
-- Inspects raw spec column first, then extracts from precleaned title/desc text.
-- Distinguishes Khmer miles (មុឺនម៉ាយ) vs kilometers (មុឺនគីឡូ/km).
-- Prevents mistaking model years or EV battery ranges for odometer distance.

{% macro parse_mileage(raw_mileage_col, text_col, year_col, fuel_col) %}
    CASE
        -- 1. Structured spec if valid numeric range
        WHEN {{ raw_mileage_col }} IS NOT NULL
         AND REGEXP_MATCHES(TRIM(CAST({{ raw_mileage_col }} AS VARCHAR)), '^[0-9]+(\.[0-9]+)?$')
         AND TRY_CAST(REGEXP_REPLACE(TRIM(CAST({{ raw_mileage_col }} AS VARCHAR)), '\..*', '') AS BIGINT) BETWEEN 0 AND 500000
            THEN TRY_CAST(REGEXP_REPLACE(TRIM(CAST({{ raw_mileage_col }} AS VARCHAR)), '\..*', '') AS BIGINT)

        -- 2. Khmer miles: X ម៉ឺនម៉ាយ (val * 10,000 * 1.60934)
        WHEN REGEXP_MATCHES({{ text_col }}, '([0-9]+(?:\.[0-9]+)?)\s*(?:មុឺន|ម៉ឺន)\s*(?:ម៉ាយ|miles?|mile)\b')
            THEN TRY_CAST(ROUND(TRY_CAST(REGEXP_EXTRACT({{ text_col }}, '([0-9]+(?:\.[0-9]+)?)\s*(?:មុឺន|ម៉ឺន)\s*(?:ម៉ាយ|miles?|mile)\b', 1) AS DOUBLE) * 10000.0 * 1.60934) AS BIGINT)

        -- 3. Khmer km: X ម៉ឺនគីឡូ (val * 10,000)
        WHEN REGEXP_MATCHES({{ text_col }}, '([0-9]+(?:\.[0-9]+)?)\s*(?:មុឺន|ម៉ឺន)\s*(?:គីឡូ(?:ម៉ែត្រ)?|km|kms)\b')
            THEN TRY_CAST(ROUND(TRY_CAST(REGEXP_EXTRACT({{ text_col }}, '([0-9]+(?:\.[0-9]+)?)\s*(?:មុឺន|ម៉ឺន)\s*(?:គីឡូ(?:ម៉ែត្រ)?|km|kms)\b', 1) AS DOUBLE) * 10000.0) AS BIGINT)

        -- 4. English miles with unit: X miles (val * 1.60934)
        WHEN REGEXP_MATCHES({{ text_col }}, '\b([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{2,6})\s*(?:miles?|mile)\b')
            THEN TRY_CAST(ROUND(TRY_CAST(REGEXP_REPLACE(REGEXP_EXTRACT({{ text_col }}, '\b([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{2,6})\s*(?:miles?|mile)\b', 1), ',', '', 'g') AS DOUBLE) * 1.60934) AS BIGINT)

        -- 5. Explicit odometer with tight proximity (max 10 chars between keyword and digits, mandatory unit, year defense)
        WHEN REGEXP_MATCHES({{ text_col }}, '(?i)(?:ជិះបាន|ប្រើបាន|odo|km\s*zin|mileage)[^0-9\n]{0,10}([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{3,6})\s*(?:km|kms|គីឡូ(?:ម៉ែត្រ)?)\b')
         AND TRY_CAST(REGEXP_REPLACE(REGEXP_EXTRACT({{ text_col }}, '(?i)(?:ជិះបាន|ប្រើបាន|odo|km\s*zin|mileage)[^0-9\n]{0,10}([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{3,6})\s*(?:km|kms|គីឡូ(?:ម៉ែត្រ)?)\b', 1), ',', '', 'g') AS BIGINT) != COALESCE({{ year_col }}, 0)
            THEN TRY_CAST(REGEXP_REPLACE(REGEXP_EXTRACT({{ text_col }}, '(?i)(?:ជិះបាន|ប្រើបាន|odo|km\s*zin|mileage)[^0-9\n]{0,10}([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{3,6})\s*(?:km|kms|គីឡូ(?:ម៉ែត្រ)?)\b', 1), ',', '', 'g') AS BIGINT)

        -- 6. Direct km (>= 1,500 km, and not pure EV without explicit odo keyword)
        WHEN REGEXP_MATCHES({{ text_col }}, '\b([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,6})\s*(?:km|kms|គីឡូ(?:ម៉ែត្រ)?)\b')
         AND (
             LOWER(COALESCE(CAST({{ fuel_col }} AS VARCHAR), '')) NOT IN ('electric', 'អគ្គិសនី', 'ev')
             OR REGEXP_MATCHES({{ text_col }}, '(?i)(?:ជិះបាន|ប្រើបាន|odo|km\s*zin|mileage)')
         )
         AND TRY_CAST(REGEXP_REPLACE(REGEXP_EXTRACT({{ text_col }}, '\b([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,6})\s*(?:km|kms|គីឡូ(?:ម៉ែត្រ)?)\b', 1), ',', '', 'g') AS BIGINT) != COALESCE({{ year_col }}, 0)
            THEN TRY_CAST(REGEXP_REPLACE(REGEXP_EXTRACT({{ text_col }}, '\b([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,6})\s*(?:km|kms|គីឡូ(?:ម៉ែត្រ)?)\b', 1), ',', '', 'g') AS BIGINT)

        ELSE NULL
    END
{% endmacro %}
