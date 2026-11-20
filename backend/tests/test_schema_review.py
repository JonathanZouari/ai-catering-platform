"""Tests for the schema review fixes (fake data only).

The SQLite tests run everywhere. The Postgres tests need TEST_POSTGRES_URL pointing at a
throwaway local database and refuse any host that looks like Supabase.
"""

import os
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

from app.core.database import Base, init_db, make_engine, uuid_default_statements
from app.models import (
    AiChangeProposal,
    AiConversation,
    AiMessage,
    Customer,
    DeliveryZone,
    Event,
    FulfillmentType,
    Order,
    TimeSlot,
)

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / ("0001_schema_review_fixes.sql")
)


@pytest.fixture
def session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    init_db(engine)
    with Session(engine) as s:
        yield s


def _event(session: Session) -> Event:
    customer = Customer(full_name="Fake Person")
    session.add(customer)
    session.flush()
    event = Event(
        customer_id=customer.id,
        event_type="birthday",
        event_date=date(2026, 12, 1),
        adults=4,
        children=0,
    )
    session.add(event)
    session.flush()
    return event


def _order(session: Session) -> Order:
    order = Order(
        event_id=_event(session).id,
        fulfillment_type=FulfillmentType.pickup,
        requested_at=datetime(2026, 12, 1, 12, tzinfo=UTC),
    )
    session.add(order)
    session.flush()
    return order


# 1. orders.customer_id removed


def test_order_has_no_customer_id_and_customer_comes_from_event(session):
    assert "customer_id" not in Order.__table__.columns
    order = _order(session)
    assert order.event.customer_id is not None


def test_order_event_and_event_customer_are_not_null(session):
    assert not Order.__table__.c.event_id.nullable
    assert not Event.__table__.c.customer_id.nullable
    session.add(
        Order(
            event_id=None,
            fulfillment_type=FulfillmentType.pickup,
            requested_at=datetime(2026, 12, 1, 12, tzinfo=UTC),
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


# 2. jsonb


def test_json_columns_are_jsonb_on_postgres():
    for model, column in [
        (AiMessage, "content"),
        (AiChangeProposal, "changes"),
        (DeliveryZone, "definition"),
    ]:
        ddl = str(CreateTable(model.__table__).compile(dialect=postgresql.dialect()))
        line = next(row for row in ddl.splitlines() if row.strip().startswith(column))
        assert "JSONB" in line, line


def test_json_round_trip_on_sqlite(session):
    zone = DeliveryZone(name="North", fee=10, definition={"cities": ["Haifa"]})
    session.add(zone)
    session.flush()
    session.expire(zone)
    assert zone.definition == {"cities": ["Haifa"]}


# 3. uuid defaults and foreign-key indexes


def test_uuid_default_statements_cover_every_uuid_id_table():
    statements = uuid_default_statements(Base.metadata.sorted_tables)
    expected = {
        t.name
        for t in Base.metadata.sorted_tables
        if [c.name for c in t.primary_key.columns] == ["id"] and t.name != "allergens"
    }
    assert len(expected) == 12
    for name in expected:
        assert f'ALTER TABLE "{name}" ALTER COLUMN "id" SET DEFAULT gen_random_uuid()' in statements
    assert len(statements) == len(expected)


def test_every_foreign_key_has_a_covering_index():
    for table in Base.metadata.sorted_tables:
        covers = [list(table.primary_key.columns.keys())]
        covers += [list(i.columns.keys()) for i in table.indexes]
        covers += [
            list(c.columns.keys())
            for c in table.constraints
            if c.__class__.__name__ == "UniqueConstraint"
        ]
        for fk in table.foreign_key_constraints:
            cols = list(fk.columns.keys())
            assert any(c[: len(cols)] == cols for c in covers), f"{table.name}{cols} has no index"


# 4. time_slots.capacity comment


def test_time_slot_capacity_comment_says_not_enforced():
    assert "not enforced" in TimeSlot.__table__.c.capacity.comment.lower()


# 5. composite FK


def test_proposal_conversation_must_belong_to_same_order(session):
    order, other = _order(session), _order(session)
    conversation = AiConversation(order_id=order.id)
    session.add(conversation)
    session.flush()

    def proposal(order_id, conversation_id):
        return AiChangeProposal(
            order_id=order_id,
            conversation_id=conversation_id,
            base_order_version=1,
            changes=[],
            price_before=0,
            price_after=0,
        )

    session.add(proposal(order.id, conversation.id))
    session.flush()
    session.add(proposal(other.id, None))  # no conversation: allowed
    session.flush()
    session.add(proposal(other.id, conversation.id))  # conversation of another order
    with pytest.raises(IntegrityError):
        session.flush()


# Postgres (local throwaway database only)


@pytest.fixture
def pg():
    url = os.environ.get("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("needs TEST_POSTGRES_URL")
    if "supabase" in (make_url(url).host or "").lower():
        pytest.fail("TEST_POSTGRES_URL must be a throwaway local database, not Supabase")
    schema = f"t_{uuid.uuid4().hex[:8]}"
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    yield engine
    engine.dispose()
    with admin.connect() as conn:
        conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
    admin.dispose()


def _scalar(conn, sql, **params):
    return conn.execute(text(sql), params).scalar()


def _assert_final_shape(engine):
    with engine.connect() as conn:
        assert (
            _scalar(
                conn,
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = 'orders' "
                "AND column_name = 'customer_id'",
            )
            == 0
        )
        for table, column in [
            ("ai_messages", "content"),
            ("ai_change_proposals", "changes"),
            ("delivery_zones", "definition"),
        ]:
            assert (
                _scalar(
                    conn,
                    "SELECT data_type FROM information_schema.columns "
                    "WHERE table_schema = current_schema() "
                    "AND table_name = :t AND column_name = :c",
                    t=table,
                    c=column,
                )
                == "jsonb"
            )
        defaults = _scalar(
            conn,
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND column_name = 'id' "
            "AND column_default LIKE '%gen_random_uuid%'",
        )
        assert defaults == 12
        assert (
            "not enforced"
            in _scalar(
                conn,
                "SELECT col_description('time_slots'::regclass, "
                "(SELECT attnum FROM pg_attribute WHERE attrelid = 'time_slots'::regclass "
                "AND attname = 'capacity'))",
            ).lower()
        )
        fks = (
            conn.execute(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conrelid = 'ai_change_proposals'::regclass AND contype = 'f' "
                    "AND conname <> 'ai_change_proposals_order_id_fkey'"
                )
            )
            .scalars()
            .all()
        )
        assert fks == ["fk_proposal_conversation_same_order"]
        assert {
            "ix_events_customer_id",
            "ix_orders_delivery_zone_id",
            "ix_order_items_dish_id",
            "ix_dish_allergens_allergen_id",
        } <= {
            i["name"]
            for t in ("events", "orders", "order_items", "dish_allergens")
            for i in inspect(conn).get_indexes(t)
        }


def test_pg_init_db_has_final_shape_and_default_ids(pg):
    init_db(pg)
    _assert_final_shape(pg)
    with pg.begin() as conn:
        conn.execute(text("INSERT INTO customers (full_name) VALUES ('Fake Person')"))
        assert _scalar(conn, "SELECT id FROM customers") is not None


def _make_old_shape(engine):
    init_db(engine)
    with engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE orders ADD COLUMN customer_id uuid REFERENCES customers(id)")
        )
        for table, column in [
            ("ai_messages", "content"),
            ("ai_change_proposals", "changes"),
            ("delivery_zones", "definition"),
        ]:
            conn.execute(
                text(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE json USING {column}::json")
            )
        for (table,) in conn.execute(
            text(
                "SELECT table_name FROM information_schema.columns WHERE "
                "table_schema = current_schema() AND column_name = 'id' "
                "AND column_default LIKE '%gen_random_uuid%'"
            )
        ).all():
            conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN id DROP DEFAULT"))
        conn.execute(
            text(
                "ALTER TABLE ai_change_proposals "
                "DROP CONSTRAINT fk_proposal_conversation_same_order"
            )
        )
        conn.execute(
            text("ALTER TABLE ai_conversations DROP CONSTRAINT uq_ai_conversations_id_order")
        )
        conn.execute(
            text(
                "ALTER TABLE ai_change_proposals ADD CONSTRAINT some_odd_name "
                "FOREIGN KEY (conversation_id) REFERENCES ai_conversations (id)"
            )
        )
        conn.execute(text("COMMENT ON COLUMN time_slots.capacity IS NULL"))
        for index in [
            "ix_events_customer_id",
            "ix_orders_delivery_zone_id",
            "ix_order_items_dish_id",
            "ix_dish_allergens_allergen_id",
            "ix_ai_change_proposals_conversation_order",
        ]:
            conn.execute(text(f"DROP INDEX {index}"))


def _run_migration(engine):
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        try:
            conn.exec_driver_sql(MIGRATION.read_text())
        except DBAPIError:
            conn.exec_driver_sql("ROLLBACK")
            raise


def test_pg_migration_upgrades_old_shape_and_is_idempotent(pg):
    _make_old_shape(pg)
    with pg.begin() as conn:
        cid = _scalar(
            conn,
            "INSERT INTO customers (id, full_name) "
            "VALUES (gen_random_uuid(), 'Fake Person') RETURNING id",
        )
        conn.execute(
            text(
                "INSERT INTO events (id, customer_id, event_type, event_date, adults, "
                "children) VALUES (gen_random_uuid(), :c, 'x', '2026-12-01', 2, 0)"
            ),
            {"c": cid},
        )
        conn.execute(
            text(
                "INSERT INTO orders (id, customer_id, event_id, fulfillment_type, "
                "requested_at) SELECT gen_random_uuid(), :c, id, 'pickup', now() "
                "FROM events"
            ),
            {"c": cid},
        )
    _run_migration(pg)
    _assert_final_shape(pg)
    _run_migration(pg)  # second run changes nothing
    _assert_final_shape(pg)
    with pg.connect() as conn:
        assert _scalar(conn, "SELECT count(*) FROM orders") == 1


def test_pg_migration_refuses_mismatched_customer(pg):
    _make_old_shape(pg)
    with pg.begin() as conn:
        a = _scalar(
            conn,
            "INSERT INTO customers (id, full_name) "
            "VALUES (gen_random_uuid(), 'Fake A') RETURNING id",
        )
        b = _scalar(
            conn,
            "INSERT INTO customers (id, full_name) "
            "VALUES (gen_random_uuid(), 'Fake B') RETURNING id",
        )
        conn.execute(
            text(
                "INSERT INTO events (id, customer_id, event_type, event_date, adults, "
                "children) VALUES (gen_random_uuid(), :c, 'x', '2026-12-01', 2, 0)"
            ),
            {"c": a},
        )
        conn.execute(
            text(
                "INSERT INTO orders (id, customer_id, event_id, fulfillment_type, "
                "requested_at) SELECT gen_random_uuid(), :c, id, 'pickup', now() "
                "FROM events"
            ),
            {"c": b},
        )
    with pytest.raises(DBAPIError, match="differs from events.customer_id"):
        _run_migration(pg)
    with pg.connect() as conn:
        assert (
            _scalar(
                conn,
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = 'orders' "
                "AND column_name = 'customer_id'",
            )
            == 1
        )
