import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.core.db import connect, get_db, init_db
from app.main import app


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    init_db(path)
    return path


@pytest.fixture
def client(db_path):
    def test_db():
        conn = connect(db_path)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = test_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_init_db_is_idempotent(db_path):
    init_db(db_path)
    conn = connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM dishes").fetchone()[0] == 17
        names = [r[0] for r in conn.execute("SELECT name FROM schema_migrations ORDER BY name")]
    finally:
        conn.close()
    assert names == [
        "migrations/0001_init.sql",
        "migrations/0002_availability.sql",
        "seeds/0001_sample_catalog.sql",
        "seeds/0002_sample_availability.sql",
    ]


def test_schema_rejects_unknown_enum_value(db_path):
    conn = connect(db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO dishes (category_id, name, pricing_unit, unit_price_minor) "
                "VALUES (1, 'x', 'per_bucket', 100)"
            )
    finally:
        conn.close()


def test_categories_in_sort_order(client):
    response = client.get("/api/catalog/categories")
    assert response.status_code == 200
    assert [c["sort_order"] for c in response.json()] == [1, 2, 3, 4, 5, 6]


def test_dishes_return_price_as_exact_string(client):
    dishes = client.get("/api/catalog/dishes").json()
    assert len(dishes) == 17
    hummus = next(d for d in dishes if d["id"] == 1)
    assert hummus["unit_price"] == "85.00"
    assert hummus["is_vegan"] is True


def test_dishes_filter_by_kashrut_and_category(client):
    dairy = client.get("/api/catalog/dishes", params={"kashrut": "dairy"}).json()
    assert {d["id"] for d in dairy} == {3, 7, 16}
    fish = client.get("/api/catalog/dishes", params={"category_id": 3}).json()
    assert {d["id"] for d in fish} == {9, 10}


def test_invalid_filter_is_rejected(client):
    assert client.get("/api/catalog/dishes", params={"kashrut": "halal"}).status_code == 422


def test_unknown_dietary_value_never_passes_a_filter(client, db_path):
    conn = connect(db_path)
    conn.execute("UPDATE dishes SET is_vegan = NULL WHERE id = 1")
    conn.commit()
    conn.close()

    vegan = client.get("/api/catalog/dishes", params={"vegan": True}).json()
    not_vegan = client.get("/api/catalog/dishes", params={"vegan": False}).json()
    assert 1 not in {d["id"] for d in vegan} | {d["id"] for d in not_vegan}
    assert client.get("/api/catalog/dishes/1").json()["is_vegan"] is None


def test_unavailable_dish_is_hidden(client, db_path):
    conn = connect(db_path)
    conn.execute("UPDATE dishes SET is_available = 0 WHERE id = 2")
    conn.commit()
    conn.close()

    assert 2 not in {d["id"] for d in client.get("/api/catalog/dishes").json()}
    assert client.get("/api/catalog/dishes/2").status_code == 404


def test_dish_detail_allergen_statuses(client):
    allergens = {
        a["name"]: a["status"] for a in client.get("/api/catalog/dishes/1").json()["allergens"]
    }
    assert allergens["שומשום"] == "contains"
    assert allergens["גלוטן"] == "free"


def test_dish_without_allergen_info_is_unknown_not_free(client):
    detail = client.get("/api/catalog/dishes/8").json()
    assert {a["status"] for a in detail["allergens"]} == {"unknown"}


def test_missing_dish_returns_404(client):
    assert client.get("/api/catalog/dishes/999").status_code == 404
