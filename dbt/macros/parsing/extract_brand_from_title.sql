-- dbt/macros/parsing/extract_brand_from_title.sql
-- Multi-brand regex extractor for listing titles (Khmer, English, Chinese).
-- Extracts canonical brand name from sanitized title text as fallback for unmapped/other brands.

{% macro extract_brand_from_title(title_col) %}
    CASE
        WHEN {{ title_col }} ILIKE '%toyota%' OR {{ title_col }} ILIKE '%តូយ៉ូតា%' THEN 'Toyota'
        WHEN {{ title_col }} ILIKE '%lexus%' OR {{ title_col }} ILIKE '%ឡិចស៊ីស%' THEN 'Lexus'
        WHEN {{ title_col }} ILIKE '%mercedes%' OR {{ title_col }} ILIKE '%benz%' OR {{ title_col }} ILIKE '%ប៊េន%' THEN 'Mercedes-Benz'
        WHEN {{ title_col }} ILIKE '%bmw%' OR {{ title_col }} ILIKE '%ប៊ីអឹម%' THEN 'BMW'
        WHEN {{ title_col }} ILIKE '%ford%' OR {{ title_col }} ILIKE '%ហ្វត%' THEN 'Ford'
        WHEN {{ title_col }} ILIKE '%hyundai%' OR {{ title_col }} ILIKE '%ហ៊ីយ៉ាន់ដាយ%' THEN 'Hyundai'
        WHEN {{ title_col }} ILIKE '%kia%' OR {{ title_col }} ILIKE '%គីអា%' THEN 'Kia'
        WHEN {{ title_col }} ILIKE '%mazda%' OR {{ title_col }} ILIKE '%ម៉ាសដា%' THEN 'Mazda'
        WHEN {{ title_col }} ILIKE '%mitsubishi%' OR {{ title_col }} ILIKE '%មីស៊ូប៊ីស៊ី%' THEN 'Mitsubishi'
        WHEN {{ title_col }} ILIKE '%nissan%' OR {{ title_col }} ILIKE '%នីសាន់%' THEN 'Nissan'
        WHEN {{ title_col }} ILIKE '%honda%' THEN 'Honda'
        WHEN {{ title_col }} ILIKE '%byd%' OR {{ title_col }} ILIKE '%ប៊ីវ៉ាយឌី%' THEN 'BYD'
        WHEN {{ title_col }} ILIKE '%avatr%' OR {{ title_col }} ILIKE '%អាវ៉ាតា%' THEN 'AVATR'
        WHEN {{ title_col }} ILIKE '%aion%' THEN 'Aion'
        WHEN {{ title_col }} ILIKE '%deepal%' THEN 'Deepal'
        WHEN {{ title_col }} ILIKE '%xiaomi%' THEN 'Xiaomi'
        WHEN {{ title_col }} ILIKE '%icar%' OR {{ title_col }} ILIKE '%i car%' THEN 'iCar'
        WHEN {{ title_col }} ILIKE '%mg%' THEN 'MG'
        WHEN {{ title_col }} ILIKE '%geely%' OR {{ title_col }} ILIKE '%ជីលី%' THEN 'Geely'
        WHEN {{ title_col }} ILIKE '%rolls-royce%' OR {{ title_col }} ILIKE '%rolls royce%' THEN 'Rolls-Royce'
        WHEN {{ title_col }} ILIKE '%land rover%' OR {{ title_col }} ILIKE '%range rover%' THEN 'Land Rover'
        WHEN {{ title_col }} ILIKE '%porsche%' THEN 'Porsche'
        WHEN {{ title_col }} ILIKE '%cadillac%' THEN 'Cadillac'
        WHEN {{ title_col }} ILIKE '%audi%' THEN 'Audi'
        WHEN {{ title_col }} ILIKE '%jeep%' THEN 'Jeep'
        WHEN {{ title_col }} ILIKE '%volkswagen%' OR {{ title_col }} ILIKE '%vw%' THEN 'Volkswagen'
        WHEN {{ title_col }} ILIKE '%suzuki%' THEN 'Suzuki'
        WHEN {{ title_col }} ILIKE '%isuzu%' THEN 'Isuzu'
        WHEN {{ title_col }} ILIKE '%subaru%' THEN 'Subaru'
        WHEN {{ title_col }} ILIKE '%chevrolet%' OR {{ title_col }} ILIKE '%chevy%' THEN 'Chevrolet'
        WHEN {{ title_col }} ILIKE '%tesla%' THEN 'Tesla'
        ELSE NULL
    END
{% endmacro %}
