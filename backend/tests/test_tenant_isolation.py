import re
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.tenancy import CatererScope
from app.main import app
from app.models import DishCategory
from app.repositories.catalog import CategoryRepository

# Tables with no caterer_id, and why they're safe.
PLATFORM_TABLES = {"allergens", "caterers"}
PARENT_SCOPED_TABLES = {
    "ai_change_proposals",
    "ai_conversations",
    "ai_messages",
    "dish_allergens",
    "dish_dietary",
}


def test_every_admin_route_requires_login(client):
    routes = [
        (method, path)
        for path, operations in app.openapi()["paths"].items()
        if path.startswith("/api/admin")
        for method in operations
    ]
    assert routes
    for method, path in routes:
        url = re.sub(r"{\w+}", str(uuid4()), path)
        response = client.request(method.upper(), url, json={})
        assert response.status_code == 401, f"{method} {path}"


def test_caterer_lists_only_own_categories(client, make_tenant):
    a, b = make_tenant("caterer-a"), make_tenant("caterer-b")
    client.post("/api/admin/categories", json={"name": "סלטים"}, headers=a.headers)
    client.post("/api/admin/categories", json={"name": "בשרים"}, headers=b.headers)

    names = [c["name"] for c in client.get("/api/admin/categories", headers=a.headers).json()]
    assert names == ["סלטים"]


def test_other_caterers_category_is_not_found(client, make_tenant):
    a, b = make_tenant("caterer-a"), make_tenant("caterer-b")
    created = client.post("/api/admin/categories", json={"name": "סלטים"}, headers=a.headers)
    url = f"/api/admin/categories/{created.json()['id']}"

    assert client.get(url, headers=b.headers).status_code == 404
    assert client.patch(url, json={"name": "נפרץ"}, headers=b.headers).status_code == 404
    assert client.get(url, headers=a.headers).json()["name"] == "סלטים"


def test_404_matches_a_missing_id_so_existence_is_hidden(client, make_tenant):
    a, b = make_tenant("caterer-a"), make_tenant("caterer-b")
    created = client.post("/api/admin/categories", json={"name": "סלטים"}, headers=a.headers)

    other = client.get(f"/api/admin/categories/{created.json()['id']}", headers=b.headers)
    missing = client.get(f"/api/admin/categories/{uuid4()}", headers=b.headers)
    assert other.json() == missing.json()


@pytest.mark.parametrize("field", ["caterer_id", "id"])
def test_body_cannot_name_a_caterer_or_id(client, make_tenant, field):
    a, b = make_tenant("caterer-a"), make_tenant("caterer-b")
    body = {"name": "סלטים", field: str(b.id)}
    assert client.post("/api/admin/categories", json=body, headers=a.headers).status_code == 422


def test_category_names_are_unique_per_caterer_not_globally(client, make_tenant):
    a, b = make_tenant("caterer-a"), make_tenant("caterer-b")
    body = {"name": "סלטים"}
    assert client.post("/api/admin/categories", json=body, headers=a.headers).status_code == 201
    assert client.post("/api/admin/categories", json=body, headers=b.headers).status_code == 201

    duplicate = client.post("/api/admin/categories", json=body, headers=a.headers)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "conflict"


def test_repository_scope_overrides_a_caller_supplied_caterer(session, make_tenant):
    a, b = make_tenant("caterer-a"), make_tenant("caterer-b")
    repo = CategoryRepository(session, CatererScope(a.id))

    category = repo.add(DishCategory(name="סלטים", caterer_id=b.id))
    session.commit()

    assert category.caterer_id == a.id
    assert CategoryRepository(session, CatererScope(b.id)).list_all() == []


def _insert_category(session, caterer_id):
    return session.scalar(
        text("insert into dish_categories (caterer_id, name) values (:c, 'x') returning id"),
        {"c": caterer_id},
    )


def _insert_dish(session, caterer_id, category_id):
    return session.scalar(
        text(
            "insert into dishes (caterer_id, category_id, name, pricing_unit, unit_price) "
            "values (:c, :cat, 'd', 'per_item', 1) returning id"
        ),
        {"c": caterer_id, "cat": category_id},
    )


def test_database_rejects_dish_in_another_caterers_category(session, make_tenant):
    a, b = make_tenant("caterer-a"), make_tenant("caterer-b")
    category_of_b = _insert_category(session, b.id)

    with pytest.raises(IntegrityError):
        _insert_dish(session, a.id, category_of_b)
    session.rollback()


def test_database_rejects_order_item_with_another_caterers_dish(session, make_tenant):
    a, b = make_tenant("caterer-a"), make_tenant("caterer-b")
    dish_of_b = _insert_dish(session, b.id, _insert_category(session, b.id))
    customer = session.scalar(
        text(
            "insert into customers (caterer_id, full_name, phone) "
            "values (:c, 'n', '050') returning id"
        ),
        {"c": a.id},
    )
    event = session.scalar(
        text(
            "insert into events (caterer_id, customer_id, event_type, event_date, adults, children)"
            " values (:c, :cu, 'יום הולדת', '2027-01-01', 10, 0) returning id"
        ),
        {"c": a.id, "cu": customer},
    )
    order = session.scalar(
        text(
            "insert into orders (caterer_id, access_token_hash, customer_id, event_id, "
            "fulfillment_type, requested_at) "
            "values (:c, 'hash', :cu, :e, 'pickup', now()) returning id"
        ),
        {"c": a.id, "cu": customer, "e": event},
    )

    for caterer_id in (a.id, b.id):
        with pytest.raises(IntegrityError), session.begin_nested():
            session.execute(
                text(
                    "insert into order_items (caterer_id, order_id, dish_id, quantity) "
                    "values (:c, :o, :d, 1)"
                ),
                {"c": caterer_id, "o": order, "d": dish_of_b},
            )
    session.rollback()


def test_schema_covers_every_table_with_tenancy_and_rls(session):
    tables = session.execute(
        text("select tablename, rowsecurity from pg_tables where schemaname = 'public'")
    ).all()
    with_caterer_id = set(
        session.scalars(
            text(
                "select table_name from information_schema.columns "
                "where table_schema = 'public' and column_name = 'caterer_id' "
                "and is_nullable = 'NO'"
            )
        )
    )

    assert tables
    for table, has_rls in tables:
        assert has_rls, f"{table} has no RLS"
        assert table in with_caterer_id | PLATFORM_TABLES | PARENT_SCOPED_TABLES, (
            f"{table} has no tenant scope"
        )
