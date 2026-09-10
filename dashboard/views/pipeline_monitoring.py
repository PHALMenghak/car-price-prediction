"""
dashboard/views/pipeline_monitoring.py
========================================
Page 2 now maps to Collection Monitoring.
This module is retained for backward compatibility but redirects to collection_monitoring.
The original pipeline monitoring content is now split between:
  - collection_monitoring.py (Page 2)
  - cleaning_transformation.py (Page 3)
"""
# This file is kept for import compatibility.
# The active render() is in collection_monitoring.py and cleaning_transformation.py.

from dashboard.views.collection_monitoring import render

__all__ = ["render"]
