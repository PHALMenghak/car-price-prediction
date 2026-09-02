-- dbt/macros/clean_specs_macro.sql
-- Reusable SQL macros for parsing, cleaning, and normalizing raw physical specifications in DuckDB.

{% macro parse_raw_mileage(raw_mileage_col) %}
    CASE
        WHEN {{ raw_mileage_col }} IS NULL OR TRIM(CAST({{ raw_mileage_col }} AS VARCHAR)) IN ('', 'None', 'null', 'nan') THEN NULL
        ELSE
            TRY_CAST(
                REGEXP_REPLACE(
                    REGEXP_REPLACE(LOWER(TRIM(CAST({{ raw_mileage_col }} AS VARCHAR))), '[^0-9\.]', '', 'g'),
                    '\..*',
                    ''
                ) AS BIGINT
            )
    END
{% endmacro %}


{% macro parse_raw_engine_cc(raw_engine_col, title_col) %}
    CASE
        -- If raw engine spec is provided
        WHEN {{ raw_engine_col }} IS NOT NULL AND TRIM(CAST({{ raw_engine_col }} AS VARCHAR)) NOT IN ('', 'None', 'null', 'nan') THEN
            CASE
                -- Decimal litres format (e.g. '1.8L', '2.0', '3.5L', '1.8')
                WHEN REGEXP_MATCHES(TRIM(CAST({{ raw_engine_col }} AS VARCHAR)), '^[0-9]\.[0-9]') THEN
                    TRY_CAST(
                        ROUND(TRY_CAST(REGEXP_EXTRACT(TRIM(CAST({{ raw_engine_col }} AS VARCHAR)), '[0-9]\.[0-9]') AS DOUBLE) * 1000, 0)
                        AS INTEGER
                    )
                -- Direct CC format (e.g. '1800cc', '2000', '3500')
                ELSE
                    TRY_CAST(
                        REGEXP_REPLACE(TRIM(CAST({{ raw_engine_col }} AS VARCHAR)), '[^0-9]', '', 'g')
                        AS INTEGER
                    )
            END

        -- Fallback: extract engine displacement from listing title (e.g. '2.5L', '3.0L', '2.0t')
        WHEN REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), '\b([1-6]\.[0-9])\s*(l|litre|cc|t)?\b') THEN
            TRY_CAST(
                ROUND(
                    TRY_CAST(REGEXP_EXTRACT(LOWER(CAST({{ title_col }} AS VARCHAR)), '([1-6]\.[0-9])', 1) AS DOUBLE) * 1000,
                    0
                ) AS INTEGER
            )
        ELSE NULL
    END
{% endmacro %}


{% macro normalize_raw_color(raw_color_col, title_col) %}
    CASE
        -- Check raw_color_col first
        WHEN {{ raw_color_col }} IS NOT NULL AND TRIM(CAST({{ raw_color_col }} AS VARCHAR)) NOT IN ('', 'Unknown', 'None', 'nan') THEN
            CASE
                WHEN REGEXP_MATCHES(LOWER(CAST({{ raw_color_col }} AS VARCHAR)), 'white|ស\b|ពណ៌ស|ពណ៍ស') THEN 'White'
                WHEN REGEXP_MATCHES(LOWER(CAST({{ raw_color_col }} AS VARCHAR)), 'black|ខ្មៅ|ពណ៌ខ្មៅ|ពណ៍ខ្មៅ') THEN 'Black'
                WHEN REGEXP_MATCHES(LOWER(CAST({{ raw_color_col }} AS VARCHAR)), 'silver|ទឹកប្រាក់|ប្រាក់|ពណ៌ប្រាក់') THEN 'Silver'
                WHEN REGEXP_MATCHES(LOWER(CAST({{ raw_color_col }} AS VARCHAR)), 'grey|gray|ប្រផេះ|កណ្ដុរប្រមេះ|កណ្តុរប្រមេះ') THEN 'Grey'
                WHEN REGEXP_MATCHES(LOWER(CAST({{ raw_color_col }} AS VARCHAR)), 'gold|ទឹកមាស|មាស|ពណ៌មាស') THEN 'Gold'
                WHEN REGEXP_MATCHES(LOWER(CAST({{ raw_color_col }} AS VARCHAR)), 'red|ក្រហម|ពណ៌ក្រហម') THEN 'Red'
                WHEN REGEXP_MATCHES(LOWER(CAST({{ raw_color_col }} AS VARCHAR)), 'blue|ខៀវ|ពណ៌ខៀវ') THEN 'Blue'
                WHEN REGEXP_MATCHES(LOWER(CAST({{ raw_color_col }} AS VARCHAR)), 'yellow|លឿង|ពណ៌លឿង') THEN 'Yellow'
                WHEN REGEXP_MATCHES(LOWER(CAST({{ raw_color_col }} AS VARCHAR)), 'brown|ត្នោត|ពណ៌ត្នោត') THEN 'Brown'
                WHEN REGEXP_MATCHES(LOWER(CAST({{ raw_color_col }} AS VARCHAR)), 'green|បៃតង|ពណ៌បៃតង') THEN 'Green'
                ELSE TRIM(CAST({{ raw_color_col }} AS VARCHAR))
            END

        -- Fallback to title keywords
        WHEN (REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), 'white|ពណ៍ស|ពណ៌ស') OR CAST({{ title_col }} AS VARCHAR) LIKE '%ពណ៌ស%' OR CAST({{ title_col }} AS VARCHAR) LIKE '%ពណ៍ស%')
             AND NOT REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), 'កៅអី|ពូក') THEN 'White'
        WHEN REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), 'black|ពណ៍ខ្មៅ|ពណ៌ខ្មៅ|ខ្មៅ') THEN 'Black'
        WHEN REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), 'silver|ទឹកប្រាក់|ពណ៍ប្រាក់|ពណ៌ប្រាក់') THEN 'Silver'
        WHEN REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), 'grey|gray|កណ្ដុរប្រមេះ|កណ្តុរប្រមេះ|ប្រផេះ') THEN 'Grey'
        WHEN REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), 'gold|ទឹកមាស|ពណ៍មាស|ពណ៌មាស') THEN 'Gold'
        WHEN REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), 'red|ក្រហម') THEN 'Red'
        WHEN REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), 'blue|ខៀវ') THEN 'Blue'
        WHEN REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), 'yellow|លឿង') THEN 'Yellow'
        ELSE 'Unknown'
    END
{% endmacro %}


{% macro normalize_raw_fuel_type(raw_fuel_col, title_col, brand_col, model_col) %}
    CASE
        -- Check raw fuel string
        WHEN {{ raw_fuel_col }} IS NOT NULL AND TRIM(CAST({{ raw_fuel_col }} AS VARCHAR)) NOT IN ('', 'Unknown', 'None', 'nan') THEN
            CASE
                WHEN REGEXP_MATCHES(LOWER(CAST({{ raw_fuel_col }} AS VARCHAR)), 'lpg|autogas|ហ្គាស') THEN 'LPG'
                WHEN REGEXP_MATCHES(LOWER(CAST({{ raw_fuel_col }} AS VARCHAR)), 'gasoline|petrol|gas|សាំង') THEN 'Petrol'
                WHEN REGEXP_MATCHES(LOWER(CAST({{ raw_fuel_col }} AS VARCHAR)), 'diesel|ម៉ាស៊ូត|ម៉ាស៊ុត') THEN 'Diesel'
                WHEN REGEXP_MATCHES(LOWER(CAST({{ raw_fuel_col }} AS VARCHAR)), 'hybrid|phev|plug-in|កូនកាត់') THEN 'Hybrid'
                WHEN REGEXP_MATCHES(LOWER(CAST({{ raw_fuel_col }} AS VARCHAR)), 'electric|ev\b|អគ្គិសនី') THEN 'Electric'
                ELSE TRIM(CAST({{ raw_fuel_col }} AS VARCHAR))
            END

        -- Check pure EV brands
        WHEN {{ brand_col }} IN ('BYD', 'AVATR', 'Xpeng', 'NIO', 'Zeekr', 'Deepal', 'Arcfox', 'VinFast', 'Tesla', 'iCar')
             OR REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), '\bev\b|electric|អគ្គិសនី') THEN 'Electric'

        -- Check known hybrid models
        WHEN REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), 'hybrid')
             OR LOWER(CAST({{ model_col }} AS VARCHAR)) IN ('prius', 'aqua', 'camry hybrid', 'ct200h', 'rx450h', 'nx300h', 'es300h', 'bz4x') THEN 'Hybrid'

        -- Check known diesel models
        WHEN REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), 'diesel|ម៉ាស៊ូត|ម៉ាស៊ុត')
             OR LOWER(CAST({{ model_col }} AS VARCHAR)) IN ('hilux', 'hilux revo', 'hilux vigo', 'ranger', 'ranger raptor', 'ranger wildtrak', 'd-max', 'navara', 'grand starex', 'starex') THEN 'Diesel'

        WHEN {{ brand_col }} != 'Unknown' OR {{ model_col }} != 'Unknown' THEN 'Petrol'
        ELSE 'Unknown'
    END
{% endmacro %}


{% macro normalize_raw_transmission(raw_trans_col, title_col) %}
    CASE
        WHEN {{ raw_trans_col }} IS NOT NULL AND TRIM(CAST({{ raw_trans_col }} AS VARCHAR)) NOT IN ('', 'Unknown', 'None', 'nan') THEN
            CASE
                WHEN REGEXP_MATCHES(LOWER(CAST({{ raw_trans_col }} AS VARCHAR)), 'manual|លេខដៃ|លេខកំប៉ុក') THEN 'Manual'
                WHEN REGEXP_MATCHES(LOWER(CAST({{ raw_trans_col }} AS VARCHAR)), 'automatic|auto|លេខអូតូ|អូតូ') THEN 'Automatic'
                ELSE 'Automatic'
            END
        WHEN REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), 'manual|លេខដៃ|លេខកំប៉ុក') THEN 'Manual'
        WHEN REGEXP_MATCHES(LOWER(CAST({{ title_col }} AS VARCHAR)), 'auto|លេខអូតូ|អូតូ') THEN 'Automatic'
        ELSE 'Automatic'
    END
{% endmacro %}


{% macro normalize_raw_tax_type(raw_tax_col) %}
    CASE
        WHEN {{ raw_tax_col }} IS NULL THEN 'Unknown'
        WHEN REGEXP_MATCHES(LOWER(CAST({{ raw_tax_col }} AS VARCHAR)), 'plate|ស្លាកលេខ') THEN 'Plate Number'
        WHEN REGEXP_MATCHES(LOWER(CAST({{ raw_tax_col }} AS VARCHAR)), 'paper|ក្រដាសពន្ធ|ពន្ធ') THEN 'Tax Paper'
        ELSE TRIM(CAST({{ raw_tax_col }} AS VARCHAR))
    END
{% endmacro %}


{% macro normalize_raw_condition(raw_cond_col) %}
    CASE
        WHEN {{ raw_cond_col }} IS NULL THEN 'used'
        WHEN REGEXP_MATCHES(LOWER(CAST({{ raw_cond_col }} AS VARCHAR)), 'new|ថ្មី') THEN 'new'
        WHEN REGEXP_MATCHES(LOWER(CAST({{ raw_cond_col }} AS VARCHAR)), 'used|ចាស់|ប្រើរួច') THEN 'used'
        ELSE 'used'
    END
{% endmacro %}
