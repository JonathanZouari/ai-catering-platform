import sqlite3
import uuid

import pytest

from app.core.db import get_connection, init_db


@pytest.fixture
def conn():
    c = get_connection(":memory:")
    init_db(c)
    yield c
    c.close()


def new_id() -> str:
    return str(uuid.uuid4())


def make_order(conn, **overrides):
    cust, event, order = new_id(), new_id(), new_id()
    conn.execute("INSERT INTO customers (id, full_name) VALUES (?, 'Dana')", (cust,))
    conn.execute(
        "INSERT INTO events (id, customer_id, event_type, event_date, adults) "
        "VALUES (?, ?, 'birthday', '2026-12-01', 20)",
        (event, cust),
    )
    values = {"fulfillment_type": "pickup", "delivery_address": None, "status": "draft"}
    values.update(overrides)
    conn.execute(
        "INSERT INTO orders (id, customer_id, event_id, fulfillment_type, delivery_address, "
        "status) VALUES (?, ?, ?, ?, ?, ?)",
        (
            order,
            cust,
            event,
            values["fulfillment_type"],
            values["delivery_address"],
            values["status"],
        ),
    )
    return order


def test_seed_loaded(conn):
    assert conn.execute("SELECT count(*) FROM dish_categories").fetchone()[0] == 6
    assert conn.execute("SELECT count(*) FROM dishes").fetchone()[0] == 17


def test_init_is_idempotent(conn):
    init_db(conn)
    assert conn.execute("SELECT count(*) FROM dishes").fetchone()[0] == 17


def test_unknown_allergens_have_no_rows(conn):
    # The mock marks one dish's allergens as unknown (null); it must not appear as "free".
    unknown = conn.execute(
        "SELECT count(*) FROM dishes d WHERE NOT EXISTS "
        "(SELECT 1 FROM dish_allergens a WHERE a.dish_id = d.id)"
    ).fetchone()[0]
    assert unknown == 1


def test_bad_status_rejected(conn):
    with pytest.raises(sqlite3.IntegrityError):
        make_order(conn, status="shipped")


def test_delivery_requires_address(conn):
    with pytest.raises(sqlite3.IntegrityError):
        make_order(conn, fulfillment_type="delivery", delivery_address=None)
    make_order(conn, fulfillment_type="delivery", delivery_address="Herzl 1, Tel Aviv")


def test_event_needs_guests(conn):
    cust = new_id()
    conn.execute("INSERT INTO customers (id, full_name) VALUES (?, 'Dana')", (cust,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO events (id, customer_id, event_type, event_date) "
            "VALUES (?, ?, 'birthday', '2026-12-01')",
            (new_id(), cust),
        )


def test_order_item_needs_existing_dish(conn):
    order = make_order(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO order_items (id, order_id, dish_id, quantity) VALUES (?, ?, ?, 1)",
            (new_id(), order, new_id()),
        )


def test_order_number_and_status_history(conn):
    first, second = make_order(conn), make_order(conn)
    numbers = [
        conn.execute("SELECT order_number FROM orders WHERE id = ?", (o,)).fetchone()[0]
        for o in (first, second)
    ]
    assert numbers == [1001, 1002]
    conn.execute("UPDATE orders SET status = 'pending_approval' WHERE id = ?", (first,))
    row = conn.execute(
        "SELECT from_status, to_status FROM order_status_history WHERE order_id = ?", (first,)
    ).fetchone()
    assert tuple(row) == ("draft", "pending_approval")


def test_updated_at_changes(conn):
    cust = new_id()
    conn.execute(
        "INSERT INTO customers (id, full_name, updated_at) "
        "VALUES (?, 'Dana', '2000-01-01T00:00:00Z')",
        (cust,),
    )
    conn.execute("UPDATE customers SET phone = '050' WHERE id = ?", (cust,))
    updated = conn.execute("SELECT updated_at FROM customers WHERE id = ?", (cust,)).fetchone()[0]
    assert updated > "2000-01-01T00:00:00Z"
