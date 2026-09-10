"""
dashboard/views/__init__.py
============================
Exports all dashboard view modules for the 7-page navigation:
  1. executive_pulse          — Overview
  2. collection_monitoring    — Collection Monitoring
  3. cleaning_transformation  — Cleaning & Transformation
  4. data_quality_monitoring  — Data Quality
  5. data_anomalies           — Data Anomalies
  6. feature_profiling        — Feature Profiling
  7. silver_readiness         — Silver Readiness
"""

from dashboard.views import (
    collection_monitoring,
    cleaning_transformation,
    data_anomalies,
    data_quality_monitoring,
    executive_pulse,
    feature_profiling,
    pipeline_monitoring,
    silver_readiness,
)

__all__ = [
    "executive_pulse",
    "collection_monitoring",
    "cleaning_transformation",
    "data_quality_monitoring",
    "data_anomalies",
    "feature_profiling",
    "silver_readiness",
    "pipeline_monitoring",
]
