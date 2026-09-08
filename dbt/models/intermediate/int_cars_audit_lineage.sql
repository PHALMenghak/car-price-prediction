-- dbt/models/intermediate/int_cars_audit_lineage.sql
-- Virtual QA & Lineage View: Dynamically joins clean Silver records with raw Staging inputs.
-- Pattern B: Zero storage overhead (materialized as view). Used for debugging and rule validation.

{{ config(materialized = 'view') }}

SELECT
    s.listing_id,
    s.scrape_date,
    s.scraped_at,

    -- Quality Status & Audit Reasons
    s.data_quality_status,
    s.data_quality_reasons,

    -- Side-by-Side: Price
    s.price                                 AS clean_price,
    b.price_raw                             AS raw_price,

    -- Side-by-Side: Brand
    s.vehicle_brand                         AS clean_brand,
    b.raw_spec_brand                        AS raw_brand,

    -- Side-by-Side: Model
    s.vehicle_model                         AS clean_model,
    b.raw_spec_model                        AS raw_model,
    s.model_extraction_method,

    -- Side-by-Side: Year
    s.vehicle_year                          AS clean_year,
    b.raw_spec_year                         AS raw_year,
    s.is_year_healed,

    -- Side-by-Side: Body Type
    s.vehicle_body_type                     AS clean_body_type,
    b.raw_spec_body_type                    AS raw_body_type,

    -- Side-by-Side: Mileage & Engine
    s.vehicle_mileage_km                    AS clean_mileage_km,
    b.raw_spec_mileage                      AS raw_mileage,
    s.vehicle_engine_cc                     AS clean_engine_cc,
    b.raw_spec_engine_size                  AS raw_engine_size,

    -- Side-by-Side: Location
    s.province                              AS clean_province,
    b.raw_province                          AS raw_province,

    -- Side-by-Side: Title
    s.title_clean,
    b.raw_title                             AS raw_title

FROM {{ ref('int_cars_cleaned') }} s
JOIN {{ ref('stg_khmer24_cars') }} b
  ON s.listing_id = b.listing_id
 AND s.scrape_date = b.scrape_date
