-- dbt/tests/assert_non_negative_price_drops.sql
-- Business Rule: price_drop_amount and days_on_market must strictly be non-negative.

SELECT listing_id, price_drop_amount, days_on_market
FROM {{ ref('fct_car_listings') }}
WHERE price_drop_amount < 0
   OR days_on_market < 0
