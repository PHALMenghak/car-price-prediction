from src.client import Khmer24Client


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


def test_scrape_category_feed_deduplicates_in_batch(monkeypatch):
    """Test that items appearing more than once in the API feed are deduplicated inside the batch."""
    client = Khmer24Client()
    
    # Mock _get response with duplicate IDs
    mock_payload = {
        "total": 3,
        "data": [
            {"id": "1001", "title": "Toyota Prius 2010", "price": "12000"},
            {"id": "1001", "title": "Toyota Prius 2010 (dup)", "price": "12000"},  # duplicate in same page
            {"id": "1002", "title": "Lexus RX350 2015", "price": "35000"},
        ],
    }

    class MockResponse:
        status_code = 200
        def json(self):
            return mock_payload

    monkeypatch.setattr(client, "_get", lambda url, params: MockResponse())
    
    results = client.scrape_category_feed(category_slug="cars-for-sale", max_pages=1)
    client.close()

    assert len(results) == 2
    assert results[0].listing_id == "1001"
    assert results[1].listing_id == "1002"

