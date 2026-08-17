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
