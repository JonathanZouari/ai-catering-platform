import sqlite3

import pytest

from app.core.sqlite_db import connect, migrate

EXPECTED_TABLES = {
    "customers", "events", "dish_categories", "dishes", "dish_dietary", "allergens",
    "dish_allergens", "delivery_zones", "time_slots", "blocked_dates", "orders",
    "order_items", "ai_conversations", "ai_messages", "ai_change_proposals",
}  # fmt: skip


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "test.db")
    migrate(c)
    yield c
    c.close()


def _order(conn, **over):
    conn.execute("INSERT INTO customers (id, full_name) VALUES ('c1', 'Dana')")
    conn.execute("INSERT INTO events VALUES ('e1','c1','birthday','2026-12-01',10,2,0,0,0,NULL)")
    row = {"fulfillment_type": "pickup", "delivery_address": None, **over}
    conn.execute(
        "INSERT INTO orders (id, customer_id, event_id, fulfillment_type, requested_at,"
        " delivery_address) VALUES ('o1','c1','e1',?, '2026-12-01T18:00:00Z', ?)",
        (row["fulfillment_type"], row["delivery_address"]),
    )


def test_all_tables_created_and_migration_idempotent(conn):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert EXPECTED_TABLES <= tables
    assert migrate(conn) == []


def test_delivery_requires_address(conn):
    with pytest.raises(sqlite3.IntegrityError):
        _order(conn, fulfillment_type="delivery")


def test_foreign_keys_enforced(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO events VALUES ('e1','missing','x','2026-12-01',1,0,0,0,0,NULL)")


def test_only_one_pending_proposal_per_order(conn):
    _order(conn)
    sql = (
        "INSERT INTO ai_change_proposals (id, order_id, base_order_version, changes,"
        " price_before, price_after) VALUES (?, 'o1', 1, '[]', 0, 0)"
    )
    conn.execute(sql, ("p1",))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(sql, ("p2",))
