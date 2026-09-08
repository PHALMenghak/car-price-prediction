-- dbt/tests/assert_positive_prices.sql
-- Business Rule: All vehicles in Gold must have prices >= $500.

SELECT listing_id, price
FROM {{ ref('fct_cars_ml_features') }}
WHERE price < 500
