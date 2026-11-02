import sqlite3

import pytest

from app.core.db import connect, init_db


@pytest.fixture
def conn(tmp_path):
    path = tmp_path / "test.db"
    init_db(path)
    conn = connect(path)
    yield conn
    conn.close()


def test_sample_zones_and_slots_are_loaded(conn):
    assert conn.execute("SELECT COUNT(*) FROM delivery_zones").fetchone()[0] == 6
    slots = conn.execute(
        "SELECT fulfillment_type, COUNT(*) FROM time_slots GROUP BY fulfillment_type"
    ).fetchall()
    assert {row[0]: row[1] for row in slots} == {"delivery": 3, "pickup": 3}


@pytest.mark.parametrize(
    ("sql", "params"),
    [
        (
            "INSERT INTO time_slots (fulfillment_type, start_time, end_time) VALUES (?, ?, ?)",
            ("pickup", "14:00", "12:00"),
        ),
        (
            "INSERT INTO time_slots (fulfillment_type, start_time, end_time) VALUES (?, ?, ?)",
            ("pickup", "9:00", "11:00"),
        ),
        ("INSERT INTO blocked_dates (date) VALUES (?)", ("24/12/2026",)),
        (
            "INSERT INTO delivery_zones (name, fee_minor, definition) VALUES (?, ?, ?)",
            ("חולון", 5000, "not json"),
        ),
        ("UPDATE dishes SET min_quantity = ? WHERE id = 1", (0,)),
    ],
    ids=["end-before-start", "unpadded-time", "bad-date", "bad-zone-json", "zero-minimum"],
)
def test_schema_rejects_invalid_rows(conn, sql, params):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(sql, params)


def test_blocked_date_is_unique(conn):
    conn.execute("INSERT INTO blocked_dates (date) VALUES ('2026-12-24')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO blocked_dates (date) VALUES ('2026-12-24')")


def test_order_delivery_zone_must_exist(conn):
    conn.execute("INSERT INTO customers (id, full_name) VALUES (1, 'לקוח')")
    conn.execute(
        "INSERT INTO events (id, customer_id, event_type, event_date, adults, children) "
        "VALUES (1, 1, 'יום הולדת', '2026-12-24', 20, 0)"
    )
    order = (
        "INSERT INTO orders (customer_id, event_id, fulfillment_type, requested_at, "
        "delivery_address, delivery_zone_id) VALUES (1, 1, 'delivery', '2026-12-24T12:00', "
        "'רחוב הדוגמה 1', ?)"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(order, (99,))
    conn.execute(order, (1,))
