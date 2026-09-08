-- dbt/tests/assert_valid_years.sql
-- Business Rule: Vehicle years in Gold ML must be within [1990, CURRENT_YEAR + 1].

SELECT listing_id, vehicle_model_year
FROM {{ ref('fct_cars_ml_features') }}
WHERE vehicle_model_year < 1990
   OR vehicle_model_year > (CAST(date_part('year', CURRENT_DATE) AS INTEGER) + 1)
