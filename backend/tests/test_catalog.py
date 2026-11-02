from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_categories_in_order():
    response = client.get("/api/catalog/categories")
    assert response.status_code == 200
    assert [c["id"] for c in response.json()][:2] == ["salads", "mains"]


def test_dishes_keep_unknown_allergens_unknown():
    dishes = {d["id"]: d for d in client.get("/api/catalog/dishes").json()}
    assert len(dishes) == 17
    assert dishes["d1"]["allergens"] == ["שומשום"]
    assert dishes["d2"]["allergens"] == []  # verified free
    assert dishes["d8"]["allergens"] is None  # no data, must not read as safe
    assert dishes["d5"]["unit"] == "kg"
