-- dbt/models/marts/core/dim_seller.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- GOLD LAYER (DIMENSION): Seller Dimension Table
-- ─────────────────────────────────────────────────────────────────────────────

{{ config(
    materialized = 'table',
    post_hook    = [
        "COPY {{ this }} TO 'data/gold/dim_seller.parquet' (FORMAT PARQUET)"
    ]
) }}

WITH seller_aggs AS (
    SELECT
        COALESCE(seller_id, 'UNKNOWN') AS seller_id,
        MAX(seller_name) AS seller_name,
        MAX(seller_type) AS seller_type,
        MAX(seller_username) AS seller_username,
        COUNT(listing_id) AS total_listings_count
    FROM {{ ref('int_cars_cleaned') }}
    GROUP BY COALESCE(seller_id, 'UNKNOWN')
)

SELECT
    MD5(seller_id) AS seller_key,
    seller_id,
    seller_name,
    seller_type,
    seller_username,
    total_listings_count
FROM seller_aggs
