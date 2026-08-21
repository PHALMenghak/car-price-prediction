-- dbt/macros/brand_tier_macro.sql
-- Classifies vehicle brands into Cambodia automotive market tiers.
-- Usage in models: {{ classify_brand_tier('vehicle_brand') }}

{% macro classify_brand_tier(brand_col) %}
    CASE
        WHEN {{ brand_col }} IN (
            'Lexus', 'Mercedes-Benz', 'BMW', 'Porsche', 'Land Rover',
            'Audi', 'Cadillac', 'Rolls-Royce', 'Bentley', 'Maserati',
            'Lamborghini', 'Ferrari', 'Aston Martin', 'Genesis', 'Volvo'
        ) THEN 'Luxury'
        WHEN {{ brand_col }} IN (
            'BYD', 'MG', 'Geely', 'Haval', 'GAC', 'Jetour', 'Changan',
            'Denza', 'Fangchengbao', 'Xpeng', 'NIO', 'Li Auto', 'Zeekr',
            'Avatr', 'iCar', 'Chery', 'GTV', 'ZNA', 'Arcfox', 'Hongqi',
            'Tank', 'Dongfeng', 'BAIC', 'Wuling', 'Foton', 'DFSK',
            'Omoda', 'Jaecoo', 'Yangwang', 'AVATR'
        ) THEN 'Chinese_EV'
        WHEN {{ brand_col }} IN (
            'Toyota', 'Ford', 'Hyundai', 'Mazda', 'Kia',
            'Honda', 'Mitsubishi', 'Nissan', 'Suzuki', 'Isuzu',
            'Subaru', 'Chevrolet', 'Volkswagen', 'Jeep', 'RAM',
            'Dodge', 'Peugeot', 'Renault', 'MINI'
        ) THEN 'Mass_Market'
        ELSE 'Other'
    END
{% endmacro %}
