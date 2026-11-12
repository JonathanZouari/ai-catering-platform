import sqlite3

import pytest

from app.core import db


@pytest.fixture
def conn():
    connection = db.connect(":memory:")
    db.migrate(connection)
    yield connection
    connection.close()


@pytest.fixture
def seeded(conn):
    db.seed(conn)
    return conn


def make_order(conn, **order_fields):
    """Insert a customer + event + order and return the order id."""
    customer = conn.execute(
        "INSERT INTO customers (full_name) VALUES ('Dana') RETURNING id"
    ).fetchone()["id"]
    event = conn.execute(
        "INSERT INTO events (customer_id, event_type, event_date, adults, children)"
        " VALUES (?, 'birthday', '2026-12-01', 10, 2) RETURNING id",
        (customer,),
    ).fetchone()["id"]
    fields = {"fulfillment_type": "pickup", "requested_at": "2026-12-01T10:00:00Z", **order_fields}
    columns = ", ".join(fields)
    marks = ", ".join("?" for _ in fields)
    sql = (
        f"INSERT INTO orders (customer_id, event_id, {columns}) VALUES (?, ?, {marks}) RETURNING id"  # noqa: S608
    )
    return conn.execute(sql, (customer, event, *fields.values())).fetchone()["id"]


def test_migrate_creates_schema_and_is_idempotent(conn):
    tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {
        "customers",
        "events",
        "dishes",
        "orders",
        "order_items",
        "ai_change_proposals",
    } <= tables
    assert db.migrate(conn) == []  # second run applies nothing


def test_failed_migration_rolls_back_and_is_not_recorded(tmp_path, monkeypatch):
    (tmp_path / "0001_ok.sql").write_text("CREATE TABLE ok (id INTEGER);")
    (tmp_path / "0002_bad.sql").write_text(
        "CREATE TABLE half (id INTEGER); CREATE TABLE ok (id INTEGER);"
    )
    monkeypatch.setattr(db, "MIGRATIONS_DIR", tmp_path)
    connection = db.connect(":memory:")
    with pytest.raises(sqlite3.OperationalError):
        db.migrate(connection)
    tables = {
        r["name"] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "ok" in tables and "half" not in tables  # 0002 left no trace
    versions = [r["version"] for r in connection.execute("SELECT version FROM schema_migrations")]
    assert versions == ["0001_ok"]


def test_seed_is_idempotent_and_loads_catalog(seeded):
    before = seeded.execute("SELECT count(*) AS n FROM dishes").fetchone()["n"]
    db.seed(seeded)
    after = seeded.execute("SELECT count(*) AS n FROM dishes").fetchone()["n"]
    assert before == after == 17
    assert seeded.execute("SELECT count(*) AS n FROM dish_categories").fetchone()["n"] == 6


def test_unknown_allergens_are_not_stored_as_free(seeded):
    unknown = seeded.execute(
        "SELECT count(*) AS n FROM dish_allergens WHERE dish_id = 'd8'"
    ).fetchone()["n"]
    assert unknown == 0  # no rows = unknown
    verified_none = seeded.execute(
        "SELECT DISTINCT status FROM dish_allergens WHERE dish_id = 'd2'"
    ).fetchall()
    assert [r["status"] for r in verified_none] == ["free"]
    contains = seeded.execute(
        "SELECT a.name FROM dish_allergens da JOIN allergens a ON a.id = da.allergen_id"
        " WHERE da.dish_id = 'd1' AND da.status = 'contains'"
    ).fetchall()
    assert [r["name"] for r in contains] == ["שומשום"]


INSERT_DISH = (
    "INSERT INTO dishes (category_id, name, pricing_unit, unit_price) VALUES (?, 'x', ?, ?)"
)


def test_foreign_keys_are_enforced(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(INSERT_DISH, ("no-such-category", "per_item", 1))


def test_check_constraints(seeded):
    with pytest.raises(sqlite3.IntegrityError):  # unknown pricing unit
        seeded.execute(INSERT_DISH, ("salads", "per_kg", 1))
    with pytest.raises(sqlite3.IntegrityError):  # negative price
        seeded.execute(INSERT_DISH, ("salads", "per_item", -1))
    with pytest.raises(sqlite3.IntegrityError):  # an event needs at least one guest
        customer = seeded.execute(
            "INSERT INTO customers (full_name) VALUES ('x') RETURNING id"
        ).fetchone()["id"]
        seeded.execute(
            "INSERT INTO events (customer_id, event_type, event_date, adults, children)"
            " VALUES (?, 'x', '2026-12-01', 0, 0)",
            (customer,),
        )


def test_delivery_order_requires_an_address(conn):
    with pytest.raises(sqlite3.IntegrityError):
        make_order(conn, fulfillment_type="delivery")
    assert make_order(conn, fulfillment_type="delivery", delivery_address="Herzl 1, Tel Aviv")


def test_order_item_rules(seeded):
    order = make_order(seeded)
    seeded.execute(
        "INSERT INTO order_items (order_id, dish_id, quantity) VALUES (?, 'd5', 2.5)", (order,)
    )
    with pytest.raises(sqlite3.IntegrityError):  # same dish twice in one order
        seeded.execute(
            "INSERT INTO order_items (order_id, dish_id, quantity) VALUES (?, 'd5', 1)", (order,)
        )
    with pytest.raises(sqlite3.IntegrityError):  # quantity must be positive
        seeded.execute(
            "INSERT INTO order_items (order_id, dish_id, quantity) VALUES (?, 'd6', 0)", (order,)
        )


def test_only_one_pending_proposal_per_order(conn):
    order = make_order(conn)
    insert = (
        "INSERT INTO ai_change_proposals"
        " (order_id, base_order_version, changes, price_before, price_after, status)"
        " VALUES (?, 1, '[]', 100, 200, ?)"
    )
    conn.execute(insert, (order, "pending"))
    conn.execute(insert, (order, "rejected"))  # decided proposals do not count
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(insert, (order, "pending"))


def test_invalid_json_is_rejected(conn):
    order = make_order(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO ai_change_proposals"
            " (order_id, base_order_version, changes, price_before, price_after)"
            " VALUES (?, 1, 'not json', 1, 2)",
            (order,),
        )


def test_transaction_rolls_back_on_error(conn):
    with pytest.raises(RuntimeError), db.transaction(conn):
        conn.execute("INSERT INTO customers (full_name) VALUES ('ghost')")
        raise RuntimeError
    assert conn.execute("SELECT count(*) AS n FROM customers").fetchone()["n"] == 0
    with db.transaction(conn):
        conn.execute("INSERT INTO customers (full_name) VALUES ('kept')")
    assert conn.execute("SELECT count(*) AS n FROM customers").fetchone()["n"] == 1
