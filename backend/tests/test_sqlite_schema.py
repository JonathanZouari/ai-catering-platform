import importlib.util
import sqlite3
from pathlib import Path

import pytest

SQLITE_DIR = Path(__file__).resolve().parents[2] / "database" / "sqlite"

EXPECTED_TABLES = {
    "ai_change_proposals",
    "ai_conversations",
    "ai_messages",
    "allergens",
    "blocked_dates",
    "customers",
    "delivery_zones",
    "dish_allergens",
    "dish_categories",
    "dish_dietary",
    "dishes",
    "events",
    "order_items",
    "orders",
    "time_slots",
}


def _load_build_module():
    spec = importlib.util.spec_from_file_location("build_db", SQLITE_DIR / "build_db.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "catering.db"
    _load_build_module().build(db_path)
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    yield connection
    connection.close()


def test_all_tables_created(conn):
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    names = {name for (name,) in rows if not name.startswith("sqlite_")}
    assert names == EXPECTED_TABLES


def test_integrity_and_foreign_keys_clean(conn):
    assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_seed_loaded(conn):
    assert conn.execute("SELECT count(*) FROM dishes").fetchone()[0] > 0
    assert conn.execute("SELECT count(*) FROM orders").fetchone()[0] > 0


def test_schema_only_build_is_empty(tmp_path):
    db_path = tmp_path / "empty.db"
    _load_build_module().build(db_path, seed=False)
    with sqlite3.connect(db_path) as empty:
        assert empty.execute("SELECT count(*) FROM dishes").fetchone()[0] == 0


def test_submitted_order_totals_match_snapshot_lines(conn):
    rows = conn.execute(
        """
        SELECT o.subtotal, o.delivery_fee, o.total, sum(oi.snapshot_line_total)
        FROM orders o JOIN order_items oi ON oi.order_id = o.id
        WHERE o.status = 'pending_approval'
        GROUP BY o.id
        """
    ).fetchall()
    assert rows
    for subtotal, fee, total, lines in rows:
        assert subtotal == lines
        assert total == subtotal + fee


def test_unknown_allergen_is_not_free(conn):
    # A dish with no dish_allergens row for an allergen means "unknown", never "free".
    row = conn.execute("SELECT count(*) FROM dish_allergens WHERE dish_id = 'd-salmon'").fetchone()
    assert row[0] == 0


@pytest.mark.parametrize(
    "sql",
    [
        # negative price
        "INSERT INTO dishes (category_id, name, pricing_unit, unit_price) "
        "VALUES ('cat-mains', 'Bad', 'per_item', -1)",
        # unknown pricing unit
        "INSERT INTO dishes (category_id, name, pricing_unit, unit_price) "
        "VALUES ('cat-mains', 'Bad', 'per_pound', 1)",
        # event with no guests
        "INSERT INTO events (customer_id, event_type, event_date, adults, children, "
        "vegetarian_guests, vegan_guests, restricted_guests) "
        "VALUES ('c-1', 'Party', '2026-12-20', 0, 0, 0, 0, 0)",
        # delivery order without an address
        "INSERT INTO events (id, customer_id, event_type, event_date, adults, children, "
        "vegetarian_guests, vegan_guests, restricted_guests) "
        "VALUES ('e-x', 'c-1', 'Party', '2026-12-20', 5, 0, 0, 0, 0); "
        "INSERT INTO orders (customer_id, event_id, fulfillment_type, requested_at) "
        "VALUES ('c-1', 'e-x', 'delivery', '2026-12-20T12:00:00Z')",
        # time slot ending before it starts
        "INSERT INTO time_slots (fulfillment_type, start_time, end_time) "
        "VALUES ('pickup', '14:00', '10:00')",
        # duplicate dish in the same order
        "INSERT INTO order_items (order_id, dish_id, quantity) VALUES ('o-1', 'd-hummus', 1)",
        # order for a customer that does not exist
        "INSERT INTO events (customer_id, event_type, event_date, adults, children, "
        "vegetarian_guests, vegan_guests, restricted_guests) "
        "VALUES ('missing', 'Party', '2026-12-20', 5, 0, 0, 0, 0)",
    ],
)
def test_constraints_reject_invalid_rows(conn, sql):
    with pytest.raises(sqlite3.IntegrityError):
        conn.executescript(sql)


def test_only_one_pending_proposal_per_order(conn):
    insert = (
        "INSERT INTO ai_change_proposals "
        "(order_id, base_order_version, changes, price_before, price_after) "
        "VALUES ('o-1', 1, '[]', 0, 0)"
    )
    conn.execute(insert)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(insert)
