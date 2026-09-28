"""
dashboard/data_loader.py
========================
Public facade for all analytical DuckDB queries.

Architecture:
    This file serves as a backwards-compatible entry point re-exporting domain query
    modules from `dashboard.queries.*`:
      - `dashboard.queries.base`             (connection pool, parquet paths, constants)
      - `dashboard.queries.core_queries`     (pipeline manifest, dbt health, dates)
      - `dashboard.queries.quality_queries`  (waterfall, DHI, audit sample, anomalies)
      - `dashboard.queries.pipeline_queries` (bronze volume, scraper health, deduplication)
      - `dashboard.queries.cleaning_queries` (missingness trends, conformed comparison)
      - `dashboard.queries.feature_queries`  (ML feature matrix, distributions, correlation)
      - `dashboard.queries.report_queries`   (executive markdown audit report)
      - `dashboard.queries.market_queries`   (market intelligence, brand/model, trends)

All results remain cached for 1 hour via @st.cache_data.
"""

from __future__ import annotations

# Re-export base infrastructure & constants
from dashboard.queries.base import (
    _BRONZE_DIR,
    _HERE,
    _con,
    BRONZE_GLOB,
    CACHE_TTL,
    DBT_RUN_RESULTS,
    GOLD_MART_PATH,
    GOLD_ML_PATH,
    MANIFEST_PATH,
    MODELS_DIR,
    SILVER_PATH,
    build_date_filter,
    build_filter_sql,
)

# Re-export Core queries
from dashboard.queries.core_queries import (
    load_available_dates,
    load_dbt_test_status,
    load_manifest,
)

# Re-export Quality queries
from dashboard.queries.quality_queries import (
    load_audit_sample,
    load_price_year_anomaly_sample,
    load_quality_summary,
    load_top_reasons,
)

# Re-export Pipeline queries
from dashboard.queries.pipeline_queries import (
    load_bronze_volume,
    load_duplicate_stats,
    load_pipeline_funnel,
    load_raw_ingestion_summary,
    load_scraper_health,
)

# Re-export Cleaning & Transformation queries
from dashboard.queries.cleaning_queries import (
    load_cleaning_impact_stats,
    load_cleaning_rules_summary,
    load_completeness_detail,
    load_daily_missingness_trend,
    load_raw_vs_conformed_comparison,
)

# Re-export Feature Profiling & ML queries
from dashboard.queries.feature_queries import (
    load_categorical_cardinality,
    load_categorical_distribution,
    load_feature_correlation_matrix,
    load_feature_distribution_sample,
    load_feature_numeric_stats,
    load_ml_leakage_audit,
    load_ml_readiness,
)

# Re-export Market Intelligence queries
from dashboard.queries.market_queries import (
    load_brand_price_trend,
    load_brand_volume_and_price,
    load_filter_options,
    load_market_insights,
    load_market_kpis,
    load_market_share_breakdown,
    load_mileage_by_brand,
    load_model_comparison_matrix,
    load_model_price_range,
    load_model_vintage_breakdown,
    load_models_for_brands,
    load_price_box_plot_data,
    load_price_distribution_data,
    load_price_trend_over_time,
    load_price_vs_mileage_sample,
    load_price_vs_year,
    load_province_brand_breakdown,
    load_regional_pricing,
    load_tax_type_comparison,
    load_vehicle_characteristic_analysis,
    load_vintage_price_curves,
    load_year_distribution,
)

# Re-export Reporting queries
from dashboard.queries.report_queries import (
    generate_markdown_report,
)

__all__ = [
    # Paths & infrastructure
    "_con",
    "SILVER_PATH",
    "BRONZE_GLOB",
    "GOLD_ML_PATH",
    "GOLD_MART_PATH",
    "MANIFEST_PATH",
    "MODELS_DIR",
    "DBT_RUN_RESULTS",
    "CACHE_TTL",
    "build_date_filter",
    "build_filter_sql",
    # Core
    "load_manifest",
    "load_dbt_test_status",
    "load_available_dates",
    # Quality
    "load_quality_summary",
    "load_top_reasons",
    "load_audit_sample",
    "load_price_year_anomaly_sample",
    # Pipeline
    "load_bronze_volume",
    "load_duplicate_stats",
    "load_scraper_health",
    "load_pipeline_funnel",
    "load_raw_ingestion_summary",
    # Cleaning
    "load_daily_missingness_trend",
    "load_completeness_detail",
    "load_cleaning_impact_stats",
    "load_raw_vs_conformed_comparison",
    "load_cleaning_rules_summary",
    # Features
    "load_ml_readiness",
    "load_ml_leakage_audit",
    "load_feature_numeric_stats",
    "load_categorical_cardinality",
    "load_categorical_distribution",
    "load_feature_distribution_sample",
    "load_feature_correlation_matrix",
    # Market Intelligence
    "load_market_kpis",
    "load_filter_options",
    "load_models_for_brands",
    "load_price_distribution_data",
    "load_price_box_plot_data",
    "load_price_trend_over_time",
    "load_brand_price_trend",
    "load_brand_volume_and_price",
    "load_model_comparison_matrix",
    "load_model_vintage_breakdown",
    "load_model_price_range",
    "load_mileage_by_brand",
    "load_price_vs_year",
    "load_price_vs_mileage_sample",
    "load_year_distribution",
    "load_vintage_price_curves",
    "load_regional_pricing",
    "load_province_brand_breakdown",
    "load_tax_type_comparison",
    "load_vehicle_characteristic_analysis",
    "load_market_share_breakdown",
    "load_market_insights",
    # Reporting
    "generate_markdown_report",
]
