import json
import os
import pytest
import pandas as pd
from src.schemas import AdListingModel
from src.storage import (
    get_historical_ids,
    load_all_parquet,
    load_from_parquet,
    save_run_manifest,
    save_sample_csv,
    save_to_parquet,
)


def test_storage_parquet_roundtrip(tmp_path):
    sample = [
        AdListingModel(
            listing_id="101",
            listing_title="Toyota Prius 2012",
            price=13500.0,
            seller_phones=["012345678", "098765432"],
            images=["https://img.khmer24.com/1.jpg", "https://img.khmer24.com/2.jpg"],
            description="Good car, original paint",
            seller_avatar="https://img.khmer24.com/avatar.jpg",
            is_saved=True,
            raw_specs={"fuel": "Hybrid", "car-year": 2012},
        ),
        AdListingModel(
            listing_id="102",
            listing_title="Ford Ranger 2021",
            price=32000.0,
            seller_phones=[],
            images=[],
            description=None,
            raw_specs=None,
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
    assert loaded_df.iloc[0]["description"] == "Good car, original paint"
    assert loaded_df.iloc[0]["is_saved"] == True

    # Test load_all_parquet
    combined_df = load_all_parquet(directory=temp_dir)
    assert len(combined_df) == 2

    # Test get_historical_ids
    hist_ids = get_historical_ids(directory=temp_dir)
    assert hist_ids == {"101", "102"}


def test_save_sample_csv(tmp_path):
    temp_dir = str(tmp_path)
    sample = [
        AdListingModel(
            listing_id=f"20{i}",
            listing_title=f"Car model {i}",
            price=10000.0 + i * 500,
        )
        for i in range(40)
    ]
    csv_path = save_sample_csv(sample, n=30, directory=temp_dir)
    assert os.path.exists(csv_path)
    df = pd.read_csv(csv_path)
    assert len(df) == 30


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

