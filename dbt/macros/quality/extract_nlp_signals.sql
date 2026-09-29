-- dbt/macros/quality/extract_nlp_signals.sql
-- NLP Option Signals (full option & urgent sale flags).

{% macro extract_nlp_signals(title_col) %}
    CASE
        WHEN REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), 'full\s*option|option\s*[34]|f[\-\s]*sport')
             OR CAST({{ title_col }} AS VARCHAR) LIKE '%ហ្វូល%'
             OR CAST({{ title_col }} AS VARCHAR) LIKE '%អប់សិនពេញ%'
        THEN 1 ELSE 0
    END AS has_full_option
{% endmacro %}
