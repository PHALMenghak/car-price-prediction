-- dbt/macros/quality/detect_spam.sql
-- Non-Vehicle / Accessory / Spam Detection.
-- Identifies spare tires, wheels, grilles, license plates, rentals, and non-car ads.
-- Strictly avoids false positives on Khmer manual transmission ('ឡានលក់លេខដៃ').

{% macro detect_non_vehicle_spam(title_col, desc_col, price_col) %}
    CASE
        -- 1. Standalone Auto Accessories / Body Parts (Grilles, Spare Tires, Bumpers, LPG kits)
        WHEN (
            REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), '^(?:ប៉ាណាលេង|គ្រឿងបន្លាស់|កង់សាគួ)|លក់កង់សាគួ|លក់គ្រឿងបន្លាស់|លក់កាង|លក់ហ្គាស|លកហ្គាដ|bodykit\s*only')
            OR (
                REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), 'ប៉ាណាលេង|កង់សាគួ|spare\s*tire')
                AND ({{ price_col }} IS NULL OR {{ price_col }} < 3000)
            )
        ) THEN 1

        -- 2. Non-Passenger Vehicles / Stolen Vehicle Reports / Community Alerts
        WHEN REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), '三轮|បោកឡាន|បាត់ឡាន|ជួយផ្សាយ') THEN 1

        -- 3. Standalone License Plate Sales (Safely protects cars with manual/auto transmission)
        WHEN REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), 'លក់(?:ស្លាក|ផ្លាក)លេខ(?:ឡាន)?|plate\s*for\s*sale|plate\s*only')
         AND NOT REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), 'លេខដៃ|លេខអូតូ|លេខកុងទ័រ') THEN 1

        -- 4. Dedicated Rental Services (and NOT private cars with rental history disclaimers or Sorento)
        WHEN (
            REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), '\b(car\s*for\s*rent|rent\s*a\s*car|rental\s*service)\b|^ឡានជួល\b|^ជួលឡាន\b')
            OR (
                REGEXP_MATCHES(LOWER(CAST({{ desc_col }} AS VARCHAR)), '\b(car\s*for\s*rent|rent\s*a\s*car)\b')
                AND REGEXP_MATCHES(LOWER(CAST({{ desc_col }} AS VARCHAR)), '\b(\$\s*[0-9]+|[0-9]+\$)\s*(?:/|\bper\b)\s*(?:day|month|week|ថ្ងៃ|ខែ)\b')
                AND NOT REGEXP_MATCHES(LOWER(CAST({{ desc_col }} AS VARCHAR)), 'មិនធ្លាប់ជួល|គ្មានប្រវត្តិជួល|មិនដែលជួល|មិនជួល')
            )
        ) THEN 1

        ELSE 0
    END
{% endmacro %}
