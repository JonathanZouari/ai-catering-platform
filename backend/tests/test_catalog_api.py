import uuid

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import Dish, DishCategory


def dish_named(dishes, name):
    return next(d for d in dishes if d["name"] == name)


def test_categories_are_ordered(client):
    response = client.get("/api/catalog/categories")
    assert response.status_code == 200
    names = [c["name"] for c in response.json()]
    assert names == ["סלטים ומטבלים", "עיקריות", "דגים", "תוספות ולחמים", "קינוחים", "שתייה"]


def test_dishes_carry_price_unit_and_dietary(client):
    dishes = client.get("/api/catalog/dishes").json()
    assert len(dishes) == 17
    hummus = dish_named(dishes, "חומוס ביתי")
    assert hummus["unit_price"] == "85.00"  # money is a string, never a float
    assert hummus["pricing_unit"] == "per_tray"
    assert hummus["dietary"] == {"kashrut": "pareve", "is_vegetarian": True, "is_vegan": True}
    statuses = {a["name"]: a["status"] for a in hummus["allergens"]}
    assert statuses["שומשום"] == "contains"
    assert statuses["גלוטן"] == "free"


def test_missing_allergen_info_is_reported_as_unknown(client):
    stew = dish_named(client.get("/api/catalog/dishes").json(), "תבשיל קדרה צמחי")
    assert {a["status"] for a in stew["allergens"]} == {"unknown"}
    assert len(stew["allergens"]) == 6


def test_dietary_filters(client):
    vegan = client.get("/api/catalog/dishes", params={"vegan": "true"}).json()
    assert vegan and all(d["dietary"]["is_vegan"] for d in vegan)
    dairy = client.get("/api/catalog/dishes", params={"kashrut": "dairy"}).json()
    assert {d["name"] for d in dairy} == {
        "סלט סלק וגבינת עיזים",
        "פשטידת ברוקולי וגבינות",
        "מיני טארטלטים",
    }


def test_category_filter(client):
    fish = next(c for c in client.get("/api/catalog/categories").json() if c["name"] == "דגים")
    dishes = client.get("/api/catalog/dishes", params={"category_id": fish["id"]}).json()
    assert {d["name"] for d in dishes} == {"פילה סלמון בלימון", "דג מושט בצ׳רמולה"}


def test_unavailable_dishes_and_inactive_categories_are_hidden(client, engine):
    with Session(engine) as session, session.begin():
        session.execute(update(Dish).where(Dish.name == "חומוס ביתי").values(is_available=False))
        session.execute(
            update(DishCategory).where(DishCategory.name == "שתייה").values(is_active=False)
        )
    names = {d["name"] for d in client.get("/api/catalog/dishes").json()}
    assert "חומוס ביתי" not in names
    assert "שתייה קלה ומים" not in names
    assert "שתייה" not in {c["name"] for c in client.get("/api/catalog/categories").json()}


def test_dish_detail(client):
    first = client.get("/api/catalog/dishes").json()[0]
    response = client.get(f"/api/catalog/dishes/{first['id']}")
    assert response.status_code == 200
    assert response.json() == first


def test_unknown_dish_uses_error_format(client):
    response = client.get(f"/api/catalog/dishes/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_invalid_filter_uses_error_format(client):
    response = client.get("/api/catalog/dishes", params={"kashrut": "fleishig"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
