-- dbt/macros/parsing/parse_year.sql
-- Evidence-Based Chronological Inversion Healing & Resolution.
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
          ) THEN 2006

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
          ) THEN 2007

        -- Evidence 3: Fallback standard 4-digit cast
        WHEN TRY_CAST({{ raw_year_col }} AS INTEGER) BETWEEN 1990 AND (CAST(date_part('year', CURRENT_DATE) AS INTEGER) + 1)
            THEN TRY_CAST({{ raw_year_col }} AS INTEGER)

        -- Evidence 4: Title 4-digit year fallback if raw_spec_year was null or out-of-bounds
        WHEN REGEXP_MATCHES(CAST({{ title_col }} AS VARCHAR), '\b(199[0-9]|20[0-2][0-9])\b')
            THEN TRY_CAST(REGEXP_EXTRACT(CAST({{ title_col }} AS VARCHAR), '\b(199[0-9]|20[0-2][0-9])\b', 1) AS INTEGER)

        -- Evidence 5: Title 2-digit year fallback for classic models when spec year is missing
        WHEN TRY_CAST({{ raw_year_col }} AS INTEGER) IS NULL
         AND REGEXP_MATCHES(CAST({{ title_col }} AS VARCHAR), '(?i)\b(?:prius|camry|corolla|highlander|rav4|cr-?v|rx300|rx330|vitz|morning)\s*0([0-9])\b')
            THEN 2000 + TRY_CAST(REGEXP_EXTRACT(CAST({{ title_col }} AS VARCHAR), '(?i)\b(?:prius|camry|corolla|highlander|rav4|cr-?v|rx300|rx330|vitz|morning)\s*0([0-9])\b', 1) AS INTEGER)

        ELSE NULL
    END
{% endmacro %}
