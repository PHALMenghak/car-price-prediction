-- dbt/macros/quality/is_ev_vehicle.sql
-- Canonical EV identification: Pure Electric fuel type OR dedicated EV brand without combustion fuel.

{% macro is_ev_vehicle(brand_col, fuel_col) %}
(
    LOWER(COALESCE(CAST({{ fuel_col }} AS VARCHAR), '')) IN ('electric', 'អគ្គិសនី', 'ev')
    OR (
        LOWER(COALESCE(CAST({{ brand_col }} AS VARCHAR), '')) IN (
            'tesla', 'nio', 'zeekr', 'polestar', 'rivian', 'lucid', 'xiaomi',
            'aion', 'xpeng', 'avatr', 'deepal', 'icar', 'leapmotor', 'arcfox', 'vinfast'
        )
        AND LOWER(COALESCE(CAST({{ fuel_col }} AS VARCHAR), '')) NOT IN ('hybrid', 'petrol', 'diesel')
    )
)
{% endmacro %}
