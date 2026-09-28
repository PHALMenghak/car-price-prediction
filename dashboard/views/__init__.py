"""
dashboard/views/__init__.py
============================
Exports view modules for CARIQ:
  1. executive_pulse          — Executive Overview
  2. pipeline                 — Pipeline & Ingestion Observability
  3. data_quality_monitoring  — Data Quality & Lineage
  4. market_intelligence      — Market Analytics & Dynamics
  5. feature_profiling        — Feature Exploration
  6. ml_readiness             — ML Readiness & Governance
"""

from dashboard.views import (
    data_quality_monitoring,
    executive_pulse,
    feature_profiling,
    market_intelligence,
    ml_readiness,
    pipeline,
)

__all__ = [
    "executive_pulse",
    "pipeline",
    "data_quality_monitoring",
    "market_intelligence",
    "feature_profiling",
    "ml_readiness",
]
