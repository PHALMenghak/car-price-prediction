-- dbt/macros/nlp_options_macro.sql
-- Extracts binary feature signals from free-text listing titles using regex.
-- Supports both English and Khmer (Unicode) keyword patterns.
-- Usage in models: {{ extract_title_options('listing_title') }}

{% macro extract_title_options(title_col) %}
    -- Full option package indicator (e.g. "full option", "option 3", "F-Sport")
    CASE
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'full\s*option|option\s*[34]|f[\-\s]*sport')
        THEN 1 ELSE 0
    END AS has_full_option,

    -- Sunroof / Moonroof indicator (includes Khmer: បើកដំបូល)
    CASE
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'solar|sunroof|moonroof|open\s*roof')
             OR {{ title_col }} LIKE '%បើកដំបូល%'
        THEN 1 ELSE 0
    END AS has_sunroof,

    -- Leather seat indicator (includes Khmer: ពូកស្បែក)
    CASE
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'leather|seat\s*leather')
             OR {{ title_col }} LIKE '%ពូកស្បែក%'
        THEN 1 ELSE 0
    END AS has_leather,

    -- Camera / Safety sensor indicator
    CASE
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'camera|sensor|360|reverse\s*cam')
        THEN 1 ELSE 0
    END AS has_camera,

    -- Urgent / negotiable seller signal (includes Khmer: លក់ប្រញាប់, ធូរថ្លៃ, ចរចា)
    CASE
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'urgent|negotiable')
             OR {{ title_col }} LIKE '%លក់ប្រញាប់%'
             OR {{ title_col }} LIKE '%ធូរថ្លៃ%'
             OR {{ title_col }} LIKE '%ចរចា%'
        THEN 1 ELSE 0
    END AS is_urgent_sale
{% endmacro %}
