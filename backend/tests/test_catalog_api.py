import pytest
from fastapi.testclient import TestClient

from app.core import db
from app.main import app


@pytest.fixture
def conn():
    connection = db.connect(":memory:")
    db.migrate(connection)
    db.seed(connection)
    yield connection
    connection.close()


@pytest.fixture
def client(conn):
    app.dependency_overrides[db.get_db] = lambda: conn
    yield TestClient(app)  # no `with`: skips the startup migration on the real DB file
    app.dependency_overrides.clear()


def ids(response):
    return [d["id"] for d in response.json()]


def test_categories_are_active_and_ordered(client, conn):
    conn.execute("UPDATE dish_categories SET is_active = 0 WHERE id = 'drinks'")
    body = client.get("/api/catalog/categories").json()
    assert [c["id"] for c in body] == ["salads", "mains", "fish", "sides", "desserts"]


def test_dishes_list_shape_and_money_as_decimal_string(client):
    response = client.get("/api/catalog/dishes")
    assert response.status_code == 200
    dishes = {d["id"]: d for d in response.json()}
    assert len(dishes) == 17
    assert dishes["d1"]["unit_price"] == "85.00"  # stored as 8500 agorot
    assert dishes["d1"]["pricing_unit"] == "per_tray"
    assert dishes["d1"]["currency"] == "ILS"
    assert dishes["d3"]["kashrut_class"] == "dairy"
    assert dishes["d3"]["is_vegan"] is False


def test_filters(client):
    assert ids(client.get("/api/catalog/dishes?category_id=fish")) == ["d9", "d10"]
    assert ids(client.get("/api/catalog/dishes?kashrut=dairy")) == ["d3", "d7", "d16"]
    vegan = client.get("/api/catalog/dishes?vegan=true").json()
    assert vegan and all(d["is_vegan"] is True for d in vegan)
    assert client.get("/api/catalog/dishes?kashrut=pork").status_code == 422


def test_unknown_dietary_info_is_null_and_never_matches_a_filter(client, conn):
    conn.execute(
        "INSERT INTO dishes (id, category_id, name, pricing_unit, unit_price)"
        " VALUES ('mystery', 'mains', 'Mystery', 'per_item', 500)"
    )
    listed = {d["id"]: d for d in client.get("/api/catalog/dishes").json()}
    assert listed["mystery"]["is_vegan"] is None
    assert listed["mystery"]["kashrut_class"] is None
    for flag in ("vegan=true", "vegan=false", "vegetarian=true", "vegetarian=false"):
        assert "mystery" not in ids(client.get(f"/api/catalog/dishes?{flag}"))


def test_unavailable_dishes_and_inactive_categories_are_hidden(client, conn):
    conn.execute("UPDATE dishes SET is_available = 0 WHERE id = 'd1'")
    conn.execute("UPDATE dish_categories SET is_active = 0 WHERE id = 'fish'")
    listed = ids(client.get("/api/catalog/dishes"))
    assert "d1" not in listed and "d9" not in listed and "d10" not in listed
    assert client.get("/api/catalog/dishes/d1").status_code == 404
    assert client.get("/api/catalog/dishes/d9").status_code == 404


def test_dish_detail_lists_every_allergen_with_explicit_unknown(client):
    detail = client.get("/api/catalog/dishes/d1").json()
    status = {a["name"]: a["status"] for a in detail["allergens"]}
    assert len(status) == 6
    assert status["שומשום"] == "contains"
    assert {s for n, s in status.items() if n != "שומשום"} == {"free"}
    # d8 has no verified allergen data: every allergen must read "unknown", never "free".
    unknown = client.get("/api/catalog/dishes/d8").json()
    assert {a["status"] for a in unknown["allergens"]} == {"unknown"}


def test_missing_dish_uses_the_contract_error_shape(client):
    response = client.get("/api/catalog/dishes/nope")
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "dish_not_found", "message": "Dish not found", "details": {}}
    }
