# tests/test_backfill.py — Unit tests for pipeline/backfill_details.py

import os
from pathlib import Path
import pandas as pd
import pytest

from pipeline.backfill_details import (
    apply_cache_to_parquets,
    extract_specs_from_detail,
    load_cache,
    save_cache,
    scan_missing_listings,
)


def test_extract_specs_from_detail_nuxt():
    detail = {
        "_source": "nuxt_html",
        "resolved_specs": {
            "transmission": "ស្វ័យប្រវត្តិ",
            "engine-type": "សាំង",
            "color": "ពណ៌ស",
            "mileage": "45,000 km",
            "engine-size": "3.5L",
            "car-year": 2018,
            "tax-type": "Plate Number",
            "condition": "Used",
        },
    }
    specs = extract_specs_from_detail(detail)
    assert specs["vehicle_transmission"] == "Automatic"
    assert specs["vehicle_fuel_type"] == "Petrol"
    assert specs["vehicle_color"] == "White"
    assert specs["vehicle_mileage_km"] == 45000
    assert specs["vehicle_engine_cc"] == 3500
    assert specs["vehicle_model_year"] == 2018
    assert specs["vehicle_tax_type"] == "Plate Number"
    assert specs["vehicle_condition"] == "Used"


def test_extract_specs_from_detail_legacy():
    detail = {
        "specs": [
            {"field": "transmission", "value": "Manual"},
            {"field": "fuel-type", "value": "Diesel"},
            {"field": "color", "value": "Black"},
            {"field": "mileage", "value": "80,000"},
            {"field": "engine-size", "value": "2.8L"},
        ]
    }
    specs = extract_specs_from_detail(detail)
    assert specs["vehicle_transmission"] == "Manual"
    assert specs["vehicle_fuel_type"] == "Diesel"
    assert specs["vehicle_color"] == "Black"
    assert specs["vehicle_mileage_km"] == 80000
    assert specs["vehicle_engine_cc"] == 2800


def test_apply_cache_and_scan(tmp_path):
    temp_dir = str(tmp_path)
    df = pd.DataFrame([
        {
            "listing_id": "1001",
            "listing_title": "Toyota Prius 2010",
            "price": 12000.0,
            "vehicle_transmission": None,
            "vehicle_fuel_type": None,
            "vehicle_color": None,
            "vehicle_mileage_km": None,
        },
        {
            "listing_id": "1002",
            "listing_title": "Ford Ranger 2020",
            "price": 28000.0,
            "vehicle_transmission": "Automatic",
            "vehicle_fuel_type": "Diesel",
            "vehicle_color": "White",
            "vehicle_mileage_km": 50000,
        },
    ])
    pfile = os.path.join(temp_dir, "cars_2026-08-17.parquet")
    df.to_parquet(pfile, index=False)

    missing, occ = scan_missing_listings(temp_dir)
    assert "1001" in missing
    assert "1002" not in missing

    cache = {
        "1001": {
            "status": "ok",
            "specs": {
                "vehicle_transmission": "Automatic",
                "vehicle_fuel_type": "Hybrid",
                "vehicle_color": "Silver",
                "vehicle_mileage_km": 110000,
                "vehicle_engine_cc": 1800,
            },
        }
    }

    cache_file = Path(temp_dir) / ".backfill_cache.json"
    save_cache(cache, cache_file)
    loaded = load_cache(cache_file)
    assert loaded["1001"]["status"] == "ok"

    res = apply_cache_to_parquets(temp_dir, cache)
    assert res["total_updated_rows"] == 1

    updated_df = pd.read_parquet(pfile)
    row_1001 = updated_df[updated_df["listing_id"] == "1001"].iloc[0]
    assert row_1001["vehicle_transmission"] == "Automatic"
    assert row_1001["vehicle_fuel_type"] == "Hybrid"
    assert row_1001["vehicle_color"] == "Silver"
    assert row_1001["vehicle_mileage_km"] == 110000
