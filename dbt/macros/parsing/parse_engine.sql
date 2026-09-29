-- dbt/macros/parsing/parse_engine.sql
-- Multi-Source Engine CC Parsing (returns integer cc or NULL).
-- Pure Electric Vehicles: Displacement is NOT applicable -> returns NULL (not 0 cc).
-- Parses decimal litres (e.g. 1.8L -> 1800cc) and explicit CC (e.g. 3500cc).

{% macro parse_engine_cc(raw_engine_col, text_col, fuel_col, brand_col) %}
    CASE
        -- 1. Pure Electric Vehicles: Displacement is NOT applicable (NULL, not 0 cc)
        WHEN {{ is_ev_vehicle(brand_col, fuel_col) }} THEN NULL

        -- 2. Structured raw engine spec in litres (e.g. '1.8L', '2.5 L')
        WHEN REGEXP_MATCHES(LOWER(TRIM(COALESCE(CAST({{ raw_engine_col }} AS VARCHAR), ''))), '^[0-9]\.[0-9]\s*l?$')
            THEN TRY_CAST(ROUND(TRY_CAST(REGEXP_REPLACE(LOWER(TRIM(CAST({{ raw_engine_col }} AS VARCHAR))), '[^0-9\.]', '', 'g') AS DOUBLE) * 1000.0) AS INTEGER)

        -- 3. Structured raw engine spec in CC (e.g. '1800', '2000cc')
        WHEN REGEXP_MATCHES(LOWER(TRIM(COALESCE(CAST({{ raw_engine_col }} AS VARCHAR), ''))), '^[0-9]{3,4}\s*(cc)?$')
            THEN TRY_CAST(REGEXP_REPLACE(LOWER(TRIM(CAST({{ raw_engine_col }} AS VARCHAR))), '[^0-9]', '', 'g') AS INTEGER)

        -- 4. Explicit litres in Title/Desc: 1.8L, 2.5L, 3.5 L
        WHEN REGEXP_MATCHES({{ text_col }}, '\b([1-6]\.[0-9])\s*(?:l|litre)\b')
            THEN TRY_CAST(ROUND(TRY_CAST(REGEXP_EXTRACT({{ text_col }}, '\b([1-6]\.[0-9])\s*(?:l|litre)\b', 1) AS DOUBLE) * 1000.0) AS INTEGER)

        -- 5. Khmer engine keyword: ម៉ាស៊ីន 1.8 / ម៉ាសុីន 2.5
        WHEN REGEXP_MATCHES({{ text_col }}, '(?:ម៉ាស៊ីន|ម៉ាសុីន|engine)\s*([1-6]\.[0-9])')
            THEN TRY_CAST(ROUND(TRY_CAST(REGEXP_EXTRACT({{ text_col }}, '(?:ម៉ាស៊ីន|ម៉ាសុីន|engine)\s*([1-6]\.[0-9])', 1) AS DOUBLE) * 1000.0) AS INTEGER)

        -- 6. Explicit CC in Title/Desc: 1800cc, 2000 cc, 3500cc (MUST have 'cc' suffix)
        WHEN REGEXP_MATCHES({{ text_col }}, '\b([1-6][0-9]{2,3})\s*cc\b')
            THEN TRY_CAST(REGEXP_EXTRACT({{ text_col }}, '\b([1-6][0-9]{2,3})\s*cc\b', 1) AS INTEGER)

        ELSE NULL
    END
{% endmacro %}
