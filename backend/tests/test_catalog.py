from uuid import uuid4

import pytest

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32
PDF = b"%PDF-1.7 fake"


@pytest.fixture
def tenant(make_tenant):
    return make_tenant("caterer-a")


def _category(client, tenant, name="סלטים"):
    response = client.post("/api/admin/categories", json={"name": name}, headers=tenant.headers)
    assert response.status_code == 201
    return response.json()


def _dish(client, tenant, category_id, **overrides):
    body = {
        "category_id": category_id,
        "name": "טבולה",
        "pricing_unit": "per_tray",
        "unit_price": "120.50",
    } | overrides
    return client.post("/api/admin/dishes", json=body, headers=tenant.headers)


def test_dish_lifecycle(client, tenant):
    category = _category(client, tenant)
    dish = _dish(client, tenant, category["id"], calories_per_portion=150).json()
    url = f"/api/admin/dishes/{dish['id']}"

    assert dish["unit_price"] == "120.50"
    assert dish["calories_per_portion"] == 150
    assert dish["dietary"] is None
    assert dish["allergens"] == []

    patch = {"unit_price": "99.00", "calories_per_portion": None}
    updated = client.patch(url, json=patch, headers=tenant.headers).json()
    assert updated["unit_price"] == "99.00"
    assert updated["calories_per_portion"] is None

    assert client.delete(url, headers=tenant.headers).status_code == 204
    assert client.get(url, headers=tenant.headers).status_code == 404


def test_list_dishes_by_category(client, tenant):
    a, b = _category(client, tenant, "א"), _category(client, tenant, "ב")
    _dish(client, tenant, a["id"], name="אחת")
    _dish(client, tenant, b["id"], name="שתיים")

    url = f"/api/admin/dishes?category_id={a['id']}"
    assert [d["name"] for d in client.get(url, headers=tenant.headers).json()] == ["אחת"]
    assert len(client.get("/api/admin/dishes", headers=tenant.headers).json()) == 2


@pytest.mark.parametrize(
    "overrides",
    [
        {"unit_price": "-1"},
        {"unit_price": "1.999"},
        {"pricing_unit": "per_hug"},
        {"pricing_unit": "per_weight"},
        {"calories_per_portion": -5},
        {"min_quantity": "0"},
        {"name": ""},
    ],
)
def test_invalid_dish_is_rejected(client, tenant, overrides):
    category = _category(client, tenant)
    assert _dish(client, tenant, category["id"], **overrides).status_code == 422


def test_weight_pricing_with_label_is_accepted(client, tenant):
    category = _category(client, tenant)
    response = _dish(client, tenant, category["id"], pricing_unit="per_weight", unit_label="ק״ג")
    assert response.status_code == 201


def test_patch_to_weight_pricing_needs_a_label(client, tenant):
    dish = _dish(client, tenant, _category(client, tenant)["id"]).json()
    url = f"/api/admin/dishes/{dish['id']}"
    patch = {"pricing_unit": "per_weight"}

    assert client.patch(url, json=patch, headers=tenant.headers).status_code == 422
    assert client.get(url, headers=tenant.headers).json()["pricing_unit"] == "per_tray"

    patch["unit_label"] = "ק״ג"
    assert client.patch(url, json=patch, headers=tenant.headers).status_code == 200


@pytest.mark.parametrize("field", ["name", "unit_price", "pricing_unit", "category_id"])
def test_patch_cannot_null_a_required_field(client, tenant, field):
    dish = _dish(client, tenant, _category(client, tenant)["id"]).json()
    url = f"/api/admin/dishes/{dish['id']}"
    assert client.patch(url, json={field: None}, headers=tenant.headers).status_code == 422


def test_category_patch_cannot_null_name(client, tenant):
    category = _category(client, tenant)
    url = f"/api/admin/categories/{category['id']}"
    assert client.patch(url, json={"name": None}, headers=tenant.headers).status_code == 422


def test_category_with_dishes_cannot_be_deleted(client, tenant):
    category = _category(client, tenant)
    _dish(client, tenant, category["id"])
    url = f"/api/admin/categories/{category['id']}"

    response = client.delete(url, headers=tenant.headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
    assert client.get(url, headers=tenant.headers).status_code == 200


def test_empty_category_can_be_deleted(client, tenant):
    category = _category(client, tenant)
    url = f"/api/admin/categories/{category['id']}"
    assert client.delete(url, headers=tenant.headers).status_code == 204


def test_allergens_are_seeded_in_hebrew(client, tenant):
    names = [a["name"] for a in client.get("/api/admin/allergens", headers=tenant.headers).json()]
    assert "גלוטן" in names


def _allergen_ids(client, tenant):
    return [a["id"] for a in client.get("/api/admin/allergens", headers=tenant.headers).json()]


def test_dietary_replacement_and_unknown_is_not_stored(client, tenant):
    dish = _dish(client, tenant, _category(client, tenant)["id"]).json()
    url = f"/api/admin/dishes/{dish['id']}/dietary"
    first, second, third = _allergen_ids(client, tenant)[:3]

    body = {
        "kashrut_class": "pareve",
        "is_vegetarian": True,
        "is_vegan": None,
        "allergens": [
            {"allergen_id": first, "status": "contains"},
            {"allergen_id": second, "status": "free"},
            {"allergen_id": third, "status": "unknown"},
        ],
    }
    result = client.put(url, json=body, headers=tenant.headers).json()
    assert result["dietary"]["kashrut_class"] == "pareve"
    assert result["dietary"]["is_vegan"] is None
    assert {a["allergen_id"]: a["status"] for a in result["allergens"]} == {
        first: "contains",
        second: "free",
    }

    # Flipping one, dropping another: nothing lingers, so a dropped allergen goes back to unknown.
    body["allergens"] = [{"allergen_id": first, "status": "free"}]
    result = client.put(url, json=body, headers=tenant.headers).json()
    assert result["allergens"] == [{"allergen_id": first, "status": "free"}]


@pytest.mark.parametrize(
    "body",
    [
        {"is_vegan": True, "is_vegetarian": False},
        {"kashrut_class": "meat", "is_vegetarian": True},
        {"kashrut_class": "meat", "is_vegan": True},
        {"kashrut_class": "dairy", "is_vegan": True},
        {"allergens": [{"allergen_id": 1, "status": "free"}] * 2},
    ],
)
def test_contradictory_dietary_data_is_rejected(client, tenant, body):
    dish = _dish(client, tenant, _category(client, tenant)["id"]).json()
    url = f"/api/admin/dishes/{dish['id']}/dietary"
    assert client.put(url, json=body, headers=tenant.headers).status_code == 422


def test_unknown_allergen_id_is_rejected_cleanly(client, tenant):
    dish = _dish(client, tenant, _category(client, tenant)["id"]).json()
    url = f"/api/admin/dishes/{dish['id']}/dietary"
    body = {"allergens": [{"allergen_id": 30000, "status": "free"}]}
    assert client.put(url, json=body, headers=tenant.headers).status_code == 409


def test_dish_image_upload_uses_own_prefix(client, tenant, storage):
    dish = _dish(client, tenant, _category(client, tenant)["id"]).json()
    url = f"/api/admin/dishes/{dish['id']}/image"

    files = {"file": ("x.png", PNG, "image/png")}
    result = client.post(url, files=files, headers=tenant.headers).json()

    assert result["image_path"].startswith(f"{tenant.id}/dishes/")
    assert storage.uploads[result["image_path"]] == (PNG, "image/png")


@pytest.mark.parametrize("content", [b"<script>alert(1)</script>", PDF, b""])
def test_non_image_is_rejected_even_if_it_claims_to_be_one(client, tenant, storage, content):
    dish = _dish(client, tenant, _category(client, tenant)["id"]).json()
    url = f"/api/admin/dishes/{dish['id']}/image"

    files = {"file": ("x.png", content, "image/png")}
    response = client.post(url, files=files, headers=tenant.headers)

    assert response.status_code == 422
    assert storage.uploads == {}


def test_oversized_upload_is_rejected(client, tenant, storage):
    dish = _dish(client, tenant, _category(client, tenant)["id"]).json()
    url = f"/api/admin/dishes/{dish['id']}/image"

    files = {"file": ("x.png", PNG + b"0" * (5 * 1024 * 1024), "image/png")}
    assert client.post(url, files=files, headers=tenant.headers).status_code == 413
    assert storage.uploads == {}


def test_missing_dish_returns_404(client, tenant):
    url = f"/api/admin/dishes/{uuid4()}"
    assert client.get(url, headers=tenant.headers).status_code == 404
