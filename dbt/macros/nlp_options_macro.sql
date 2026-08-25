-- dbt/macros/nlp_options_macro.sql
-- Extracts binary feature signals from free-text listing titles using regex.
-- Supports both English and Khmer (Unicode) keyword patterns.
-- Usage in models: {{ extract_title_options('listing_title') }}

{% macro extract_title_options(title_col) %}
    -- Full option package indicator (e.g. "full option", "option 3", "F-Sport", "ហ្វូល")
    CASE
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'full\s*option|option\s*[34]|f[\-\s]*sport')
             OR {{ title_col }} LIKE '%ហ្វូល%'
             OR {{ title_col }} LIKE '%អប់សិនពេញ%'
        THEN 1 ELSE 0
    END AS has_full_option,

    -- Urgent / negotiable seller signal (includes Khmer: លក់ប្រញាប់, ធូរថ្លៃ, ចរចា)
    CASE
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'urgent|negotiable|below\s*market')
             OR {{ title_col }} LIKE '%លក់ប្រញាប់%'
             OR {{ title_col }} LIKE '%ធូរថ្លៃ%'
             OR {{ title_col }} LIKE '%ចរចា%'
             OR {{ title_col }} LIKE '%ចចារ%'
        THEN 1 ELSE 0
    END AS is_urgent_sale
{% endmacro %}

{% macro extract_color_from_title(title_col) %}
    CASE
        WHEN (REGEXP_MATCHES(LOWER({{ title_col }}), 'white|ពណ៍ស|ពណ៌ស') OR {{ title_col }} LIKE '%ពណ៌ស%' OR {{ title_col }} LIKE '%ពណ៍ស%')
             AND NOT REGEXP_MATCHES(LOWER({{ title_col }}), 'កៅអី|ពូក') THEN 'White'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'black|ពណ៍ខ្មៅ|ពណ៌ខ្មៅ|ខ្មៅ') THEN 'Black'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'silver|ទឹកប្រាក់|ពណ៍ប្រាក់|ពណ៌ប្រាក់') THEN 'Silver'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'grey|gray|កណ្ដុរប្រមេះ|កណ្តុរប្រមេះ|ប្រផេះ') THEN 'Grey'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'gold|ទឹកមាស|ពណ៍មាស|ពណ៌មាស') THEN 'Gold'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'red|ក្រហម') THEN 'Red'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'blue|ខៀវ') THEN 'Blue'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'yellow|លឿង') THEN 'Yellow'
        ELSE 'Unknown'
    END
{% endmacro %}

{% macro infer_fuel_type(brand_col, model_col, title_col, raw_fuel_col) %}
    CASE
        WHEN LOWER({{ raw_fuel_col }}) IN ('gasoline', 'petrol', 'gas') THEN 'Petrol'
        WHEN LOWER({{ raw_fuel_col }}) = 'diesel' THEN 'Diesel'
        WHEN LOWER({{ raw_fuel_col }}) IN ('hybrid', 'plug-in hybrid', 'phev') THEN 'Hybrid'
        WHEN LOWER({{ raw_fuel_col }}) IN ('electric', 'ev') THEN 'Electric'
        WHEN {{ raw_fuel_col }} IS NOT NULL AND {{ raw_fuel_col }} IN ('Petrol', 'Diesel', 'Hybrid', 'Electric') THEN {{ raw_fuel_col }}
        WHEN {{ brand_col }} IN ('BYD', 'Avatr', 'Xpeng', 'NIO', 'Zeekr', 'Deepal', 'Arcfox', 'VinFast', 'Tesla', 'iCar')
             OR REGEXP_MATCHES(LOWER({{ title_col }}), '\bev\b|electric|អគ្គិសនី') THEN 'Electric'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'hybrid')
             OR LOWER({{ model_col }}) IN ('prius', 'aqua', 'camry hybrid', 'ct200h', 'rx450h', 'nx300h', 'es300h', 'bz4x') THEN 'Hybrid'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'diesel|ម៉ាស៊ូត')
             OR LOWER({{ model_col }}) IN ('hilux', 'hilux revo', 'hilux vigo', 'ranger', 'ranger raptor', 'ranger wildtrak', 'd-max', 'navara', 'grand starex') THEN 'Diesel'
        WHEN {{ brand_col }} != 'Unknown' OR {{ model_col }} != 'Unknown' THEN 'Petrol'
        ELSE 'Unknown'
    END
{% endmacro %}

{% macro infer_transmission(title_col, raw_trans_col) %}
    CASE
        WHEN LOWER({{ raw_trans_col }}) IN ('manual', 'លេខដៃ', 'លេខកំប៉ុក') THEN 'Manual'
        WHEN LOWER({{ raw_trans_col }}) IN ('automatic', 'auto', 'លេខអូតូ', 'អូតូ') THEN 'Automatic'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'manual|លេខដៃ|លេខកំប៉ុក') THEN 'Manual'
        WHEN REGEXP_MATCHES(LOWER({{ title_col }}), 'auto|លេខអូតូ|អូតូ') THEN 'Automatic'
        ELSE 'Automatic'
    END
{% endmacro %}

