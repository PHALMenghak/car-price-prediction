"""
tests/test_prediction_service.py
================================
Unit tests for CARIQ prediction_service and duckdb_service.
Verifies model inference, log inversion exp(y), SHAP explanation, and analytical queries.
"""

from __future__ import annotations

import pytest
from dashboard.services import duckdb_service, prediction_service


def test_predict_price_toyota_prius():
    """Verify inference for a high-volume Cambodian hybrid."""
    res = prediction_service.predict_price(
        vehicle_brand="Toyota",
        vehicle_model="Prius",
        vehicle_year=2010,
        vehicle_body_type="Hatchback",
        vehicle_fuel_type="Hybrid",
        is_plate_number=1,
        has_full_option=1,
    )
    assert "fair_price" in res
    assert "low_range" in res
    assert "high_range" in res
    assert res["low_range"] < res["fair_price"] < res["high_range"]
    # 2010 Prius should reasonably fall between $8,000 and $22,000 USD
    assert 8000 <= res["fair_price"] <= 22000


def test_predict_price_lexus_rx():
    """Verify inference for luxury SUV with tax paper."""
    res = prediction_service.predict_price(
        vehicle_brand="Lexus",
        vehicle_model="RX350",
        vehicle_year=2015,
        vehicle_body_type="SUV",
        vehicle_fuel_type="Gasoline",
        is_plate_number=0,
        has_full_option=1,
    )
    assert 20000 <= res["fair_price"] <= 85000
    assert res["low_range"] == round(res["fair_price"] * (1.0 - 0.143), -1)
    assert res["high_range"] == round(res["fair_price"] * (1.0 + 0.143), -1)


def test_explain_prediction_shap():
    """Verify SHAP explainability returns expected structure and feature attributions."""
    xai = prediction_service.explain_prediction(
        vehicle_brand="Toyota",
        vehicle_model="Camry",
        vehicle_year=2018,
        vehicle_body_type="Sedan",
        vehicle_fuel_type="Gasoline",
        is_plate_number=1,
        has_full_option=0,
    )
    assert "fair_price_usd" in xai
    assert "contributions" in xai
    assert len(xai["contributions"]) > 0
    for item in xai["contributions"]:
        assert "feature" in item
        assert "impact_usd" in item


def test_compare_to_market():
    """Verify market comparison calculations."""
    comp = prediction_service.compare_to_market(
        vehicle_brand="Toyota",
        vehicle_model="Prius",
        predicted_price=14500.0,
    )
    assert "market_median" in comp
    assert "diff_usd" in comp
    assert "position" in comp
    assert "pos_badge" in comp


def test_duckdb_service_kpis():
    """Verify DuckDB analytical KPI query."""
    kpis = duckdb_service.get_market_kpis()
    assert kpis["total_listings"] > 0
    assert kpis["avg_price"] > 0
    assert kpis["median_price"] > 0
    assert kpis["unique_brands"] > 0


def test_duckdb_service_brand_hierarchy():
    """Verify cascading brand-model hierarchy."""
    hierarchy = duckdb_service.get_brand_model_options()
    assert isinstance(hierarchy, dict)
    assert len(hierarchy) > 0
    assert "Toyota" in hierarchy
    assert len(hierarchy["Toyota"]) > 0


def test_get_model_feature_importances():
    """Verify real champion model feature importances extraction."""
    df = prediction_service.get_model_feature_importances()
    assert not df.empty
    assert "Feature" in df.columns
    assert "Importance" in df.columns
    assert "Impact" in df.columns
    assert (df["Importance"] > 0).all()
    assert pytest.approx(df["Importance"].sum(), 0.05) == 1.0

