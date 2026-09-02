import json
import os
import pytest
import pandas as pd
from src.schemas import RawCarListing
from src.storage import (
    get_historical_ids,
    load_all_parquet,
    load_from_parquet,
    save_run_manifest,
    save_to_csv,
    save_to_parquet,
)


def test_storage_parquet_roundtrip(tmp_path):
    sample = [
        RawCarListing(
            listing_id="101",
            raw_title="Toyota Prius 2012",
            raw_price="13500.0",
            raw_spec_brand="Toyota",
            raw_spec_model="Prius",
            raw_spec_year="2012",
            seller_phones=["012345678", "098765432"],
            images=["https://img.khmer24.com/1.jpg", "https://img.khmer24.com/2.jpg"],
            raw_description="Good car, original paint",
            raw_feed_payload='{"id": 101, "title": "Toyota Prius 2012"}',
        ),
        RawCarListing(
            listing_id="102",
            raw_title="Ford Ranger 2021",
            raw_price="32000.0",
            raw_spec_brand="Ford",
            raw_spec_model="Ranger",
            raw_spec_year="2021",
            seller_phones=[],
            images=[],
            raw_description=None,
            raw_feed_payload=None,
        ),
    ]

    temp_dir = str(tmp_path)
    file_path = save_to_parquet(sample, "test_cars_v01.parquet", directory=temp_dir)
    assert os.path.exists(file_path)

    loaded_df = load_from_parquet("test_cars_v01.parquet", directory=temp_dir)
    assert len(loaded_df) == 2
    assert loaded_df["listing_id"].tolist() == ["101", "102"]
    assert loaded_df.iloc[0]["seller_phones"] == ["012345678", "098765432"]
    assert loaded_df.iloc[0]["images"] == ["https://img.khmer24.com/1.jpg", "https://img.khmer24.com/2.jpg"]
    assert loaded_df.iloc[0]["raw_description"] == "Good car, original paint"

    # Test load_all_parquet
    combined_df = load_all_parquet(directory=temp_dir)
    assert len(combined_df) == 2

    # Test get_historical_ids
    hist_ids = get_historical_ids(directory=temp_dir)
    assert "101" in hist_ids and "102" in hist_ids


def test_save_to_csv_full(tmp_path):
    temp_dir = str(tmp_path)
    sample = [
        RawCarListing(
            listing_id=f"20{i}",
            raw_title=f"Car model {i}",
            raw_price=str(10000.0 + i * 500),
        )
        for i in range(150)
    ]
    csv_path = save_to_csv(sample, filename="khmer24_cars.csv", directory=temp_dir)
    assert os.path.exists(csv_path)
    df = pd.read_csv(csv_path)
    # Verifies all 150 records from the run are saved (no downsampling)
    assert len(df) == 150


def test_save_run_manifest(tmp_path):
    temp_dir = str(tmp_path)
    manifest_data = {
        "timestamp": "2026-08-19T14:00:00Z",
        "batch_total": 60,
        "new_ids_count": 45,
        "cumulative_unique_ids": 1260,
    }
    manifest_path = save_run_manifest(manifest_data, directory=temp_dir)
    assert os.path.exists(manifest_path)
    with open(manifest_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["cumulative_unique_ids"] == 1260
