import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.db import get_db, init_db
from app.main import app


def dish_id(number: int) -> str:
    """The fixed id of a sample dish (database/seeds/0001_sample_catalog.sql)."""
    return f"d0000000-0000-4000-8000-{number:012d}"


def category_id(number: int) -> str:
    return f"c0000000-0000-4000-8000-{number:012d}"


@pytest.fixture
def client(engine):
    def test_db():
        with engine.connect() as conn:
            yield conn

    app.dependency_overrides[get_db] = test_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_init_db_is_idempotent(engine):
    init_db(engine)
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT COUNT(*) FROM dishes")) == 17
        names = list(conn.scalars(text("SELECT name FROM schema_migrations ORDER BY name")))
    assert names == [
        "migrations/0001_init.sql",
        "migrations/0002_availability.sql",
        "seeds/0001_sample_catalog.sql",
        "seeds/0002_sample_availability.sql",
    ]


def test_schema_rejects_unknown_enum_value(engine):
    with engine.connect() as conn, pytest.raises(DBAPIError):
        conn.execute(
            text(
                "INSERT INTO dishes (category_id, name, pricing_unit, unit_price) "
                "VALUES (:category_id, 'x', 'per_bucket', 1)"
            ),
            {"category_id": category_id(1)},
        )


def test_every_table_has_row_level_security(engine):
    with engine.connect() as conn:
        unprotected = list(
            conn.scalars(
                text(
                    "SELECT relname FROM pg_class "
                    "WHERE relkind = 'r' AND relnamespace = current_schema()::regnamespace "
                    "AND NOT relrowsecurity"
                )
            )
        )
    assert unprotected == []


def test_categories_in_sort_order(client):
    response = client.get("/api/catalog/categories")
    assert response.status_code == 200
    assert [c["sort_order"] for c in response.json()] == [1, 2, 3, 4, 5, 6]


def test_dishes_return_price_as_exact_string(client):
    dishes = client.get("/api/catalog/dishes").json()
    assert len(dishes) == 17
    hummus = next(d for d in dishes if d["id"] == dish_id(1))
    assert hummus["unit_price"] == "85.00"
    assert hummus["is_vegan"] is True


def test_dishes_filter_by_kashrut_and_category(client):
    dairy = client.get("/api/catalog/dishes", params={"kashrut": "dairy"}).json()
    assert {d["id"] for d in dairy} == {dish_id(3), dish_id(7), dish_id(16)}
    fish = client.get("/api/catalog/dishes", params={"category_id": category_id(3)}).json()
    assert {d["id"] for d in fish} == {dish_id(9), dish_id(10)}


def test_invalid_filter_is_rejected(client):
    assert client.get("/api/catalog/dishes", params={"kashrut": "halal"}).status_code == 422


def test_unknown_dietary_value_never_passes_a_filter(client, engine):
    with engine.begin() as conn:
        conn.execute(text("UPDATE dishes SET is_vegan = NULL WHERE id = :id"), {"id": dish_id(1)})

    vegan = client.get("/api/catalog/dishes", params={"vegan": True}).json()
    not_vegan = client.get("/api/catalog/dishes", params={"vegan": False}).json()
    assert dish_id(1) not in {d["id"] for d in vegan} | {d["id"] for d in not_vegan}
    assert client.get(f"/api/catalog/dishes/{dish_id(1)}").json()["is_vegan"] is None


def test_unavailable_dish_is_hidden(client, engine):
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE dishes SET is_available = false WHERE id = :id"), {"id": dish_id(2)}
        )

    assert dish_id(2) not in {d["id"] for d in client.get("/api/catalog/dishes").json()}
    assert client.get(f"/api/catalog/dishes/{dish_id(2)}").status_code == 404


def test_dish_detail_allergen_statuses(client):
    allergens = {
        a["name"]: a["status"]
        for a in client.get(f"/api/catalog/dishes/{dish_id(1)}").json()["allergens"]
    }
    assert allergens["שומשום"] == "contains"
    assert allergens["גלוטן"] == "free"


def test_dish_without_allergen_info_is_unknown_not_free(client):
    detail = client.get(f"/api/catalog/dishes/{dish_id(8)}").json()
    assert {a["status"] for a in detail["allergens"]} == {"unknown"}


def test_missing_dish_returns_404(client):
    assert client.get(f"/api/catalog/dishes/{dish_id(999)}").status_code == 404
