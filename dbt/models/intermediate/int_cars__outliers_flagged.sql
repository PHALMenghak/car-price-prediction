-- dbt/models/intermediate/int_cars__outliers_flagged.sql
-- Intermediate Layer: NLP listing signals, spam detection, financing down payments, and dynamic 2-tier IQR outlier fences.
-- Grain: 1 listing_id x 1 scrape_date.

{{ config(materialized = 'view') }}

WITH specs_parsed AS (
    SELECT * FROM {{ ref('int_cars__specs_imputed') }}
),

signals_flagged AS (
    SELECT
        sp.*,

        -- Title NLP features
        {{ extract_nlp_signals('sp.title_clean') }},

        -- Non-vehicle spam detection (safe on Khmer transmission 'លេខដៃ')
        {{ detect_non_vehicle_spam('sp.title_clean', 'sp.description_clean', 'sp.price') }} AS is_spam,

        -- Financing down-payment detection (protects generic dealer boilerplate)
        {{ detect_down_payment('sp.price', 'sp.vehicle_year', 'sp._precleaned_text') }} AS is_down_payment

    FROM specs_parsed sp
),

-- Segment Statistics & Dynamic Statistical IQR Fences (2-Tier Hybrid)
segment_stats AS (
    SELECT
        sf.*,

        -- Volume of peer listings in this exact (Brand, Model, Year) segment
        COUNT(*) FILTER (
            WHERE sf.price >= 500 AND sf.vehicle_brand IS NOT NULL AND sf.vehicle_model IS NOT NULL AND sf.vehicle_year IS NOT NULL
        ) OVER (
            PARTITION BY sf.vehicle_brand, sf.vehicle_model, sf.vehicle_year
        ) AS _n_segment,

        -- Quartiles for peer segment
        QUANTILE_CONT(sf.price, 0.25) FILTER (
            WHERE sf.price >= 500 AND sf.vehicle_brand IS NOT NULL AND sf.vehicle_model IS NOT NULL AND sf.vehicle_year IS NOT NULL
        ) OVER (
            PARTITION BY sf.vehicle_brand, sf.vehicle_model, sf.vehicle_year
        ) AS _q1_price,

        QUANTILE_CONT(sf.price, 0.50) FILTER (
            WHERE sf.price >= 500 AND sf.vehicle_brand IS NOT NULL AND sf.vehicle_model IS NOT NULL AND sf.vehicle_year IS NOT NULL
        ) OVER (
            PARTITION BY sf.vehicle_brand, sf.vehicle_model, sf.vehicle_year
        ) AS _median_price,

        QUANTILE_CONT(sf.price, 0.75) FILTER (
            WHERE sf.price >= 500 AND sf.vehicle_brand IS NOT NULL AND sf.vehicle_model IS NOT NULL AND sf.vehicle_year IS NOT NULL
        ) OVER (
            PARTITION BY sf.vehicle_brand, sf.vehicle_model, sf.vehicle_year
        ) AS _q3_price

    FROM signals_flagged sf
),

fences AS (
    SELECT
        s.*,

        -- Routing: High-confidence Segment IQR (N >= 10) vs Heuristic Fallback (N < 10)
        CASE
            WHEN COALESCE(s._n_segment, 0) >= 10 THEN 'SEGMENT_IQR'
            ELSE 'HEURISTIC_FALLBACK'
        END AS outlier_method,

        -- Dynamic Lower Fence (with zero-variance protection and $500 marketplace floor clamp)
        GREATEST(
            ROUND(s._q1_price - 1.5 * GREATEST(s._q3_price - s._q1_price, s._median_price * 0.10), 0),
            500.0
        ) AS price_lower_fence,

        -- Dynamic Upper Fence (with zero-variance protection)
        ROUND(
            s._q3_price + 1.5 * GREATEST(s._q3_price - s._q1_price, s._median_price * 0.10),
            0
        ) AS price_upper_fence

    FROM segment_stats s
),

evaluated AS (
    SELECT
        f.*,

        -- Statistical Low/High indicators (Clean references to precomputed fences)
        CASE
            WHEN f.outlier_method = 'SEGMENT_IQR' AND f.price < f.price_lower_fence THEN 1
            ELSE 0
        END AS _is_stat_low,

        CASE
            WHEN f.outlier_method = 'SEGMENT_IQR' AND f.price > f.price_upper_fence THEN 1
            ELSE 0
        END AS _is_stat_high,

        -- Final Outlier Determination (Option A: 2-Tier Hybrid)
        CASE
            WHEN f.price IS NULL OR f.price <= 0 THEN 0

            -- Tier 1: Statistical IQR for Common Segments (N >= 10)
            WHEN f.outlier_method = 'SEGMENT_IQR' AND (f.price < f.price_lower_fence OR f.price > f.price_upper_fence)
                THEN 1

            -- Tier 2: Heuristic Fallback for Rare Cars / Singletons (N < 10)
            WHEN f.outlier_method = 'HEURISTIC_FALLBACK'
             AND {{ detect_price_outlier('f.price', 'f.vehicle_brand', 'f.vehicle_model', 'f.vehicle_year', 'f.vehicle_age') }} = 1
                THEN 1

            ELSE 0
        END AS is_price_outlier

    FROM fences f
)

SELECT * FROM evaluated
