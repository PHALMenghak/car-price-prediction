"""
tests/test_duckdb_service.py
============================
Unit tests for modernized DuckDB analytics service, holdout evaluation,
price segmentation, SLA scorecard, and anomaly queries.
"""

import pandas as pd
import pytest

from dashboard.services import duckdb_service


def test_market_kpis():
    kpis = duckdb_service.get_market_kpis()
    assert isinstance(kpis, dict)
    assert "total_listings" in kpis
    assert "avg_price" in kpis
    assert "median_price" in kpis
    assert kpis["total_listings"] > 0
    assert kpis["median_price"] > 0


def test_price_segments():
    df = duckdb_service.get_price_segments()
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "price_segment" in df.columns
    assert "count" in df.columns
    assert "avg_price" in df.columns
    assert "share" in df.columns
    assert len(df) == 4


def test_fuel_premium_comparison():
    df = duckdb_service.get_fuel_premium_comparison()
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "fuel_type" in df.columns
    assert "count" in df.columns
    assert "median_price" in df.columns


def test_holdout_evaluation():
    holdout = duckdb_service.get_holdout_evaluation_data()
    assert isinstance(holdout, dict)
    assert "df" in holdout
    assert "r2_log" in holdout
    assert "mae_usd" in holdout
    assert "mape_pct" in holdout
    assert holdout["test_count"] > 0
    assert holdout["r2_log"] > 0.85
    eval_df = holdout["df"]
    assert "actual_price" in eval_df.columns
    assert "predicted_price" in eval_df.columns
    assert "residual_log" in eval_df.columns


def test_correlation_matrix():
    corr = duckdb_service.get_correlation_matrix()
    assert isinstance(corr, pd.DataFrame)
    assert not corr.empty
    assert "Price (USD)" in corr.columns
    assert "Vehicle Age" in corr.columns
    # Price and vehicle age should be negatively correlated
    assert corr.loc["Vehicle Age", "Price (USD)"] < 0


def test_target_leakage_audit():
    audit_df = duckdb_service.get_target_leakage_audit()
    assert isinstance(audit_df, pd.DataFrame)
    assert len(audit_df) >= 5
    assert "Attribute" in audit_df.columns
    assert "Leakage Risk" in audit_df.columns


def test_data_quality_metrics_and_sla():
    metrics = duckdb_service.get_data_quality_metrics()
    assert isinstance(metrics, dict)
    assert metrics["raw_listings"] > 0
    assert metrics["clean_listings"] > 0
    assert metrics["usable_pct"] >= 90.0
    assert metrics["critical_conformance_pct"] >= 95.0
    assert metrics["total_anomalies"] > 0
    assert metrics["dbt_passed"] == 101
    assert "freshness_status" in metrics
    assert "freshness_observed" in metrics

    sla_df = duckdb_service.get_pipeline_sla_scorecard()
    assert isinstance(sla_df, pd.DataFrame)
    assert len(sla_df) == 5
    assert "SLA Boundary" in sla_df.columns
    assert "Status" in sla_df.columns


def test_dq_status_breakdown_and_triggers():
    status_df = duckdb_service.get_dq_status_breakdown()
    assert isinstance(status_df, pd.DataFrame)
    assert not status_df.empty
    assert "Status" in status_df.columns
    assert "Count" in status_df.columns
    assert "Share" in status_df.columns

    triggers_df = duckdb_service.get_top_anomaly_triggers()
    assert isinstance(triggers_df, pd.DataFrame)
    assert not triggers_df.empty
    assert "Anomaly Trigger Rule" in triggers_df.columns
    assert "Violations" in triggers_df.columns


def test_vehicle_listings_query_columns():
    df = duckdb_service.query_vehicle_listings(limit=10)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "listing_id" in df.columns
    assert "seller_type" in df.columns
    assert "seller_phones" in df.columns
    assert "data_quality_status" in df.columns


def test_transformation_pipeline_funnel():
    funnel_df = duckdb_service.get_transformation_pipeline_funnel()
    assert isinstance(funnel_df, pd.DataFrame)
    assert len(funnel_df) == 5
    assert "Stage" in funnel_df.columns
    assert "Count" in funnel_df.columns
    assert (funnel_df["Count"] > 0).all()


def test_field_completeness_and_uplift():
    uplift_df = duckdb_service.get_field_completeness_and_uplift()
    assert isinstance(uplift_df, pd.DataFrame)
    assert len(uplift_df) >= 5
    assert "Field" in uplift_df.columns
    assert "Raw Fill %" in uplift_df.columns
    assert "Conformed Fill %" in uplift_df.columns
    assert "Uplift %" in uplift_df.columns
    assert "Priority" not in uplift_df.columns


def test_similar_market_listings():
    sim_df = duckdb_service.get_similar_market_listings("Toyota", "Prius", limit=3)
    assert isinstance(sim_df, pd.DataFrame)
    assert not sim_df.empty
    assert "Asking Price (USD)" in sim_df.columns
    assert "Year" in sim_df.columns
    assert len(sim_df) <= 3


def test_top_brands_volume_and_price():
    # Volume mode should have Toyota at the top
    vol_df = duckdb_service.get_top_brands(sort_by="volume", top_n=5)
    assert isinstance(vol_df, pd.DataFrame)
    assert not vol_df.empty
    assert "vehicle_brand" in vol_df.columns
    assert "listings" in vol_df.columns
    assert "share_pct" in vol_df.columns
    assert vol_df.iloc[0]["vehicle_brand"] == "Toyota"
    assert vol_df.iloc[0]["share_pct"] > 30.0

    # Price mode should have high average prices
    prc_df = duckdb_service.get_top_brands(sort_by="price", top_n=5)
    assert isinstance(prc_df, pd.DataFrame)
    assert not prc_df.empty
    assert prc_df.iloc[0]["avg_price"] > 50000.0


def test_market_trend_anchoring():
    for preset in ["7 Days", "30 Days", "90 Days", "All"]:
        trend_df = duckdb_service.get_market_trend(date_range_preset=preset)
        assert isinstance(trend_df, pd.DataFrame)
        assert not trend_df.empty
        assert "date" in trend_df.columns
        assert "listings" in trend_df.columns
        assert "avg_price" in trend_df.columns


def test_cambodia_tax_and_regional_dynamics():
    tax_df = duckdb_service.get_tax_document_premium()
    assert isinstance(tax_df, pd.DataFrame)
    assert not tax_df.empty
    assert "tax_status" in tax_df.columns
    assert "median_price" in tax_df.columns
    assert "share_pct" in tax_df.columns
    statuses = set(tax_df["tax_status"].tolist())
    assert "Tax Paper" in statuses
    assert "Plate Number" in statuses

    reg_df = duckdb_service.get_regional_price_distribution(top_n=5)
    assert isinstance(reg_df, pd.DataFrame)
    assert not reg_df.empty
    assert "province" in reg_df.columns
    assert "listings" in reg_df.columns
    assert reg_df.iloc[0]["province"] == "Phnom Penh"
    assert reg_df.iloc[0]["share_pct"] > 80.0

