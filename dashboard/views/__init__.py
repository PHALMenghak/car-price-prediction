"""
dashboard/views/__init__.py
============================
Core application views for CARIQ Automotive Intelligence Platform:
  1. market_overview   — Page 1: Used Car Market Overview (KPIs, distributions, brands, vintages)
  2. vehicle_explorer  — Page 2: Vehicle Explorer (Faceted search, data table, detail valuation card)
  3. price_prediction  — Page 3: AI Vehicle Price Predictor (ML inference, market deltas, SHAP XAI)
  4. model_insights    — Page 4: Model Performance & Explainability (Tournament, residuals, metrics)
  5. data_quality      — Page 5: Data Quality & Pipeline Monitoring (DAG status, missingness audit)
"""

from dashboard.views import (
    data_quality,
    market_overview,
    model_insights,
    price_prediction,
    vehicle_explorer,
)

__all__ = [
    "market_overview",
    "vehicle_explorer",
    "price_prediction",
    "model_insights",
    "data_quality",
]

