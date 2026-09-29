-- dbt/models/intermediate/int_cars_audit_lineage.sql
-- Virtual QA & Lineage View: Dynamically joins clean Silver records with raw Staging inputs.
-- Provides end-to-end before/after audit traceability with zero physical storage overhead.

{{ config(materialized = 'view') }}

SELECT
    s.listing_id,
    s.scrape_date,
    s.scraped_at,
    s.posted_at,

    -- Quality Status & Diagnostic Reasons
    s.data_quality_status,
    s.data_quality_reasons,

    -- Side-by-Side: Price
    b.price_raw                             AS raw_price,
    s.price                                 AS clean_price,

    -- Side-by-Side: Brand & Model
    b.raw_spec_brand                        AS raw_brand,
    s.vehicle_brand                         AS clean_brand,
    s.brand_tier,
    b.raw_spec_model                        AS raw_model,
    s.vehicle_model                         AS clean_model,
    s.model_extraction_method,

    -- Side-by-Side: Year & Age
    b.raw_spec_year                         AS raw_year,
    s.vehicle_year                          AS clean_year,
    s.vehicle_age,
    s.is_year_healed,

    -- Side-by-Side: Body Type
    b.raw_spec_body_type                    AS raw_body_type,
    s.vehicle_body_type                     AS clean_body_type,

    -- Side-by-Side: Mileage
    b.raw_spec_mileage                      AS raw_mileage,
    s.vehicle_mileage_km                    AS clean_mileage_km,

    -- Side-by-Side: Engine CC & EV Handling
    b.raw_spec_engine_size                  AS raw_engine_size,
    s.vehicle_engine_cc                     AS clean_engine_cc,
    s.is_electric,

    -- Side-by-Side: Powertrain & Attributes
    b.raw_spec_fuel_type                    AS raw_fuel_type,
    s.vehicle_fuel_type                     AS clean_fuel_type,
    b.raw_spec_transmission                 AS raw_transmission,
    s.vehicle_transmission                  AS clean_transmission,
    b.raw_spec_tax_type                     AS raw_tax_type,
    s.vehicle_tax_type                      AS clean_tax_type,
    b.raw_spec_color                        AS raw_color,
    s.vehicle_color                         AS clean_color,
    b.raw_spec_condition                    AS raw_condition,
    s.vehicle_condition                     AS clean_condition,

    -- Side-by-Side: Location
    b.raw_province                          AS raw_location,
    s.province                              AS clean_province,

    -- Anomaly & NLP Flags
    s.has_full_option,
    s.is_spam,
    s.is_down_payment,
    s.is_price_outlier,
    s.outlier_method,
    s.price_lower_fence,
    s.price_upper_fence,

    -- Side-by-Side: Title & Description
    b.raw_title,
    s.title_clean,
    b.raw_description,

    -- Longitudinal Dynamics & SCD Type 3
    s.initial_price,
    s.previous_price,
    s.previous_scrape_date,
    s.price_drop_amount,
    s.has_price_drop,
    s.days_on_market,
    s.first_seen_date,
    s.last_seen_date,
    s.observation_count

FROM {{ ref('int_cars_cleaned') }} s
JOIN {{ ref('stg_khmer24_cars') }} b
  ON s.listing_id = b.listing_id
 AND s.scrape_date = b.scrape_date
