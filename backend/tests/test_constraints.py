import sqlite3

import pytest

from app.db import init_db

BASE = [
    "INSERT INTO customers (id, full_name) VALUES ('c', 'x')",
    "INSERT INTO events (id, customer_id, event_type, event_date, adults, children)"
    " VALUES ('e', 'c', 't', '2026-01-01', 1, 0)",
    "INSERT INTO dish_categories (id, name) VALUES ('k', 'k')",
    "INSERT INTO dishes (id, category_id, name, pricing_unit, unit_price)"
    " VALUES ('d', 'k', 'n', 'per_item', 100)",
    "INSERT INTO orders (id, customer_id, event_id, fulfillment_type, requested_at)"
    " VALUES ('o', 'c', 'e', 'pickup', 'x')",
    "INSERT INTO ai_change_proposals (id, order_id, base_order_version, changes, price_before,"
    " price_after) VALUES ('p1', 'o', 1, '[]', 0, 0)",
]

# Each statement must be rejected by the schema.
REJECTED = {
    "event with zero guests": "INSERT INTO events (id, customer_id, event_type, event_date,"
    " adults, children) VALUES ('e2', 'c', 't', '2026-01-01', 0, 0)",
    "event with unknown customer": "INSERT INTO events (id, customer_id, event_type, event_date,"
    " adults, children) VALUES ('e2', 'nope', 't', '2026-01-01', 1, 0)",
    "unknown order status": "UPDATE orders SET status = 'bogus'",
    "delivery without address": "INSERT INTO orders (id, customer_id, event_id, fulfillment_type,"
    " requested_at) VALUES ('o2', 'c', 'e2', 'delivery', 'x')",
    "second order for one event": "INSERT INTO orders (id, customer_id, event_id,"
    " fulfillment_type, requested_at) VALUES ('o2', 'c', 'e', 'pickup', 'x')",
    "negative dish price": "INSERT INTO dishes (id, category_id, name, pricing_unit, unit_price)"
    " VALUES ('d2', 'k', 'n', 'per_item', -1)",
    "unknown pricing unit": "INSERT INTO dishes (id, category_id, name, pricing_unit, unit_price)"
    " VALUES ('d2', 'k', 'n', 'per_kg', 1)",
    "zero quantity": "INSERT INTO order_items (id, order_id, dish_id, quantity)"
    " VALUES ('i', 'o', 'd', 0)",
    "end time before start": "INSERT INTO time_slots (id, fulfillment_type, start_time, end_time)"
    " VALUES ('s', 'pickup', '12:00', '10:00')",
    "second pending proposal": "INSERT INTO ai_change_proposals (id, order_id,"
    " base_order_version, changes, price_before, price_after) VALUES ('p2', 'o', 1, '[]', 0, 0)",
    "invalid proposal json": "INSERT INTO ai_change_proposals (id, order_id, base_order_version,"
    " changes, price_before, price_after, status) VALUES ('p3', 'o', 1, '{bad', 0, 0, 'rejected')",
}


@pytest.fixture
def conn(tmp_path):
    c = init_db(str(tmp_path / "t.db"))
    for sql in BASE:
        c.execute(sql)
    return c


@pytest.mark.parametrize("sql", REJECTED.values(), ids=REJECTED.keys())
def test_rejected(conn, sql):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(sql)


def test_duplicate_dish_in_order_rejected(conn):
    conn.execute(
        "INSERT INTO order_items (id, order_id, dish_id, quantity) VALUES ('i1','o','d',1)"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO order_items (id, order_id, dish_id, quantity) VALUES ('i2','o','d',2)"
        )


def test_second_pending_allowed_once_first_is_decided(conn):
    conn.execute("UPDATE ai_change_proposals SET status = 'rejected'")
    conn.execute(
        "INSERT INTO ai_change_proposals (id, order_id, base_order_version, changes,"
        " price_before, price_after) VALUES ('p2', 'o', 1, '[]', 0, 0)"
    )


def test_deleting_order_cascades(conn):
    conn.execute("INSERT INTO order_items (id, order_id, dish_id, quantity) VALUES ('i','o','d',1)")
    conn.execute("DELETE FROM orders")
    for table in ("order_items", "ai_change_proposals"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608 (fixed table names).fetchone()[0] == 0
