# tests/test_parsers.py — Unit tests for src/parsers.py

import pytest
from src.parsers import extract_brand_model, parse_mileage


class TestExtractBrandModel:
    """Tests for brand/model extraction from listing titles."""

    def test_basic_brand_and_model(self):
        brand, model = extract_brand_model("Toyota Camry used good condition")
        assert brand == "Toyota"
        assert model == "Camry"

    def test_year_not_leaked_into_model(self):
        """Fix #2: year digits must NOT appear in the model field."""
        brand, model = extract_brand_model("Toyota Camry 2019 used")
        assert brand == "Toyota"
        assert model == "Camry"          # NOT "Camry 2019"

    def test_year_only_title(self):
        brand, model = extract_brand_model("Honda 2021 for sale")
        assert brand == "Honda"
        assert model is None             # no model word after year

    def test_khmer_prefix(self):
        """Khmer Unicode characters before the brand should not break parsing."""
        brand, model = extract_brand_model("ឡានHonda Civic 2021")
        assert brand == "Honda"
        assert model == "Civic"

    def test_khmer_brand_name(self):
        """Khmer script brand names like តូយ៉ូតា should map to canonical English names."""
        brand, model = extract_brand_model("ឡានតូយ៉ូតា Prius 2010 ពណ៌ស")
        assert brand == "Toyota"
        assert model == "Prius"

    def test_multi_word_brand(self):
        brand, model = extract_brand_model("Mercedes-Benz E300 2020 for sale")
        assert brand == "Mercedes-Benz"
        assert model == "E300"

    def test_benz_alias(self):
        brand, model = extract_brand_model("Benz C300 2018 full option")
        assert brand == "Mercedes-Benz"
        assert model == "C300"

    def test_land_rover(self):
        brand, model = extract_brand_model("Land Rover Defender 2022")
        assert brand == "Land Rover"
        assert model == "Defender"

    def test_range_rover(self):
        brand, model = extract_brand_model("Range Rover Sport 2021 HSE")
        assert brand == "Land Rover"
        assert model == "Range Rover Sport"

    def test_stop_word_halts_model(self):
        brand, model = extract_brand_model("Kia for sale cheap")
        assert brand == "Kia"
        assert model is None

    def test_keyword_stop_word(self):
        brand, model = extract_brand_model("Mazda automatic 2020")
        assert brand == "Mazda"
        assert model is None             # "automatic" is a stop word

    def test_unknown_brand(self):
        brand, model = extract_brand_model("Car for sale good condition")
        assert brand is None
        assert model is None

    def test_empty_title(self):
        brand, model = extract_brand_model("")
        assert brand is None
        assert model is None

    def test_none_title(self):
        brand, model = extract_brand_model(None)
        assert brand is None
        assert model is None

    def test_case_insensitive(self):
        brand, model = extract_brand_model("TOYOTA CAMRY 2020")
        assert brand == "Toyota"         # canonical casing preserved
        assert model == "Camry"

    def test_multi_word_model(self):
        brand, model = extract_brand_model("Toyota Land Cruiser 2022 used")
        assert brand == "Toyota"
        assert model == "Land Cruiser"

    def test_chinese_brand(self):
        brand, model = extract_brand_model("BYD Atto 3 2023 new")
        assert brand == "BYD"
        assert model == "Atto 3"         # "Atto 3" is the full model name

    def test_inferred_brand_from_distinct_model(self):
        """When brand is omitted in title, infer from famous model name."""
        brand, model = extract_brand_model("Prius 2010 Option 4 Solar ក្រដាសពន្ធ")
        assert brand == "Toyota"
        assert model == "Prius"

        brand2, model2 = extract_brand_model("RX350 2016 F-Sport full option")
        assert brand2 == "Lexus"
        assert model2 == "RX350"

        brand3, model3 = extract_brand_model("Wildtrak 2022 Bi-Turbo Diesel")
        assert brand3 == "Ford"
        assert model3 == "Ranger Wildtrak"


class TestParseMileage:
    """Tests for mileage string parsing."""

    def test_plain_integer(self):
        assert parse_mileage("150000") == 150000

    def test_comma_separated(self):
        assert parse_mileage("150,000") == 150000

    def test_with_km_suffix(self):
        assert parse_mileage("150000 km") == 150000

    def test_k_shorthand(self):
        assert parse_mileage("150k") == 150000

    def test_k_shorthand_decimal(self):
        assert parse_mileage("85.5k") == 85500

    def test_none_input(self):
        assert parse_mileage(None) is None

    def test_unparseable_string(self):
        assert parse_mileage("unknown") is None

    def test_integer_input(self):
        assert parse_mileage(80000) == 80000
