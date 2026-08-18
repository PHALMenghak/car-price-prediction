import os
import pytest
import pandas as pd
from src.schemas import AdListingModel
from src.storage import save_to_parquet, load_from_parquet, load_all_parquet


def test_storage_parquet_roundtrip(tmp_path):
    sample = [
        AdListingModel(
            listing_id="101",
            listing_title="Toyota Prius 2012",
            price=13500.0,
            seller_phones=["012345678", "098765432"],
            raw_specs={"fuel": "Hybrid", "car-year": 2012},
        ),
        AdListingModel(
            listing_id="102",
            listing_title="Ford Ranger 2021",
            price=32000.0,
            seller_phones=[],
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

    # Test load_all_parquet
    combined_df = load_all_parquet(directory=temp_dir)
    assert len(combined_df) == 2
