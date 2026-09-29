-- dbt/tests/assert_no_ml_feature_leakage.sql
-- Enterprise Governance Contract: Ensures ML feature matrix never contains future market dynamics or leaking metadata.
-- Prohibited columns: days_on_market, price_drop_amount, initial_price, seller_name, data_quality_reasons

SELECT column_name
FROM information_schema.columns
WHERE table_name = 'fct_cars_ml_features'
  AND column_name IN (
      'days_on_market',
      'price_drop_amount',
      'price_drop_percentage',
      'has_price_drop',
      'initial_price',
      'latest_price',
      'previous_price',
      'previous_scrape_date',
      'seller_name',
      'data_quality_reasons'
  )
