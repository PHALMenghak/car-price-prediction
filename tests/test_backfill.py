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
            "raw_currency": "USD",
            "raw_province": "Phnom Penh",
            "seller_name": "Seller 1",
            "raw_description": None,
            "has_detail": False,
            "listing_url": "https://www.khmer24.com/post-adid-1001",
        },
        {
            "listing_id": "1002",
            "raw_title": "Lexus RX300 2002",
            "raw_price": "11500.0",
            "raw_currency": "USD",
            "raw_province": "Kandal",
            "seller_name": "Seller 2",
            "raw_description": None,
            "has_detail": False,
            "listing_url": "https://www.khmer24.com/post-adid-1002",
        },
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
                {"description": f"Backfilled description for {listing_id}", "specs": {"engine-size": "1.8L"}},
                "rest_api",
                '{"description": "Backfilled description"}',
            )

    monkeypatch.setattr("pipeline.backfill_details.Khmer24Client", MockClient)

    enriched = backfill_bronze_file(pfile, workers=2)
    assert enriched == 2

    updated_df = pd.read_parquet(pfile)
    assert updated_df.iloc[0]["raw_description"] == "Backfilled description for 1001"
    assert updated_df.iloc[0]["raw_province"] == "Phnom Penh"
    assert updated_df.iloc[0]["seller_name"] == "Seller 1"
    assert updated_df.iloc[0]["has_detail"] is True or updated_df.iloc[0]["has_detail"] == 1
    assert updated_df.iloc[1]["raw_description"] == "Backfilled description for 1002"
    assert updated_df.iloc[1]["raw_province"] == "Kandal"

