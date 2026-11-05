import psycopg
import pytest

C, E, E2, K, D, O, P1 = (f"00000000-0000-0000-0000-{n:012d}" for n in range(1, 8))

BASE = [
    f"INSERT INTO customers (id, full_name) VALUES ('{C}', 'x')",
    "INSERT INTO events (id, customer_id, event_type, event_date, adults, children)"
    f" VALUES ('{E}', '{C}', 't', '2026-01-01', 1, 0)",
    "INSERT INTO events (id, customer_id, event_type, event_date, adults, children)"
    f" VALUES ('{E2}', '{C}', 't', '2026-01-01', 1, 0)",
    f"INSERT INTO dish_categories (id, name) VALUES ('{K}', 'test-category')",
    "INSERT INTO dishes (id, category_id, name, pricing_unit, unit_price)"
    f" VALUES ('{D}', '{K}', 'n', 'per_item', 100)",
    "INSERT INTO orders (id, customer_id, event_id, fulfillment_type, requested_at)"
    f" VALUES ('{O}', '{C}', '{E}', 'pickup', now())",
    "INSERT INTO ai_change_proposals (id, order_id, base_order_version, changes, price_before,"
    f" price_after) VALUES ('{P1}', '{O}', 1, '[]', 0, 0)",
]

PROPOSAL = (
    "INSERT INTO ai_change_proposals (order_id, base_order_version, changes, price_before,"
    f" price_after) VALUES ('{O}', 1, '[]', 0, 0)"
)
ITEM = f"INSERT INTO order_items (order_id, dish_id, quantity) VALUES ('{O}', '{D}', %s)"

# Each statement must be rejected by the schema.
REJECTED = {
    "event with zero guests": "INSERT INTO events (customer_id, event_type, event_date,"
    f" adults, children) VALUES ('{C}', 't', '2026-01-01', 0, 0)",
    "event with unknown customer": "INSERT INTO events (customer_id, event_type, event_date,"
    " adults, children) VALUES (gen_random_uuid(), 't', '2026-01-01', 1, 0)",
    "unknown order status": "UPDATE orders SET status = 'bogus'",
    "delivery without address": "INSERT INTO orders (customer_id, event_id, fulfillment_type,"
    f" requested_at) VALUES ('{C}', '{E2}', 'delivery', now())",
    "second order for one event": "INSERT INTO orders (customer_id, event_id,"
    f" fulfillment_type, requested_at) VALUES ('{C}', '{E}', 'pickup', now())",
    "negative dish price": "INSERT INTO dishes (category_id, name, pricing_unit, unit_price)"
    f" VALUES ('{K}', 'n2', 'per_item', -1)",
    "unknown pricing unit": "INSERT INTO dishes (category_id, name, pricing_unit, unit_price)"
    f" VALUES ('{K}', 'n2', 'per_kg', 1)",
    "zero quantity": ITEM % 0,
    "end time before start": "INSERT INTO time_slots (fulfillment_type, start_time, end_time)"
    " VALUES ('pickup', '12:00', '10:00')",
    "second pending proposal": PROPOSAL,
}


@pytest.fixture
def conn(db):
    for sql in BASE:
        db.execute(sql)
    return db


@pytest.mark.parametrize("sql", REJECTED.values(), ids=REJECTED.keys())
def test_rejected(conn, sql):
    with pytest.raises(psycopg.errors.IntegrityError), conn.transaction():
        conn.execute(sql)


def test_invalid_proposal_json_rejected(conn):
    conn.execute("UPDATE ai_change_proposals SET status = 'rejected'")
    with pytest.raises(psycopg.errors.DataError), conn.transaction():
        conn.execute(PROPOSAL.replace("'[]'", "'{bad'"))


def test_duplicate_dish_in_order_rejected(conn):
    conn.execute(ITEM % 1)
    with pytest.raises(psycopg.errors.UniqueViolation), conn.transaction():
        conn.execute(ITEM % 2)


def test_second_pending_allowed_once_first_is_decided(conn):
    conn.execute("UPDATE ai_change_proposals SET status = 'rejected'")
    conn.execute(PROPOSAL)


def test_deleting_order_cascades(conn):
    conn.execute(ITEM % 1)
    conn.execute(f"DELETE FROM orders WHERE id = '{O}'")
    for table in ("order_items", "ai_change_proposals"):
        n = conn.execute(f"SELECT COUNT(*) AS n FROM {table} WHERE order_id = '{O}'")  # noqa: S608
        assert n.fetchone()["n"] == 0
