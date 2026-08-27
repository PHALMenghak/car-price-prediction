from src.client import Khmer24Client
from src.schemas import AdListingModel


def test_parse_item_accepts_null_highlight_specs():
    client = Khmer24Client()
    try:
        listing = client._parse_item(
            {
                "id": 123,
                "title": "Toyota Camry 2020",
                "price": "10000",
                "highlight_specs": None,
            }
        )
    finally:
        client.close()

    assert listing is not None
    assert listing.listing_id == "123"
    assert listing.vehicle_brand == "Toyota"
    assert listing.vehicle_model == "Camry"


def test_parse_item_ignores_malformed_highlight_specs():
    client = Khmer24Client()
    try:
        listing = client._parse_item(
            {
                "id": 456,
                "title": "Honda Civic 2019",
                "price": "$12,500",
                "highlight_specs": [
                    None,
                    "bad spec",
                    {"field": "car-year", "value": "2019"},
                    {"field": "tax-type", "value": "Imported"},
                ],
            }
        )
    finally:
        client.close()

    assert listing is not None
    assert listing.price == 12500
    assert listing.vehicle_model_year == 2019
    assert listing.vehicle_tax_type == "Imported"


def test_parse_item_extracts_rich_fields():
    client = Khmer24Client()
    try:
        raw = {
            "id": "789",
            "title": "Lexus RX350 2018",
            "price": "48000",
            "description": "Clean car from direct owner",
            "images": ["https://img.khmer24.com/rx1.jpg", "https://img.khmer24.com/rx2.jpg"],
            "user": {
                "id": "555",
                "name": "Sokha",
                "username": "sokha_auto",
                "avatar": "https://img.khmer24.com/sokha.jpg",
                "user_type": "2",
            },
            "highlight_specs": [
                {"field": "car-year", "value": "2018"},
                {"field": "engine-size", "value": "3.5L"},
                {"field": "mileage", "value": "45,000 km"},
                {"field": "fuel-type", "value": "Gasoline"},
                {"field": "transmission", "value": "Automatic"},
            ],
        }
        listing = client._parse_item(raw)
    finally:
        client.close()

    assert listing is not None
    assert listing.listing_id == "789"
    assert listing.description == "Clean car from direct owner"
    assert len(listing.images) == 2
    assert listing.seller_avatar == "https://img.khmer24.com/sokha.jpg"
    assert listing.seller_type == "store"
    assert listing.vehicle_engine_cc == 3500
    assert listing.vehicle_mileage_km == 45000
    assert listing.vehicle_fuel_type == "Petrol"


def test_enrich_item_with_detail():
    client = Khmer24Client()
    try:
        base_item = AdListingModel(
            listing_id="999",
            listing_title="Ford Ranger 2022",
            price=38000.0,
        )
        detail_data = {
            "description": "Full option Wildtrak with roller shutter",
            "photos": ["https://img.khmer24.com/ranger1.jpg"],
            "specs": [
                {"field": "mileage", "value": "20,000"},
                {"field": "engine-size", "value": "2.0L"},
                {"field": "fuel-type", "value": "Diesel"},
                {"field": "transmission", "value": "Auto"},
            ],
        }
        enriched = client._enrich_item_with_detail(base_item, detail_data)
    finally:
        client.close()

    assert enriched.description == "Full option Wildtrak with roller shutter"
    assert enriched.images == ["https://img.khmer24.com/ranger1.jpg"]
    assert enriched.vehicle_mileage_km == 20000
    assert enriched.vehicle_engine_cc == 2000
    assert enriched.vehicle_fuel_type == "Diesel"
    assert enriched.vehicle_transmission == "Automatic"


def test_enrich_item_with_nuxt_resolved_specs():
    client = Khmer24Client()
    try:
        base_item = AdListingModel(
            listing_id="888",
            listing_title="Lexus RX300 2021",
            price=65000.0,
        )
        detail_data = {
            "_source": "nuxt_html",
            "resolved_specs": {
                "engine-type": "Petrol",
                "transmission": "Automatic",
                "color": "White",
                "mileage": "32,000 km",
                "engine-size": "2.0L",
                "tax-type": "Plate Number",
                "car-year": 2021,
                "car-brand": "Lexus",
                "car-model": "RX300",
                "condition": "Used",
            },
        }
        enriched = client._enrich_item_with_detail(base_item, detail_data)
    finally:
        client.close()

    assert enriched.vehicle_mileage_km == 32000
    assert enriched.vehicle_engine_cc == 2000
    assert enriched.vehicle_fuel_type == "Petrol"
    assert enriched.vehicle_transmission == "Automatic"
    assert enriched.vehicle_color == "White"
    assert enriched.vehicle_tax_type == "Plate Number"
    assert enriched.vehicle_model_year == 2021
    assert enriched.vehicle_condition == "Used"


def test_scrape_category_feed_deduplicates_in_batch(monkeypatch):
    """Test that items appearing more than once in the API feed are deduplicated inside the batch."""
    client = Khmer24Client()
    
    mock_payload = {
        "total": 3,
        "data": [
            {"id": "1001", "title": "Toyota Prius 2010", "price": "12000"},
            {"id": "1001", "title": "Toyota Prius 2010 (dup)", "price": "12000"},
            {"id": "1002", "title": "Lexus RX350 2015", "price": "35000"},
        ],
    }

    class MockResponse:
        status_code = 200
        text = ""
        def json(self):
            return mock_payload

    monkeypatch.setattr(client, "_get", lambda *args, **kwargs: MockResponse())
    
    results = client.scrape_category_feed(category_slug="cars-for-sale", max_pages=1, enrich_details=False)
    client.close()

    assert len(results) == 2
    assert results[0].listing_id == "1001"
    assert results[1].listing_id == "1002"


def test_scrape_category_feed_triggers_enrichment_on_missing_brand_or_model(monkeypatch):
    """Test that listings missing brand, model, or year trigger detail enrichment even if other specs are present."""
    client = Khmer24Client()
    
    # Title has no recognizable brand/model, but has full physical specs
    mock_payload = {
        "total": 1,
        "data": [
            {
                "id": "2001",
                "title": "Good Car For Sale",
                "price": "15000",
                "highlight_specs": [
                    {"field": "car-year", "value": "2018"},
                    {"field": "mileage", "value": "50000"},
                    {"field": "fuel-type", "value": "Petrol"},
                    {"field": "transmission", "value": "Automatic"},
                    {"field": "engine-size", "value": "2.0L"},
                    {"field": "color", "value": "White"},
                ],
            }
        ],
    }

    class MockResponse:
        status_code = 200
        text = ""
        def json(self):
            return mock_payload

    detail_fetched = []

    def mock_fetch_detail(lid, slug):
        detail_fetched.append(lid)
        return {
            "resolved_specs": {
                "car-brand": "Mazda",
                "car-model": "CX-5",
            }
        }

    monkeypatch.setattr(client, "_get", lambda *args, **kwargs: MockResponse())
    monkeypatch.setattr(client, "fetch_post_detail", mock_fetch_detail)

    results = client.scrape_category_feed(category_slug="cars-for-sale", max_pages=1, enrich_details=True)
    client.close()

    assert len(results) == 1
    assert "2001" in detail_fetched
    assert results[0].vehicle_brand == "Mazda"
    assert results[0].vehicle_model == "CX-5"


def test_enrich_overrides_noisy_title_brand_and_model():
    """Test that detail page authoritative dropdown specs override noisy/unknown title extractions."""
    client = Khmer24Client()
    try:
        base_item = AdListingModel(
            listing_id="3001",
            listing_title="ឡានស្អាត លក់ប្រញាប់ 012345678",  # Noisy title without clean brand/model
            price=14000.0,
            vehicle_brand=None,
            vehicle_model=None,
        )
        detail_data = {
            "_source": "nuxt_html",
            "resolved_specs": {
                "car-brand": "Toyota",
                "car-model": "Prius",
                "car-year": 2010,
                "engine-type": "Hybrid",
            },
        }
        enriched = client._enrich_item_with_detail(base_item, detail_data)
    finally:
        client.close()

    assert enriched.vehicle_brand == "Toyota"
    assert enriched.vehicle_model == "Prius"
    assert enriched.vehicle_model_year == 2010
    assert enriched.vehicle_fuel_type == "Hybrid"


def test_enrich_with_legacy_specs_extracts_brand_and_model():
    """Test that legacy specs dict in detail payload extracts brand and model when title was noisy."""
    client = Khmer24Client()
    try:
        base_item = AdListingModel(
            listing_id="3002",
            listing_title="Urgent sale car",
            price=25000.0,
            vehicle_brand=None,
            vehicle_model=None,
        )
        detail_data = {
            "specs": [
                {"field": "car-brand", "value": "Ford"},
                {"field": "car-model", "value": "Ranger"},
                {"field": "fuel-type", "value": "Diesel"},
            ],
        }
        enriched = client._enrich_item_with_detail(base_item, detail_data)
    finally:
        client.close()

    assert enriched.vehicle_brand == "Ford"
    assert enriched.vehicle_model == "Ranger"
    assert enriched.vehicle_fuel_type == "Diesel"


