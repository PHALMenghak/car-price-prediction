# tests/test_pipeline.py — Unit tests for pipeline/extract_load.py

import json
import os
import pytest
from src.schemas import AdListingModel
from pipeline.extract_load import run, _compute_quality_metrics


def test_compute_quality_metrics():
    sample = [
        AdListingModel(
            listing_id="1",
            listing_title="Toyota Prius 2012",
            price=12000.0,
            vehicle_brand="Toyota",
            vehicle_model="Prius",
            vehicle_model_year=2012,
            province="Phnom Penh",
            vehicle_mileage_km=120000,
            vehicle_fuel_type="Hybrid",
            vehicle_transmission="Automatic",
        ),
        AdListingModel(
            listing_id="2",
            listing_title="Ford Ranger 2020",
            price=28000.0,
            vehicle_brand="Ford",
            vehicle_model="Ranger",
            vehicle_model_year=2020,
            province="Siem Reap",
            vehicle_mileage_km=None,
            vehicle_fuel_type="Diesel",
            vehicle_transmission=None,
        ),
    ]

    metrics = _compute_quality_metrics(sample, total_historical_unique=2)
    assert metrics["batch_size"] == 2
    assert metrics["price_coverage_pct"] == 100.0
    assert metrics["brand_coverage_pct"] == 100.0
    assert metrics["mileage_coverage_pct"] == 50.0
    assert metrics["transmission_coverage_pct"] == 50.0
    assert metrics["cumulative_unique_ids"] == 2


def test_pipeline_run_end_to_end(tmp_path, monkeypatch):
    """Test running the EL pipeline end-to-end with a mocked Khmer24Client."""
    temp_dir = str(tmp_path)

    sample = [
        AdListingModel(
            listing_id="501",
            listing_title="Toyota Camry 2018",
            price=25000.0,
            vehicle_brand="Toyota",
            vehicle_model="Camry",
            vehicle_model_year=2018,
            province="Phnom Penh",
        ),
        AdListingModel(
            listing_id="502",
            listing_title="Lexus RX350 2015",
            price=36000.0,
            vehicle_brand="Lexus",
            vehicle_model="RX350",
            vehicle_model_year=2015,
            province="Kandal",
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

    # Verify manifest creation
    manifest_path = os.path.join(temp_dir, "ingestion_manifest.json")
    assert os.path.exists(manifest_path)
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["batch_total"] == 2
    assert manifest["new_ids_count"] == 2
    assert manifest["quality_metrics"]["brand_coverage_pct"] == 100.0
