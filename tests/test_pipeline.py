# tests/test_pipeline.py — Unit tests for pipeline/extract_load.py

import json
import os
import pytest
from src.schemas import RawCarListing
from pipeline.extract_load import run, _compute_quality_metrics


def test_compute_quality_metrics():
    sample = [
        RawCarListing(
            listing_id="1",
            raw_title="Toyota Prius 2012",
            raw_price="12000.0",
            raw_spec_brand="Toyota",
            raw_spec_model="Prius",
            raw_spec_year="2012",
            raw_province="Phnom Penh",
            raw_spec_mileage="120000",
            raw_spec_fuel_type="Hybrid",
            raw_spec_transmission="Automatic",
            has_detail=True,
        ),
        RawCarListing(
            listing_id="2",
            raw_title="Ford Ranger 2020",
            raw_price="28000.0",
            raw_spec_brand="Ford",
            raw_spec_model="Ranger",
            raw_spec_year="2020",
            raw_province="Siem Reap",
            raw_spec_mileage=None,
            raw_spec_fuel_type="Diesel",
            raw_spec_transmission=None,
            has_detail=False,
        ),
    ]

    metrics = _compute_quality_metrics(sample, total_historical_unique=2)
    assert metrics["batch_size"] == 2
    assert metrics["price_coverage_pct"] == 100.0
    assert metrics["brand_coverage_pct"] == 100.0
    assert metrics["mileage_coverage_pct"] == 50.0
    assert metrics["transmission_coverage_pct"] == 50.0
    assert metrics["detail_enrich_pct"] == 50.0
    assert metrics["cumulative_unique_ids"] == 2


def test_pipeline_run_end_to_end(tmp_path, monkeypatch):
    """Test running the EL pipeline end-to-end with a mocked Khmer24Client."""
    temp_dir = str(tmp_path)

    sample = [
        RawCarListing(
            listing_id="501",
            raw_title="Toyota Camry 2018",
            raw_price="25000.0",
            raw_spec_brand="Toyota",
            raw_spec_model="Camry",
            raw_spec_year="2018",
            raw_province="Phnom Penh",
        ),
        RawCarListing(
            listing_id="502",
            raw_title="Lexus RX350 2015",
            raw_price="36000.0",
            raw_spec_brand="Lexus",
            raw_spec_model="RX350",
            raw_spec_year="2015",
            raw_province="Kandal",
        ),
    ]

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def scrape_category_feed(self, *args, **kwargs):
            return sample

    monkeypatch.setattr("pipeline.extract_load.Khmer24Client", MockClient)

    count = run(
        category="cars-for-sale",
        province=None,
        max_pages=1,
        scrape_mode="feed_window",
        enrich_details=False,
        output_dir=temp_dir,
    )

    assert count == 2

    manifest_path = os.path.join(temp_dir, "ingestion_manifest.json")
    assert os.path.exists(manifest_path)
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["batch_total"] == 2
