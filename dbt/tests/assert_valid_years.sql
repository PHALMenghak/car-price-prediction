-- dbt/tests/assert_valid_years.sql
-- Business Rule: Vehicle year & observation-date age must be non-negative and within valid automotive boundaries.

SELECT
    listing_id,
    scrape_date,
    vehicle_year,
    vehicle_age
FROM {{ ref('fct_car_listings') }}
WHERE vehicle_year IS NULL
   OR vehicle_age IS NULL
   OR vehicle_age < 0
   OR vehicle_age != GREATEST(CAST(date_part('year', scrape_date) - vehicle_year AS INTEGER), 0)
   OR vehicle_year < 1990
   OR vehicle_year > (CAST(date_part('year', CURRENT_DATE) AS INTEGER) + 1)
