-- dbt/tests/assert_staging_grain.sql
-- Business Rule: Staging layer observation grain must be unique on (listing_id, scrape_date).

SELECT listing_id, scrape_date, count(*) as duplicate_count
FROM {{ ref('stg_khmer24_cars') }}
GROUP BY listing_id, scrape_date
HAVING count(*) > 1
