# tests/test_parsers.py — Unit tests for src/parsers.py

import pytest
from src.parsers import (
    clean_title,
    extract_brand_model,
    parse_engine_cc,
    parse_mileage,
    normalize_transmission,
    normalize_fuel_type,
    normalize_color,
)


class TestCleanTitle:
    """Tests for clean_title string normalization."""

    def test_strip_zero_width_chars(self):
        title = "P\u200blugin 2017 Option 2"
        assert clean_title(title) == "Plugin 2017 Option 2"

    def test_squished_word_and_year(self):
        assert clean_title("Highlander01") == "Highlander 01"
        assert clean_title("Camry2019") == "Camry 2019"
        assert clean_title("2026Changan") == "2026 Changan"

    def test_preserves_model_codes(self):
        assert clean_title("Mercedes E300") == "Mercedes E300"
        assert clean_title("Lexus RX350") == "Lexus RX350"
        assert clean_title("BMW 530i") == "BMW 530i"


class TestExtractBrandModel:
    """Tests for brand/model extraction from listing titles."""

    def test_basic_brand_and_model(self):
        brand, model = extract_brand_model("Toyota Camry used good condition")
        assert brand == "Toyota"
        assert model == "Camry"

    def test_year_not_leaked_into_model(self):
        """Year digits must NOT appear in the model field."""
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

    def test_khmer_nickname(self):
        """Khmer nicknames like ស្រីម៉ៅ should map to Lexus RX300."""
        brand, model = extract_brand_model("លក់ឡាន ស្រីម៉ៅ ឆ្នាំ2000 ឡានស្អាត")
        assert brand == "Lexus"
        assert model == "RX300"

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

    def test_chinese_brands(self):
        brand1, model1 = extract_brand_model("BYD Atto 3 2023 new")
        assert brand1 == "BYD"
        assert model1 == "Atto 3"

        brand2, model2 = extract_brand_model("腾势 D9 2024 EV")
        assert brand2 == "Denza"
        assert model2 == "D9"

        brand3, model3 = extract_brand_model("Fangchengbao Leopard 5 2024")
        assert brand3 == "Fangchengbao"
        assert model3 == "Leopard 5"

        brand4, model4 = extract_brand_model("Deepal S07 2024 Full")
        assert brand4 == "Changan"
        assert model4 == "Deepal S07"

    def test_stop_word_halts_model(self):
        brand, model = extract_brand_model("Kia for sale cheap")
        assert brand == "Kia"
        assert model is None

    def test_keyword_stop_word(self):
        brand, model = extract_brand_model("Mazda automatic 2020")
        assert brand == "Mazda"
        assert model is None

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
        assert brand == "Toyota"
        assert model == "Camry"

    def test_multi_word_model(self):
        brand, model = extract_brand_model("Toyota Land Cruiser 2022 used")
        assert brand == "Toyota"
        assert model == "Land Cruiser"

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

        brand4, model4 = extract_brand_model("D9 EV 2024 Luxury Edition")
        assert brand4 == "Denza"
        assert model4 == "D9"

        brand5, model5 = extract_brand_model("Highlander 2003 V6 4WD")
        assert brand5 == "Toyota"
        assert model5 == "Highlander"


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

    def test_negative_mileage(self):
        assert parse_mileage("-5000") is None


class TestParseEngineCc:
    """Tests for engine displacement parsing."""

    def test_liter_format(self):
        assert parse_engine_cc("2.0L") == 2000
        assert parse_engine_cc("2.5 l") == 2500
        assert parse_engine_cc("1.8 Liter") == 1800

    def test_cc_format(self):
        assert parse_engine_cc("1500 cc") == 1500
        assert parse_engine_cc("3,500cc") == 3500

    def test_plain_integer(self):
        assert parse_engine_cc(2000) == 2000
        assert parse_engine_cc("2400") == 2400

    def test_out_of_bounds(self):
        assert parse_engine_cc("50") is None        # Below 300cc
        assert parse_engine_cc("15000") is None    # Above 10,000cc

    def test_invalid_input(self):
        assert parse_engine_cc(None) is None
        assert parse_engine_cc("Electric") is None


class TestSpecNormalizers:
    """Tests for English and Khmer transmission, fuel type, and color normalizers."""

    def test_normalize_transmission(self):
        assert normalize_transmission("Auto") == "Automatic"
        assert normalize_transmission("automatic") == "Automatic"
        assert normalize_transmission("ស្វ័យប្រវត្តិ") == "Automatic"
        assert normalize_transmission("លេខអូតូ") == "Automatic"
        assert normalize_transmission("Manual") == "Manual"
        assert normalize_transmission("លេខដៃ") == "Manual"
        assert normalize_transmission("លេខកំប៉ុក") == "Manual"
        assert normalize_transmission(None) is None
        assert normalize_transmission("unknown") is None

    def test_normalize_fuel_type(self):
        assert normalize_fuel_type("Petrol") == "Petrol"
        assert normalize_fuel_type("gasoline") == "Petrol"
        assert normalize_fuel_type("សាំង") == "Petrol"
        assert normalize_fuel_type("ប្រេងសាំង") == "Petrol"
        assert normalize_fuel_type("Diesel") == "Diesel"
        assert normalize_fuel_type("ម៉ាស៊ូត") == "Diesel"
        assert normalize_fuel_type("Hybrid") == "Hybrid"
        assert normalize_fuel_type("ហាយប្រីត/Hybrid") == "Hybrid"
        assert normalize_fuel_type("កូនកាត់") == "Hybrid"
        assert normalize_fuel_type("Electric") == "Electric"
        assert normalize_fuel_type("អគ្គិសនី") == "Electric"
        assert normalize_fuel_type("ហ្គាស/LPG") == "LPG"
        assert normalize_fuel_type(None) is None
        assert normalize_fuel_type("unknown") is None

    def test_normalize_color(self):
        assert normalize_color("White") == "White"
        assert normalize_color("ពណ៌ស") == "White"
        assert normalize_color("ពណ៍ខ្មៅ") == "Black"
        assert normalize_color("ពណ៌ប្រាក់") == "Silver"
        assert normalize_color("ទឹកប្រាក់") == "Silver"
        assert normalize_color("ពណ៌ប្រផេះ") == "Grey"
        assert normalize_color("កណ្តុរប្រមេះ") == "Grey"
        assert normalize_color("ពណ៌មាស") == "Gold"
        assert normalize_color("ពណ៌ក្រហម") == "Red"
        assert normalize_color("ពណ៌ខៀវ") == "Blue"
        assert normalize_color("ពណ៌លឿង") == "Yellow"
        assert normalize_color("ពណ៌ទឹកក្រូច") == "Orange"
        assert normalize_color("ពណ៌បៃតង") == "Green"
        assert normalize_color("ពណ៌ត្នោត") == "Brown"
        assert normalize_color("ផ្សេងៗ") == "Other"
        assert normalize_color(None) is None
        assert normalize_color("unknown") is None


