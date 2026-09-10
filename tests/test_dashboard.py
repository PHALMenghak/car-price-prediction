"""
tests/test_dashboard.py
=======================
Unit tests for Executive Data Quality Dashboard configuration,
DuckDB aggregations, leakage audit, and metric calculations.
"""

import os
from pathlib import Path
import pandas as pd
import pytest

from dashboard import config, data_loader


def test_config_weights_and_thresholds():
    assert "quarantined" in config.DHI_WEIGHTS
    assert "warning" in config.DHI_WEIGHTS
    assert config.DHI_WEIGHTS["quarantined"] == 1.0
    assert config.DHI_WEIGHTS["warning"] == 0.03
    assert config.SLA_MIN_RECORDS_PER_DAY == 1000

    label, color = config.dhi_status(98.5)
    assert "Excellent" in label
    assert color == "normal"

    label_crit, color_crit = config.dhi_status(80.0)
    assert "Critical" in label_crit
    assert color_crit == "inverse"


def test_data_loader_manifest_and_dbt():
    manifest = data_loader.load_manifest()
    assert isinstance(manifest, dict)

    dbt_status = data_loader.load_dbt_test_status()
    assert isinstance(dbt_status, dict)
    assert "passed" in dbt_status
    assert "total" in dbt_status
    if dbt_status["available"]:
        assert dbt_status["failed"] == 0
        assert dbt_status["pass_rate_pct"] == 100.0


def test_quality_summary_and_dates():
    dates = data_loader.load_available_dates()
    assert isinstance(dates, list)
    if dates:
        assert len(dates) > 0

    q_df = data_loader.load_quality_summary()
    assert isinstance(q_df, pd.DataFrame)
    if not q_df.empty:
        assert "dhi" in q_df.columns
        assert "total" in q_df.columns
        assert "quarantined" in q_df.columns
        assert (q_df["dhi"] >= 0).all()
        assert (q_df["dhi"] <= 100).all()


def test_missingness_trend():
    trend_df = data_loader.load_daily_missingness_trend()
    assert isinstance(trend_df, pd.DataFrame)
    if not trend_df.empty:
        assert "scrape_date" in trend_df.columns
        assert "Price (Target)" in trend_df.columns
        assert (trend_df["Price (Target)"] == 0.0).all()


def test_duplicate_monitoring():
    dup_stats = data_loader.load_duplicate_stats()
    assert isinstance(dup_stats, dict)
    assert dup_stats["bronze_total"] >= dup_stats["silver_total"]
    # Verify intra-day deduplication efficacy
    silver_daily = dup_stats["silver_daily"]
    if not silver_daily.empty:
        assert (silver_daily["intra_day_duplicates"] == 0).all()


def test_pipeline_funnel_and_cleaning_impact():
    funnel_df = data_loader.load_pipeline_funnel()
    assert isinstance(funnel_df, pd.DataFrame)
    if not funnel_df.empty:
        assert len(funnel_df) == 5
        # Funnel stage counts should be non-increasing generally
        counts = funnel_df["count"].tolist()
        assert counts[0] >= counts[1] >= counts[3] >= counts[4]

    impact = data_loader.load_cleaning_impact_stats()
    assert isinstance(impact, dict)
    if impact:
        assert impact["total_silver"] > 0
        assert impact["preserved_pct"] >= 95.0
def test_ml_readiness_and_leakage_prevention():
    ml_info = data_loader.load_ml_readiness()
    assert isinstance(ml_info, dict)
    if ml_info.get("available"):
        assert ml_info["total_ml_records"] > 0
        assert ml_info["verdict"] == "READY"
        t_stats = ml_info["target_stats"]
        assert t_stats["price_min"] > 0
        assert t_stats["invalid_target_count"] == 0

    # Leakage audit must confirm zero leakage
    leakage_df = data_loader.load_ml_leakage_audit()
    assert isinstance(leakage_df, pd.DataFrame)
    if not leakage_df.empty:
        for _, row in leakage_df.iterrows():
            assert "SAFE" in row["leakage_status"]
            assert row["in_gold_ml_features"] == "🛡️ Excluded"


def test_raw_ingestion_summary():
    summary = data_loader.load_raw_ingestion_summary()
    assert isinstance(summary, dict)
    if summary["available"]:
        assert summary["total_files"] > 0
        assert summary["total_records"] > 0
        assert summary["total_distinct"] > 0
        assert summary["total_size_mb"] > 0
        assert isinstance(summary["batches"], pd.DataFrame)
        assert not summary["batches"].empty
        assert "file_name" in summary["batches"].columns
        assert "records_ingested" in summary["batches"].columns


def test_cleaning_rules_summary():
    rules_df = data_loader.load_cleaning_rules_summary()
    assert isinstance(rules_df, pd.DataFrame)
    assert not rules_df.empty
    assert "attribute" in rules_df.columns
    assert "transformation" in rules_df.columns
    assert "logic" in rules_df.columns
    assert "conformance_rule" in rules_df.columns
    attrs = rules_df["attribute"].tolist()
    assert "vehicle_brand" in attrs
    assert "vehicle_model" in attrs
    assert "vehicle_year" in attrs


def test_feature_profiling_numeric_stats():
    # Test Silver profiling
    silver_num = data_loader.load_feature_numeric_stats("silver")
    assert isinstance(silver_num, pd.DataFrame)
    if not silver_num.empty:
        assert "feature" in silver_num.columns
        assert "mean" in silver_num.columns
        assert "median_val" in silver_num.columns
        features = silver_num["feature"].tolist()
        assert "price" in features

    # Test Gold ML profiling
    gold_num = data_loader.load_feature_numeric_stats("gold_ml")
    assert isinstance(gold_num, pd.DataFrame)
    if not gold_num.empty:
        features = gold_num["feature"].tolist()
        assert "price" in features
        assert "log_price" in features


def test_categorical_cardinality_and_distribution():
    card_df = data_loader.load_categorical_cardinality("silver")
    assert isinstance(card_df, pd.DataFrame)
    if not card_df.empty:
        assert "feature" in card_df.columns
        assert "distinct_count" in card_df.columns
        assert "top_1" in card_df.columns

    dist_df = data_loader.load_categorical_distribution("vehicle_brand", top_n=5, target_dataset="silver")
    assert isinstance(dist_df, pd.DataFrame)
    if not dist_df.empty:
        assert "category" in dist_df.columns
        assert "count" in dist_df.columns
        assert "pct" in dist_df.columns
        assert len(dist_df) <= 5


def test_price_year_anomaly_sample():
    sample_df = data_loader.load_price_year_anomaly_sample(limit=100)
    assert isinstance(sample_df, pd.DataFrame)
    if not sample_df.empty:
        assert "price" in sample_df.columns
        assert "vehicle_year" in sample_df.columns
        assert "anomaly_group" in sample_df.columns
        assert len(sample_df) <= 100


def test_feature_correlation_matrix():
    corr_df = data_loader.load_feature_correlation_matrix()
    assert isinstance(corr_df, pd.DataFrame)
    if not corr_df.empty:
        assert "price" in corr_df.columns
        assert "log_price" in corr_df.columns
        # Correlation with self must be 1.0
        assert corr_df.loc["price", "price"] == pytest.approx(1.0, 0.01)
        assert corr_df.loc["log_price", "log_price"] == pytest.approx(1.0, 0.01)


def test_load_audit_sample():
    audit_df = data_loader.load_audit_sample(limit=20)
    assert isinstance(audit_df, pd.DataFrame)
    if not audit_df.empty:
        assert "listing_id" in audit_df.columns
        assert "status" in audit_df.columns
        assert "clean_brand" in audit_df.columns
        assert "clean_price" in audit_df.columns
        assert "raw_title" in audit_df.columns
        assert "title_clean" in audit_df.columns
        assert "is_year_healed" in audit_df.columns
        assert len(audit_df) <= 20
