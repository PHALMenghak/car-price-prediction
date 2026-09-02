-- dbt/macros/nlp_options_macro.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- NLP Option Extraction Macro
-- ─────────────────────────────────────────────────────────────────────────────
-- Extracts binary feature signals from free-text listing titles using regex.
-- Supports both English and Khmer (Unicode) keyword patterns.
-- Usage in models: {{ extract_title_options('listing_title') }}

{% macro extract_title_options(title_col) %}
    -- Full option package indicator (e.g. "full option", "option 3", "F-Sport", "ហ្វូល")
    CASE
        WHEN REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), 'full\s*option|option\s*[34]|f[\-\s]*sport')
             OR CAST({{ title_col }} AS VARCHAR) LIKE '%ហ្វូល%'
             OR CAST({{ title_col }} AS VARCHAR) LIKE '%អប់សិនពេញ%'
        THEN 1 ELSE 0
    END AS has_full_option,

    -- Urgent / negotiable seller signal (includes Khmer: លក់ប្រញាប់, ធូរថ្លៃ, ចរចា)
    CASE
        WHEN REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), 'urgent|negotiable|below\s*market')
             OR CAST({{ title_col }} AS VARCHAR) LIKE '%លក់ប្រញាប់%'
             OR CAST({{ title_col }} AS VARCHAR) LIKE '%ធូរថ្លៃ%'
             OR CAST({{ title_col }} AS VARCHAR) LIKE '%ចរចា%'
             OR CAST({{ title_col }} AS VARCHAR) LIKE '%ចចារ%'
        THEN 1 ELSE 0
    END AS is_urgent_sale
{% endmacro %}
