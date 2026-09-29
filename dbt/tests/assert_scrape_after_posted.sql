-- dbt/tests/assert_scrape_after_posted.sql
-- Business Rule: Listing posted_at timestamp must logically precede or equal scraped_at (allowing 1 day tolerance for timezone offset).

SELECT listing_id, posted_at, scraped_at
FROM {{ ref('stg_khmer24_cars') }}
WHERE posted_at IS NOT NULL
  AND scraped_at IS NOT NULL
  AND posted_at > (scraped_at + INTERVAL 1 DAY)
