import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError


@pytest.fixture
def conn(engine):
    with engine.connect() as conn:
        yield conn


def test_sample_zones_and_slots_are_loaded(conn):
    assert conn.scalar(text("SELECT COUNT(*) FROM delivery_zones")) == 6
    slots = conn.execute(
        text("SELECT fulfillment_type, COUNT(*) FROM time_slots GROUP BY fulfillment_type")
    ).all()
    assert {row[0]: row[1] for row in slots} == {"delivery": 3, "pickup": 3}


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO time_slots (fulfillment_type, start_time, end_time) "
        "VALUES ('pickup', '14:00', '12:00')",
        "INSERT INTO time_slots (fulfillment_type, start_time, end_time) "
        "VALUES ('pickup', '25:00', '26:00')",
        "INSERT INTO blocked_dates (date) VALUES ('2026-13-45')",
        "INSERT INTO delivery_zones (name, fee, definition) VALUES ('חולון', 50, 'not json')",
        "UPDATE dishes SET min_quantity = 0 WHERE name = 'חומוס ביתי'",
    ],
    ids=["end-before-start", "invalid-time", "bad-date", "bad-zone-json", "zero-minimum"],
)
def test_schema_rejects_invalid_rows(conn, sql):
    with pytest.raises(DBAPIError):
        conn.execute(text(sql))


def test_blocked_date_is_unique(conn):
    conn.execute(text("INSERT INTO blocked_dates (date) VALUES ('2026-12-24')"))
    with pytest.raises(IntegrityError):
        conn.execute(text("INSERT INTO blocked_dates (date) VALUES ('2026-12-24')"))


def test_order_delivery_zone_must_exist(conn):
    customer_id = conn.scalar(
        text("INSERT INTO customers (full_name) VALUES ('לקוח') RETURNING id")
    )
    event_id = conn.scalar(
        text(
            "INSERT INTO events (customer_id, event_type, event_date, adults, children) "
            "VALUES (:customer_id, 'יום הולדת', '2026-12-24', 20, 0) RETURNING id"
        ),
        {"customer_id": customer_id},
    )
    order = text(
        "INSERT INTO orders (customer_id, event_id, fulfillment_type, requested_at, "
        "delivery_address, delivery_zone_id) VALUES (:customer_id, :event_id, 'delivery', "
        "'2026-12-24 12:00+02', 'רחוב הדוגמה 1', :zone_id)"
    )
    params = {"customer_id": customer_id, "event_id": event_id}
    # The savepoint keeps the transaction usable after the expected failure.
    with pytest.raises(IntegrityError), conn.begin_nested():
        conn.execute(order, {**params, "zone_id": "00000000-0000-4000-8000-000000000000"})
    zone_id = conn.scalar(text("SELECT id FROM delivery_zones LIMIT 1"))
    conn.execute(order, {**params, "zone_id": zone_id})
