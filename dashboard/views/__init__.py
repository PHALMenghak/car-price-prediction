"""
dashboard/views/__init__.py
============================
Exports view modules for the streamlined dashboard:
  1. executive_pulse          — Overview & Collection
  2. data_quality_monitoring  — Data Quality & Lineage
  3. market_intelligence      — Market Dynamics & Pricing
  4. feature_profiling        — Feature Profiling
"""

from dashboard.views import (
    data_quality_monitoring,
    executive_pulse,
    feature_profiling,
    market_intelligence,
)

__all__ = [
    "executive_pulse",
    "data_quality_monitoring",
    "market_intelligence",
    "feature_profiling",
]
