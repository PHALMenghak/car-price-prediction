-- dbt/tests/assert_positive_prices.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- Custom singular test: verify no negative or zero prices in the Gold layer.
-- dbt treats any row returned by this query as a TEST FAILURE.
-- An empty result set means all prices are positive → test passes.
-- ─────────────────────────────────────────────────────────────────────────────

SELECT
    listing_id,
    price,
    'Price must be positive and above minimum threshold $500' AS failure_reason
FROM {{ ref('fct_cars_ml_features') }}
WHERE price <= 0
   OR price < 500
