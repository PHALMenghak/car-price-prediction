-- dbt/macros/quality/detect_down_payment.sql
-- Disguised Financing Down Payment Detection.
-- Identifies low-price ($500 - $3,000) listings where price represents down payment.
-- Protects generic dealer boilerplate ('មានសេវាបង់រំលស់').

{% macro detect_down_payment(price_col, year_col, text_or_title_col, desc_col=None) %}
{% if desc_col is not none %}
    {% set search_text = "LOWER(COALESCE(CAST(" ~ text_or_title_col ~ " AS VARCHAR), '') || ' ' || COALESCE(CAST(" ~ desc_col ~ " AS VARCHAR), ''))" %}
{% else %}
    {% set search_text = text_or_title_col %}
{% endif %}
    CASE
        WHEN {{ price_col }} < 3000
          AND ({{ year_col }} >= 2005 OR {{ year_col }} IS NULL)
          AND REGEXP_MATCHES(
              {{ search_text }},
              'បង់មុន\s*(?:ត្រឹម|តែ)?\s*[\$0-9]|រំលស់សុទ្ធ\s*100%|បង់\s*[0-9]+\$\s*(?:/|\bper\b)\s*ខែ|down\s*payment'
          ) THEN 1
        ELSE 0
    END
{% endmacro %}
