"""
dashboard/views/__init__.py
============================
Exports view modules for the streamlined 4-page dashboard:
  1. executive_pulse          — Overview & Collection
  2. cleaning_transformation  — Cleaning & Transformation
  3. data_quality_monitoring  — Data Quality & Anomalies
  4. feature_profiling        — Feature Profiling
"""

from dashboard.views import (
    cleaning_transformation,
    data_quality_monitoring,
    executive_pulse,
    feature_profiling,
)

__all__ = [
    "executive_pulse",
    "cleaning_transformation",
    "data_quality_monitoring",
    "feature_profiling",
]
