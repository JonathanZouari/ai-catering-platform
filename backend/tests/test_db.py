import sqlite3

import pytest

from app.core.db import connect, migrate


@pytest.fixture
def conn():
    c = connect(":memory:")
    migrate(c)
    return c


def _event(conn):
    return conn.execute(
        "INSERT INTO events (event_type, event_date, adults) VALUES ('birthday', '2026-12-01', 10)"
    ).lastrowid


def test_migrate_is_idempotent(conn):
    migrate(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1


def test_foreign_keys_enforced(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO dishes (category_id, name, pricing_unit, unit_price)"
            " VALUES (999, 'x', 'per_tray', 100)"
        )


def test_submitted_order_must_be_complete(conn):
    event_id = _event(conn)
    conn.execute(
        "INSERT INTO orders (id, event_id, fulfillment_type) VALUES ('draft-ok', ?, 'pickup')",
        (event_id,),
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO orders (id, event_id, fulfillment_type, status)"
            " VALUES ('bad', ?, 'pickup', 'pending_approval')",
            (_event(conn),),
        )


def test_event_needs_guests(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO events (event_type, event_date, adults)"
            " VALUES ('birthday', '2026-12-01', 0)"
        )


def test_one_pending_proposal_per_order(conn):
    conn.execute(
        "INSERT INTO orders (id, event_id, fulfillment_type) VALUES ('o1', ?, 'pickup')",
        (_event(conn),),
    )
    insert = (
        "INSERT INTO ai_change_proposals"
        " (order_id, base_order_version, changes, price_before, price_after)"
        " VALUES ('o1', 1, '[]', 0, 0)"
    )
    conn.execute(insert)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(insert)
