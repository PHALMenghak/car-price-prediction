-- dbt/tests/assert_log_price_consistency.sql
-- Business Rule: log_price in ML Feature Store must strictly match pure LN(price).

SELECT listing_id, price, log_price
FROM {{ ref('fct_cars_ml_features') }}
WHERE ABS(log_price - LN(price)) > 0.0001
