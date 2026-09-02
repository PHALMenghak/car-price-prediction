# tests/test_backfill.py — Unit tests for pipeline/backfill_details.py

import os
from pathlib import Path
import pandas as pd
import pytest

from src.client import Khmer24Client
from pipeline.backfill_details import backfill_bronze_file


def test_backfill_bronze_file(tmp_path, monkeypatch):
    temp_dir = str(tmp_path)
    df = pd.DataFrame([
        {
            "listing_id": "1001",
            "raw_title": "Toyota Prius 2012",
            "raw_price": "12000.0",
            "raw_description": None,
            "has_detail": False,
            "listing_url": "https://www.khmer24.com/post-adid-1001",
        }
    ])
    pfile = os.path.join(temp_dir, "cars_2026-08-17.parquet")
    df.to_parquet(pfile, index=False)

    class MockClient(Khmer24Client):
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def fetch_raw_post_detail(self, listing_id, slug=None):
            return (
                {"description": "Backfilled description", "specs": {"engine-size": "1.8L"}},
                "rest_api",
                '{"description": "Backfilled description"}',
            )

    monkeypatch.setattr("pipeline.backfill_details.Khmer24Client", MockClient)

    enriched = backfill_bronze_file(pfile)
    assert enriched == 1

    updated_df = pd.read_parquet(pfile)
    assert updated_df.iloc[0]["raw_description"] == "Backfilled description"
