from app.core.config import get_settings
from tests.conftest import AUTH


def make_dish(client, **extra):
    cat = client.post("/api/admin/categories", json={"name": "סלטים"}, headers=AUTH).json()
    body = {
        "category_id": cat["id"],
        "name": "חומוס",
        "pricing_unit": "per_tray",
        "unit_price": "120.50",
        "unit_label": 'מגש 2 ק"ג',
        **extra,
    }
    res = client.post("/api/admin/dishes", json=body, headers=AUTH)
    assert res.status_code == 201, res.text
    return cat, res.json()


def test_admin_requires_token(client):
    assert client.get("/api/admin/dishes").status_code == 401
    res = client.get("/api/admin/dishes", headers={"Authorization": "Bearer wrong"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unauthenticated"


def test_admin_fails_closed_without_configured_token(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_token", None)
    assert client.get("/api/admin/dishes", headers={"Authorization": "Bearer "}).status_code == 401


def test_dish_crud_and_unknown_dietary(client):
    _, dish = make_dish(client)
    assert dish["unit_price"] == "120.50" and dish["currency"] == "ILS"
    # Nothing entered yet → every dietary field is unknown (null), never false.
    assert dish["dietary"] == {
        "kashrut_class": None,
        "is_vegetarian": None,
        "is_vegan": None,
        "verified_at": None,
    }
    res = client.patch(f"/api/admin/dishes/{dish['id']}", json={"unit_price": "99"}, headers=AUTH)
    assert res.json()["unit_price"] == "99.00"
    assert client.delete(f"/api/admin/dishes/{dish['id']}", headers=AUTH).status_code == 204
    assert client.get(f"/api/admin/dishes/{dish['id']}", headers=AUTH).status_code == 404


def test_validation_errors_use_error_shape(client):
    cat, dish = make_dish(client)
    res = client.patch(f"/api/admin/dishes/{dish['id']}", json={"unit_price": "-1"}, headers=AUTH)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"
    res = client.patch(f"/api/admin/dishes/{dish['id']}", json={"name": None}, headers=AUTH)
    assert res.status_code == 422
    res = client.patch(f"/api/admin/dishes/{dish['id']}", json={"image_path": "x"}, headers=AUTH)
    assert res.status_code == 422  # image only via the (future) upload endpoint
    dup = client.post("/api/admin/categories", json={"name": cat["name"]}, headers=AUTH)
    assert dup.status_code == 409


def test_dietary_and_allergens(client):
    _, dish = make_dish(client)
    nuts = client.post("/api/admin/allergens", json={"name": "אגוזים"}, headers=AUTH).json()
    gluten = client.post("/api/admin/allergens", json={"name": "גלוטן"}, headers=AUTH).json()
    body = {
        "kashrut_class": "pareve",
        "is_vegan": True,
        "allergens": [
            {"allergen_id": nuts["id"], "status": "contains"},
            {"allergen_id": gluten["id"], "status": "unknown"},
        ],
    }
    res = client.put(f"/api/admin/dishes/{dish['id']}/dietary", json=body, headers=AUTH)
    out = res.json()
    assert out["dietary"]["kashrut_class"] == "pareve"
    assert out["dietary"]["is_vegetarian"] is None  # not entered stays unknown
    assert out["allergens"] == [{"allergen_id": nuts["id"], "name": "אגוזים", "status": "contains"}]
    # Replacing clears what is no longer listed.
    res = client.put(f"/api/admin/dishes/{dish['id']}/dietary", json={}, headers=AUTH)
    assert res.json()["allergens"] == [] and res.json()["dietary"]["kashrut_class"] is None
    bad = {"allergens": [{"allergen_id": 999, "status": "free"}]}
    res = client.put(f"/api/admin/dishes/{dish['id']}/dietary", json=bad, headers=AUTH)
    assert res.status_code == 422


def test_category_with_dishes_cannot_be_deleted(client):
    cat, _ = make_dish(client)
    res = client.delete(f"/api/admin/categories/{cat['id']}", headers=AUTH)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "category_not_empty"


def test_public_catalog_hides_unavailable_and_inactive(client):
    cat, dish = make_dish(client)
    assert [d["id"] for d in client.get("/api/catalog/dishes").json()] == [dish["id"]]
    client.patch(f"/api/admin/dishes/{dish['id']}", json={"is_available": False}, headers=AUTH)
    assert client.get("/api/catalog/dishes").json() == []
    assert client.get(f"/api/catalog/dishes/{dish['id']}").status_code == 404
    client.patch(f"/api/admin/dishes/{dish['id']}", json={"is_available": True}, headers=AUTH)
    client.patch(f"/api/admin/categories/{cat['id']}", json={"is_active": False}, headers=AUTH)
    assert client.get("/api/catalog/categories").json() == []
    assert client.get("/api/catalog/dishes").json() == []


def test_public_catalog_dietary_filter(client):
    _, dish = make_dish(client)
    assert client.get("/api/catalog/dishes?vegan=true").json() == []  # unknown ≠ vegan
    client.put(f"/api/admin/dishes/{dish['id']}/dietary", json={"is_vegan": True}, headers=AUTH)
    assert len(client.get("/api/catalog/dishes?vegan=true").json()) == 1
