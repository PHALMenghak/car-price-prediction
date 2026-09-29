-- dbt/macros/quality/detect_price_outlier.sql
-- Unified Price Outlier Detection & Reason Diagnostics.
-- Contains both:
--   1. detect_price_outlier_reason: Diagnostic reason string for auditability & lineage.
--   2. detect_price_outlier: Binary 0/1 flag for filtering and quality tier tagging.
-- Uses point-in-time vehicle age rather than hardcoded calendar years.

-- =============================================================================
-- 1. DETAILED DIAGNOSTIC REASON MACRO
-- =============================================================================
{% macro detect_price_outlier_reason(price_col, brand_col, model_col, year_col, age_col=None) %}
{% set age_expr = age_col if age_col is not none else "(CAST(date_part('year', CURRENT_DATE) AS INTEGER) - " ~ year_col ~ ")" %}
CASE
    -- ── Structural Validity ─────────────────────────────────────────────────────────
    -- NULL or zero price is a structural problem handled by the INVALID quality tier.
    WHEN {{ price_col }} IS NULL OR {{ price_col }} <= 0
        THEN 'MISSING_OR_ZERO_PRICE'

    -- ── Rule 1: Luxury Lower Bound (Age-Indexed) ────────────────────────────────────
    -- Modern luxury vehicles listed under $15k are fraud, loan deposits, or scam listings.
    WHEN LOWER(COALESCE(CAST({{ brand_col }} AS VARCHAR), ''))
         IN ('lexus', 'porsche', 'land rover', 'mercedes-benz', 'bmw', 'audi', 'cadillac')
     AND {{ age_expr }} <= 7
     AND {{ price_col }} < 15000
        THEN 'MODERN_LUXURY_SUSPICIOUS_LOW'

    -- ── Rule 2: Universal Mass-Market Lower Bound ───────────────────────────────────
    -- Protects all brands (Toyota, Hyundai, BYD, etc.) against down-payment / scam prices.
    WHEN {{ age_expr }} <= 2
     AND {{ price_col }} < 8000
        THEN 'MODERN_VEHICLE_SUSPICIOUS_LOW'
    WHEN {{ age_expr }} <= 5
     AND {{ price_col }} < 4000
        THEN 'RECENT_VEHICLE_SUSPICIOUS_LOW'
    WHEN {{ age_expr }} <= 10
     AND {{ price_col }} < 2000
        THEN 'MID_AGE_VEHICLE_SUSPICIOUS_LOW'

    -- ── Rule 3: Ultra-Luxury / Exotic Brands (Ceiling $1.5M) ────────────────────────
    -- Rolls-Royce, Bentley, Ferrari, etc. are legitimate at ultra-high prices in Cambodia.
    WHEN LOWER(COALESCE(CAST({{ brand_col }} AS VARCHAR), ''))
         IN ('rolls-royce', 'bentley', 'ferrari', 'lamborghini', 'aston martin', 'mclaren')
      OR (LOWER(COALESCE(CAST({{ brand_col }} AS VARCHAR), '')) = 'mercedes-benz'
          AND LOWER(COALESCE(CAST({{ model_col }} AS VARCHAR), '')) = 'maybach')
        THEN CASE
                 WHEN {{ price_col }} > 1500000 THEN 'EXOTIC_ABOVE_1.5M'
                 ELSE 'NORMAL_PRICE'
             END

    -- ── Rule 4: Older Luxury Model Fat-Finger Typo ──────────────────────────────────
    -- A 2001 Lexus RX300 or 2005 BMW 5 Series listed at $99k is a data-entry typo.
    WHEN LOWER(COALESCE(CAST({{ brand_col }} AS VARCHAR), ''))
         IN ('lexus', 'mercedes-benz', 'bmw')
     AND LOWER(COALESCE(CAST({{ model_col }} AS VARCHAR), ''))
         IN ('rx300', 'rx330', 'es300', 'es350', 'is250', 'c-class', '3 series', '5 series')
     AND {{ age_expr }} >= 18
     AND {{ price_col }} > 55000
        THEN 'OLDER_LUXURY_TYPO_HIGH'

    -- ── Rule 5: Tesla Model 3 Generation Typo ───────────────────────────────────────
    -- Pre-2022 Model 3 at over $60k is almost certainly a wrong decimal entry.
    WHEN LOWER(COALESCE(CAST({{ brand_col }} AS VARCHAR), '')) = 'tesla'
     AND LOWER(COALESCE(CAST({{ model_col }} AS VARCHAR), '')) = 'model 3'
     AND {{ age_expr }} >= 4
     AND {{ price_col }} > 60000
        THEN 'OLDER_MODEL_3_TYPO_HIGH'

    -- ── Rule 6: Standard Luxury Brands (Ceiling $600k) ──────────────────────────────
    -- Lexus, BMW, Mercedes-Benz, Porsche, etc. are legitimate up to $600k.
    WHEN LOWER(COALESCE(CAST({{ brand_col }} AS VARCHAR), ''))
         IN ('lexus', 'mercedes-benz', 'bmw', 'porsche', 'land rover', 'audi',
             'cadillac', 'maserati', 'genesis', 'volvo', 'tesla')
        THEN CASE
                 WHEN {{ price_col }} > 600000 THEN 'LUXURY_ABOVE_600K'
                 ELSE 'NORMAL_PRICE'
             END

    -- ── Rule 7: Flagship Models from Mass-Market & Chinese EV Brands (Ceiling $350k) ─
    -- Toyota Land Cruiser, Ford F-150 Raptor, Kia EV9, BYD, Zeekr can exceed $160k.
    WHEN (
        (LOWER(COALESCE(CAST({{ brand_col }} AS VARCHAR), '')) = 'toyota'
         AND LOWER(COALESCE(CAST({{ model_col }} AS VARCHAR), ''))
             IN ('land cruiser', 'land cruiser prado', 'alphard', 'vellfire', 'granvia',
                 'century', 'tundra', 'sequoia', 'gr supra', 'hiace', 'crown',
                 'grand highlander', 'hilux revo', 'hilux', 'tacoma', '4runner', 'fortuner'))
        OR (LOWER(COALESCE(CAST({{ brand_col }} AS VARCHAR), '')) = 'ford'
            AND LOWER(COALESCE(CAST({{ model_col }} AS VARCHAR), ''))
                IN ('f-150', 'f-150 raptor', 'ranger raptor', 'bronco', 'bronco sport', 'expedition'))
        OR (LOWER(COALESCE(CAST({{ brand_col }} AS VARCHAR), '')) = 'hyundai'
            AND LOWER(COALESCE(CAST({{ model_col }} AS VARCHAR), ''))
                IN ('palisade', 'santa fe', 'staria', 'county', 'equus'))
        OR (LOWER(COALESCE(CAST({{ brand_col }} AS VARCHAR), '')) = 'kia'
            AND LOWER(COALESCE(CAST({{ model_col }} AS VARCHAR), ''))
                IN ('carnival', 'ev6', 'ev9', 'mohave', 'stinger'))
        OR LOWER(COALESCE(CAST({{ brand_col }} AS VARCHAR), ''))
           IN ('xiaomi', 'zeekr', 'deepal', 'byd', 'tank', 'denza', 'li auto',
               'nio', 'hongqi', 'gwm', 'yangwang', 'aito')
    )
        THEN CASE
                 WHEN {{ price_col }} > 350000 THEN 'FLAGSHIP_ABOVE_350K'
                 ELSE 'NORMAL_PRICE'
             END

    -- ── Rule 8: Economy Model Fat-Finger Typo ────────────────────────────────────────
    -- A 3+ year-old Prius, Corolla, or Vitz listed above $45k is a decimal typo.
    WHEN LOWER(COALESCE(CAST({{ model_col }} AS VARCHAR), ''))
         IN ('prius', 'corolla', 'camry', 'vitz', 'yaris', 'morning', 'ray',
             'spark', 'windstar', 'ecosport', 'fit', 'march', 'mira', 'swift')
     AND {{ age_expr }} >= 3
     AND {{ price_col }} > 45000
        THEN 'ECONOMY_CAR_TYPO_HIGH'

    -- ── Rule 9: Older Family Crossover Fat-Finger Typo ───────────────────────────────
    -- An 11+ year-old Highlander, CR-V, or RAV4 above $45k is a decimal typo.
    WHEN LOWER(COALESCE(CAST({{ model_col }} AS VARCHAR), ''))
         IN ('highlander', 'cr-v', 'rav4', 'tucson', 'sportage', 'duster', 'x-trail')
     AND {{ age_expr }} >= 11
     AND {{ price_col }} > 45000
        THEN 'OLDER_CROSSOVER_TYPO_HIGH'

    -- ── Rule 10: Age-Based Depreciation Envelope ─────────────────────────────────────
    WHEN {{ age_expr }} > 11
     AND {{ price_col }} > 50000
        THEN 'DEPRECIATION_ENVELOPE_EXCEEDED'
    WHEN {{ age_expr }} BETWEEN 7 AND 11
     AND {{ price_col }} > 80000
        THEN 'DEPRECIATION_ENVELOPE_EXCEEDED'
    WHEN {{ age_expr }} < 7
     AND {{ price_col }} > 160000
        THEN 'DEPRECIATION_ENVELOPE_EXCEEDED'

    -- ── Rule 11: General Extreme Upper Bound ─────────────────────────────────────────
    WHEN {{ price_col }} > 300000
        THEN 'GENERAL_UPPER_BOUND_EXCEEDED'

    ELSE 'NORMAL_PRICE'
END
{% endmacro %}


-- =============================================================================
-- 2. BINARY OUTLIER FLAG MACRO (1 = Outlier, 0 = Normal)
-- =============================================================================
{% macro detect_price_outlier(price_col, brand_col, model_col, year_col, age_col=None) %}
    CASE
        -- Structural invalidity (NULL / zero price) is handled by INVALID tier.
        WHEN {{ price_col }} IS NULL OR {{ price_col }} <= 0
            THEN 0
        WHEN {{ detect_price_outlier_reason(price_col, brand_col, model_col, year_col, age_col) }} = 'NORMAL_PRICE'
            THEN 0
        ELSE 1
    END
{% endmacro %}
