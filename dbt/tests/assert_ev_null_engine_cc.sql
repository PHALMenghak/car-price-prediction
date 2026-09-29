-- dbt/tests/assert_ev_null_engine_cc.sql
-- Business Rule: Displacement is not applicable for pure electric vehicles (must be NULL, not 0 cc).

SELECT listing_id, vehicle_brand, vehicle_engine_cc, is_electric
FROM {{ ref('int_cars_cleaned') }}
WHERE is_electric = 1
  AND vehicle_engine_cc IS NOT NULL
