from src.client import Khmer24Client
from src.schemas import RawCarListing


def test_map_raw_listing_basic():
    client = Khmer24Client()
    raw = {
        "id": 123,
        "title": "Toyota Camry 2020",
        "price": "10000",
        "currency": "USD",
        "highlight_specs": None,
    }
    listing = client._map_raw_listing(raw)

    assert listing is not None
    assert listing.listing_id == "123"
    assert listing.raw_title == "Toyota Camry 2020"
    assert listing.raw_price == "10000"
    assert listing.has_detail is False


def test_map_raw_listing_with_highlight_specs():
    client = Khmer24Client()
    raw = {
        "id": 456,
        "title": "Honda Civic 2019",
        "price": "$12,500",
        "highlight_specs": [
            {"field": "car-year", "value": "2019"},
            {"field": "tax-type", "value": "Imported"},
            {"field": "fuel-type", "value": "Gasoline"},
        ],
    }
    listing = client._map_raw_listing(raw)

    assert listing is not None
    assert listing.listing_id == "456"
    assert listing.raw_spec_year == "2019"
    assert listing.raw_spec_tax_type == "Imported"
    assert listing.raw_spec_fuel_type == "Gasoline"


def test_map_raw_listing_with_detail_payload():
    client = Khmer24Client()
    raw_feed = {
        "id": "789",
        "title": "Lexus RX350 2018",
        "price": "48000",
        "user": {
            "id": "555",
            "name": "Sokha",
            "username": "sokha_auto",
            "avatar": "https://img.khmer24.com/sokha.jpg",
            "user_type": "2",
        },
    }
    detail_data = {
        "description": "Clean car from direct owner",
        "photos": ["https://img.khmer24.com/rx1.jpg", "https://img.khmer24.com/rx2.jpg"],
        "phone": ["012345678"],
        "specs": {
            "car-brand": "Lexus",
            "car-model": "RX350",
            "car-year": "2018",
            "engine-size": "3.5L",
            "mileage": "45,000 km",
            "fuel-type": "Gasoline",
            "transmission": "Automatic",
        },
    }

    listing = client._map_raw_listing(
        item=raw_feed,
        detail=detail_data,
        detail_source="rest_api",
        raw_detail_json='{"description": "Clean car from direct owner"}',
    )

    assert listing is not None
    assert listing.listing_id == "789"
    assert listing.raw_description == "Clean car from direct owner"
    assert len(listing.images) == 2
    assert listing.seller_type_code == "2"
    assert listing.raw_spec_brand == "Lexus"
    assert listing.raw_spec_model == "RX350"
    assert listing.raw_spec_engine_size == "3.5L"
    assert listing.raw_spec_mileage == "45,000 km"
    assert listing.raw_spec_fuel_type == "Gasoline"
    assert listing.has_detail is True
    assert listing.detail_source == "rest_api"
