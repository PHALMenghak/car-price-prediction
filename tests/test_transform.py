# tests/test_transform.py — Unit tests for pipeline/transform.py

import os
import sys
import tempfile

import numpy as np
import pandas as pd
import pytest

# Ensure project root is on sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from pipeline.transform import (
    CHINESE_EV_BRANDS,
    CURRENT_YEAR,
    LUXURY_BRANDS,
    POPULAR_BRANDS,
    apply_sanity_filters,
    deduplicate_snapshots,
    engineer_features,
    impute_missing_values,
    re_extract_brands,
    run,
    select_ml_features,
    split_train_test,
)


# ── Helper ────────────────────────────────────────────────────────────────────

def _make_test_df(n=5, **overrides):
    """Create a minimal test DataFrame mimicking raw Parquet schema."""
    data = {
        "listing_id": [str(i) for i in range(n)],
        "listing_title": ["Toyota Camry 2020 full option"] * n,
        "price": [25000.0] * n,
        "currency": ["USD"] * n,
        "vehicle_brand": ["Toyota"] * n,
        "vehicle_model": ["Camry"] * n,
        "vehicle_model_year": [2020] * n,
        "vehicle_condition": ["used"] * n,
        "vehicle_tax_type": ["Tax Paper"] * n,
        "vehicle_transmission": [None] * n,
        "vehicle_fuel_type": [None] * n,
        "vehicle_mileage_km": [None] * n,
        "vehicle_engine_cc": [None] * n,
        "vehicle_color": [None] * n,
        "province": ["Phnom Penh"] * n,
        "seller_type": ["individual"] * n,
        "view_count": [100] * n,
        "posted_at": ["2026-08-17T00:00:00+00:00"] * n,
        "scraped_at": ["2026-08-19T00:00:00+00:00"] * n,
        "renewed_at": ["2026-08-18T00:00:00+00:00"] * n,
        "seller_id": ["s1"] * n,
        "seller_name": ["Test Seller"] * n,
        "seller_username": ["test"] * n,
        "seller_phones": ["[]"] * n,
        "thumbnail_url": [None] * n,
        "listing_url": ["https://example.com"] * n,
        "raw_specs": ["{}"] * n,
        "discount_price": [None] * n,
        "is_premium": [None] * n,
        "category": ["Cars"] * n,
        "category_slug": ["cars-for-sale"] * n,
        "province_slug": ["phnom-penh"] * n,
        "district": [None] * n,
        "location_full": ["Phnom Penh"] * n,
    }
    data.update(overrides)
    return pd.DataFrame(data)


# ═══════════════════════════════════════════════════════════════════════════════
#  TestDeduplicateSnapshots
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeduplicateSnapshots:
    def test_keeps_latest_snapshot(self):
        df = _make_test_df(
            n=2,
            listing_id=["A", "A"],
            price=[10000, 12000],
            scraped_at=["2026-08-17T00:00:00+00:00", "2026-08-19T00:00:00+00:00"],
        )
        result = deduplicate_snapshots(df)
        assert len(result) == 1
        assert result.iloc[0]["price"] == 12000

    def test_extracts_historical_features(self):
        df = _make_test_df(
            n=2,
            listing_id=["A", "A"],
            price=[15000, 12000],
            scraped_at=["2026-08-17T00:00:00+00:00", "2026-08-19T00:00:00+00:00"],
            posted_at=["2026-08-15T00:00:00+00:00", "2026-08-15T00:00:00+00:00"],
        )
        result = deduplicate_snapshots(df)
        assert result.iloc[0]["days_on_market"] >= 0
        assert result.iloc[0]["price_drop_amount"] == 3000
        assert result.iloc[0]["has_price_drop"] == 1

    def test_single_snapshot_no_change(self):
        df = _make_test_df(n=1, listing_id=["A"])
        result = deduplicate_snapshots(df)
        assert len(result) == 1
        assert result.iloc[0]["price_drop_amount"] == 0
        assert result.iloc[0]["has_price_drop"] == 0

    def test_multiple_listings_preserved(self):
        df = _make_test_df(
            n=4,
            listing_id=["A", "A", "B", "B"],
            price=[10000, 12000, 20000, 18000],
            scraped_at=[
                "2026-08-17T00:00:00+00:00", "2026-08-19T00:00:00+00:00",
                "2026-08-17T00:00:00+00:00", "2026-08-19T00:00:00+00:00",
            ],
        )
        result = deduplicate_snapshots(df)
        assert len(result) == 2
        assert set(result["listing_id"]) == {"A", "B"}


# ═══════════════════════════════════════════════════════════════════════════════
#  TestApplySanityFilters
# ═══════════════════════════════════════════════════════════════════════════════

class TestApplySanityFilters:
    def test_removes_low_price(self):
        df = _make_test_df(n=2, listing_id=["A", "B"], price=[100, 5000])
        result = apply_sanity_filters(df)
        assert len(result) == 1
        assert result.iloc[0]["price"] == 5000

    def test_removes_high_price(self):
        df = _make_test_df(n=2, listing_id=["A", "B"], price=[400000, 50000])
        result = apply_sanity_filters(df)
        assert len(result) == 1
        assert result.iloc[0]["price"] == 50000

    def test_drops_null_price(self):
        df = _make_test_df(n=2, listing_id=["A", "B"], price=[None, 25000])
        result = apply_sanity_filters(df)
        assert len(result) == 1

    def test_year_bounds(self):
        df = _make_test_df(
            n=3,
            listing_id=["A", "B", "C"],
            price=[25000, 25000, 25000],
            vehicle_model_year=[1980, 2020, None],
        )
        result = apply_sanity_filters(df)
        # 1980 is dropped (< 1990), 2020 kept, None kept
        assert len(result) == 2

    def test_mileage_clamped(self):
        df = _make_test_df(
            n=2,
            listing_id=["A", "B"],
            vehicle_mileage_km=[600000, 50000],
        )
        result = apply_sanity_filters(df)
        assert pd.isna(result.loc[result["listing_id"] == "A", "vehicle_mileage_km"].iloc[0])
        assert result.loc[result["listing_id"] == "B", "vehicle_mileage_km"].iloc[0] == 50000

    def test_engine_cc_clamped(self):
        df = _make_test_df(
            n=2,
            listing_id=["A", "B"],
            vehicle_engine_cc=[10000, 2000],
        )
        result = apply_sanity_filters(df)
        assert pd.isna(result.loc[result["listing_id"] == "A", "vehicle_engine_cc"].iloc[0])
        assert result.loc[result["listing_id"] == "B", "vehicle_engine_cc"].iloc[0] == 2000


# ═══════════════════════════════════════════════════════════════════════════════
#  TestReExtractBrands
# ═══════════════════════════════════════════════════════════════════════════════

class TestReExtractBrands:
    def test_fills_missing_brand(self):
        df = _make_test_df(
            n=1,
            listing_title=["Toyota Camry 2020 full option"],
            vehicle_brand=[None],
            vehicle_model=[None],
        )
        result = re_extract_brands(df)
        assert result.iloc[0]["vehicle_brand"] == "Toyota"
        assert result.iloc[0]["vehicle_model"] == "Camry"

    def test_preserves_existing_brand(self):
        df = _make_test_df(
            n=1,
            listing_title=["Honda Civic 2021"],
            vehicle_brand=["Honda"],
            vehicle_model=["Civic"],
        )
        result = re_extract_brands(df)
        assert result.iloc[0]["vehicle_brand"] == "Honda"
        assert result.iloc[0]["vehicle_model"] == "Civic"

    def test_fills_khmer_title(self):
        df = _make_test_df(
            n=1,
            listing_title=["ឡានតូយ៉ូតា Camry 2007"],
            vehicle_brand=[None],
            vehicle_model=[None],
        )
        result = re_extract_brands(df)
        assert result.iloc[0]["vehicle_brand"] == "Toyota"


# ═══════════════════════════════════════════════════════════════════════════════
#  TestImputeMissingValues
# ═══════════════════════════════════════════════════════════════════════════════

class TestImputeMissingValues:
    def test_fills_unknown_brand(self):
        df = _make_test_df(n=1, vehicle_brand=[None])
        result = impute_missing_values(df)
        assert result.iloc[0]["vehicle_brand"] == "Unknown"

    def test_fills_default_condition(self):
        df = _make_test_df(n=1, vehicle_condition=[None])
        result = impute_missing_values(df)
        assert result.iloc[0]["vehicle_condition"] == "used"

    def test_fills_default_province(self):
        df = _make_test_df(n=1, province=[None])
        result = impute_missing_values(df)
        assert result.iloc[0]["province"] == "Phnom Penh"

    def test_mileage_missing_indicator(self):
        df = _make_test_df(n=2, vehicle_mileage_km=[None, 50000])
        result = impute_missing_values(df)
        assert result.iloc[0]["is_mileage_missing"] == 1
        assert result.iloc[1]["is_mileage_missing"] == 0

    def test_fills_transmission_unknown(self):
        df = _make_test_df(n=1, vehicle_transmission=[None])
        result = impute_missing_values(df)
        assert result.iloc[0]["vehicle_transmission"] == "Unknown"

    def test_fills_fuel_type_unknown(self):
        df = _make_test_df(n=1, vehicle_fuel_type=[None])
        result = impute_missing_values(df)
        assert result.iloc[0]["vehicle_fuel_type"] == "Unknown"


# ═══════════════════════════════════════════════════════════════════════════════
#  TestEngineerFeatures
# ═══════════════════════════════════════════════════════════════════════════════

class TestEngineerFeatures:
    def _prepare_df(self, **overrides):
        """Create a df that has already passed through imputation."""
        df = _make_test_df(n=1, **overrides)
        df["is_mileage_missing"] = 0
        df["days_on_market"] = 5.0
        df["initial_price"] = df["price"]
        df["price_drop_amount"] = 0.0
        df["has_price_drop"] = 0
        df["view_velocity"] = 20.0
        return df

    def test_vehicle_age(self):
        df = self._prepare_df(vehicle_model_year=[2020])
        result = engineer_features(df)
        assert result.iloc[0]["vehicle_age"] == CURRENT_YEAR - 2020

    def test_vehicle_age_squared(self):
        df = self._prepare_df(vehicle_model_year=[2020])
        result = engineer_features(df)
        expected_age = CURRENT_YEAR - 2020
        assert result.iloc[0]["vehicle_age_squared"] == expected_age ** 2

    def test_luxury_brand_flag(self):
        df = self._prepare_df(vehicle_brand=["Lexus"])
        result = engineer_features(df)
        assert result.iloc[0]["is_luxury_brand"] == 1

    def test_popular_brand_flag(self):
        df = self._prepare_df(vehicle_brand=["Toyota"])
        result = engineer_features(df)
        assert result.iloc[0]["is_popular_brand"] == 1

    def test_lexus_is_both_luxury_and_popular(self):
        df = self._prepare_df(vehicle_brand=["Lexus"])
        result = engineer_features(df)
        assert result.iloc[0]["is_luxury_brand"] == 1
        assert result.iloc[0]["is_popular_brand"] == 1

    def test_chinese_ev_brand_flag(self):
        df = self._prepare_df(vehicle_brand=["BYD"])
        result = engineer_features(df)
        assert result.iloc[0]["is_chinese_ev_brand"] == 1

    def test_location_tier_1(self):
        df = self._prepare_df(province=["Phnom Penh"])
        result = engineer_features(df)
        assert result.iloc[0]["location_tier"] == "Tier_1"

    def test_location_tier_2(self):
        df = self._prepare_df(province=["Siem Reap"])
        result = engineer_features(df)
        assert result.iloc[0]["location_tier"] == "Tier_2"

    def test_location_tier_3(self):
        df = self._prepare_df(province=["Prey Veng"])
        result = engineer_features(df)
        assert result.iloc[0]["location_tier"] == "Tier_3"

    def test_title_full_option_flag(self):
        df = self._prepare_df(listing_title=["Toyota Camry full option 2020"])
        result = engineer_features(df)
        assert result.iloc[0]["has_full_option"] == 1

    def test_title_urgent_sale_flag(self):
        df = self._prepare_df(listing_title=["Urgent sale Toyota 2020"])
        result = engineer_features(df)
        assert result.iloc[0]["is_urgent_sale"] == 1

    def test_log_price(self):
        df = self._prepare_df(price=[10000])
        result = engineer_features(df)
        assert np.isclose(result.iloc[0]["log_price"], np.log1p(10000))


# ═══════════════════════════════════════════════════════════════════════════════
#  TestSelectMLFeatures
# ═══════════════════════════════════════════════════════════════════════════════

class TestSelectMLFeatures:
    def test_returns_expected_columns(self):
        df = _make_test_df(n=1)
        # Add all the columns that would be present after engineering
        for col in [
            "is_mileage_missing", "vehicle_age", "vehicle_age_squared",
            "mileage_per_year", "log_price", "location_tier",
            "is_luxury_brand", "is_popular_brand", "is_chinese_ev_brand",
            "has_full_option", "has_sunroof", "has_leather", "has_camera",
            "is_urgent_sale", "days_on_market", "initial_price",
            "price_drop_amount", "has_price_drop", "view_velocity",
        ]:
            df[col] = 0
        result = select_ml_features(df)
        assert "listing_id" in result.columns
        assert "price" in result.columns
        assert "log_price" in result.columns
        assert "vehicle_brand" in result.columns
        # Non-ML columns should be excluded
        assert "raw_specs" not in result.columns
        assert "thumbnail_url" not in result.columns


# ═══════════════════════════════════════════════════════════════════════════════
#  TestSplitTrainTest
# ═══════════════════════════════════════════════════════════════════════════════

class TestSplitTrainTest:
    def test_split_ratio(self):
        df = _make_test_df(n=100, listing_id=[str(i) for i in range(100)])
        df["vehicle_brand"] = "Toyota"
        train, test = split_train_test(df, test_size=0.2, random_state=42)
        assert len(train) == 80
        assert len(test) == 20

    def test_no_listing_id_overlap(self):
        df = _make_test_df(n=50, listing_id=[str(i) for i in range(50)])
        df["vehicle_brand"] = "Toyota"
        train, test = split_train_test(df, test_size=0.2)
        train_ids = set(train["listing_id"])
        test_ids = set(test["listing_id"])
        assert len(train_ids & test_ids) == 0


# ═══════════════════════════════════════════════════════════════════════════════
#  TestRunPipeline (Integration)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRunPipeline:
    def test_run_end_to_end(self, tmp_path):
        """Create a synthetic Parquet, run the full pipeline, verify outputs."""
        # Create synthetic input data
        input_dir = str(tmp_path / "raw")
        output_dir = str(tmp_path / "processed")
        os.makedirs(input_dir, exist_ok=True)

        df = _make_test_df(
            n=30,
            listing_id=[str(i) for i in range(30)],
            price=[float(p) for p in range(5000, 35000, 1000)],
            vehicle_brand=(["Toyota"] * 10 + ["Lexus"] * 8 + ["Ford"] * 7 + ["BYD"] * 5),
            vehicle_model=(["Camry"] * 10 + ["RX350"] * 8 + ["Ranger"] * 7 + ["Atto 3"] * 5),
            vehicle_model_year=([2020] * 10 + [2018] * 8 + [2022] * 7 + [2024] * 5),
            province=(["Phnom Penh"] * 20 + ["Siem Reap"] * 5 + ["Battambang"] * 5),
        )
        df.to_parquet(os.path.join(input_dir, "cars_2026-08-19.parquet"), index=False)

        # Run pipeline
        result = run(input_dir=input_dir, output_dir=output_dir, test_size=0.2, random_state=42)

        # Verify result dict
        assert result["train_rows"] > 0
        assert result["test_rows"] > 0
        assert result["total_unique_listings"] == 30

        # Verify output files exist
        assert os.path.exists(os.path.join(output_dir, "cars_train.parquet"))
        assert os.path.exists(os.path.join(output_dir, "cars_test.parquet"))
        assert os.path.exists(os.path.join(output_dir, "preprocessing_manifest.json"))

        # Verify train + test row count matches total
        assert result["train_rows"] + result["test_rows"] == 30
