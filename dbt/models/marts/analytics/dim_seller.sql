-- dbt/models/marts/analytics/dim_seller.sql
-- Merchant Dimension: Dealership and private seller profiles and contacts.
-- Grain: 1 record per unique Seller Contact / Identity (unique seller_key).

{{ config(
    materialized = 'table',
    post_hook    = [
        "COPY {{ this }} TO 'data/gold/dim_seller.parquet' (FORMAT PARQUET)"
    ]
) }}

WITH raw_sellers AS (
    SELECT
        MD5(
            COALESCE(
                NULLIF(TRIM(seller_phones), ''),
                NULLIF(TRIM(seller_name), ''),
                'unspecified'
            )
        ) AS seller_key,
        TRIM(seller_name)   AS seller_name,
        TRIM(seller_phones) AS seller_phones,
        seller_type,
        ROW_NUMBER() OVER (
            PARTITION BY MD5(
                COALESCE(
                    NULLIF(TRIM(seller_phones), ''),
                    NULLIF(TRIM(seller_name), ''),
                    'unspecified'
                )
            )
            ORDER BY scraped_at DESC
        ) AS _recency_rank
    FROM {{ ref('int_cars_cleaned') }}
    WHERE data_quality_status IN ('VALID', 'WARNING')
      AND (seller_name IS NOT NULL OR seller_phones IS NOT NULL)
)

SELECT
    seller_key,
    seller_name,
    seller_phones,
    seller_type
FROM raw_sellers
WHERE _recency_rank = 1
