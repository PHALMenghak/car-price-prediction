-- dbt/tests/assert_no_train_test_overlap.sql
-- Business Rule: ML Training Mart must have zero listing overlap across train/validation/test split groups.

SELECT listing_id, count(DISTINCT split_group) AS split_count
FROM {{ ref('fct_cars_ml_features') }}
GROUP BY listing_id
HAVING count(DISTINCT split_group) > 1
