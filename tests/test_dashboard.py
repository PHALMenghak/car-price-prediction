"""
tests/test_dashboard.py
=======================
Unit tests for CARIQ Dashboard: UI configurations, SLA gating, active views,
DuckDB metadata loader, and executive audit report generation.
"""

from __future__ import annotations

import pytest

from dashboard import config
from dashboard.services import duckdb_service
from dashboard.views import (
    data_quality,
    market_overview,
    model_insights,
    price_prediction,
    vehicle_explorer,
)


def test_config_weights_and_thresholds():
    """Verify DHI weights, SLA defaults, and threshold formatting."""
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


def test_evaluate_sla_gates():
    """Verify SLA evaluation engine under passing and breach scenarios."""
    # Scenario 1: All passing
    gates = config.evaluate_sla_gates(
        dhi_score=97.5,
        total=1500,
        freshness_hrs=4.0,
        quar_pct=0.5,
        dbt_status={"available": True, "failed": 0, "passed": 10, "total": 10},
        enrich_pct=99.0,
    )
    assert len(gates) == 6
    assert all(g["passed"] for g in gates)

    # Scenario 2: Freshness breach
    gates_stale = config.evaluate_sla_gates(
        dhi_score=97.5,
        total=1500,
        freshness_hrs=50.0,
        quar_pct=0.5,
        dbt_status={"available": True, "failed": 0},
        enrich_pct=90.0,
    )
    fresh_gate = next(g for g in gates_stale if g["id"] == "freshness")
    assert not fresh_gate["passed"]
    assert fresh_gate["critical"] is True


def test_views_import_and_catalog():
    """Verify that all 5 active production views expose callable render contracts."""
    views = [market_overview, vehicle_explorer, price_prediction, model_insights, data_quality]
    for v in views:
        assert hasattr(v, "render")
        assert callable(v.render)


def test_manifest_and_dates_loader():
    """Verify manifest and partition date loading from duckdb_service."""
    manifest = duckdb_service.load_manifest()
    assert isinstance(manifest, dict)

    dates = duckdb_service.load_available_dates()
    assert isinstance(dates, list)
    if dates:
        assert len(dates) > 0
        # Verify dates are sorted descending
        assert dates == sorted(dates, reverse=True)


def test_generate_markdown_report():
    """Verify executive markdown report generation."""
    report = duckdb_service.generate_markdown_report()
    assert isinstance(report, str)
    assert "Data Health Index" in report
    assert "Analysis-Ready" in report
    assert "Automated dbt Contract Tests" in report
