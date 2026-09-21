"""
dashboard/queries/__init__.py
=============================
Domain-driven analytical query package for Cambodian Car Data Quality Center.
"""

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
    SILVER_PATH,
)
from dashboard.queries.cleaning_queries import (
    load_cleaning_impact_stats,
    load_cleaning_rules_summary,
    load_completeness_detail,
    load_daily_missingness_trend,
    load_raw_vs_conformed_comparison,
)
from dashboard.queries.core_queries import (
    load_available_dates,
    load_dbt_test_status,
    load_manifest,
)
from dashboard.queries.feature_queries import (
    load_categorical_cardinality,
    load_categorical_distribution,
    load_feature_correlation_matrix,
    load_feature_distribution_sample,
    load_feature_numeric_stats,
    load_ml_leakage_audit,
    load_ml_readiness,
)
from dashboard.queries.pipeline_queries import (
    load_bronze_volume,
    load_duplicate_stats,
    load_pipeline_funnel,
    load_raw_ingestion_summary,
    load_scraper_health,
)
from dashboard.queries.quality_queries import (
    load_audit_sample,
    load_price_year_anomaly_sample,
    load_quality_summary,
    load_top_reasons,
)
from dashboard.queries.market_queries import (
    load_market_kpis,
    load_market_share_breakdown,
    load_regional_pricing,
    load_tax_type_comparison,
    load_vintage_price_curves,
)
from dashboard.queries.report_queries import (
    generate_markdown_report,
)

__all__ = [
    # Base & connection
    "_con",
    "SILVER_PATH",
    "BRONZE_GLOB",
    "GOLD_ML_PATH",
    "GOLD_MART_PATH",
    "MANIFEST_PATH",
    "DBT_RUN_RESULTS",
    "CACHE_TTL",
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
    # Market Intelligence
    "load_market_kpis",
    "load_vintage_price_curves",
    "load_regional_pricing",
    "load_tax_type_comparison",
    "load_market_share_breakdown",
    # Features
    "load_ml_readiness",
    "load_ml_leakage_audit",
    "load_feature_numeric_stats",
    "load_categorical_cardinality",
    "load_categorical_distribution",
    "load_feature_distribution_sample",
    "load_feature_correlation_matrix",
    # Reporting
    "generate_markdown_report",
]
