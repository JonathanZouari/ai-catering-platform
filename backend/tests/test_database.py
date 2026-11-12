import os
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import (
    Base,
    default_sqlite_path,
    init_db,
    lockdown_statements,
    make_engine,
    resolve_database_url,
)
from app.models import (
    Customer,
    Dish,
    DishCategory,
    DishDietary,
    Event,
    FulfillmentType,
    Order,
    OrderItem,
    PricingUnit,
)


@pytest.fixture
def session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    init_db(engine)
    with Session(engine) as s:
        yield s


def _order(session: Session, **overrides) -> Order:
    customer = Customer(full_name="Dana Levi")
    session.add(customer)
    session.flush()
    event = Event(
        customer_id=customer.id,
        event_type="birthday",
        event_date=date(2026, 12, 1),
        adults=10,
        children=2,
    )
    session.add(event)
    session.flush()
    fields = {
        "customer_id": customer.id,
        "event_id": event.id,
        "fulfillment_type": FulfillmentType.pickup,
        "requested_at": datetime(2026, 12, 1, 12, tzinfo=UTC),
    } | overrides
    order = Order(**fields)
    session.add(order)
    session.flush()
    return order


def test_default_url_is_sqlite():
    assert resolve_database_url(None).startswith("sqlite:///")
    assert resolve_database_url("postgresql://x") == "postgresql://x"


def test_init_db_creates_all_tables(session):
    assert {"customers", "dishes", "orders", "ai_change_proposals"} <= set(Base.metadata.tables)
    assert session.scalar(select(Customer)) is None


def test_dish_round_trip_keeps_money_exact_and_dietary_unknown(session):
    category = DishCategory(name="Salads")
    dish = Dish(
        category=category,
        name="Hummus",
        pricing_unit=PricingUnit.per_tray,
        unit_price=Decimal("39.90"),
        dietary=DishDietary(),
    )
    session.add(dish)
    session.commit()
    loaded = session.scalar(select(Dish))
    assert loaded.unit_price == Decimal("39.90")
    assert loaded.dietary.is_vegan is None  # unknown, not False
    assert loaded.dietary.kashrut_class is None


def test_order_defaults_and_item_uniqueness(session):
    order = _order(session)
    assert order.status == "draft"
    assert order.version == 1
    dish = Dish(
        category=DishCategory(name="Mains"),
        name="Schnitzel",
        pricing_unit=PricingUnit.per_item,
        unit_price=Decimal("12"),
    )
    session.add(dish)
    session.flush()
    session.add(OrderItem(order_id=order.id, dish_id=dish.id, quantity=Decimal("5")))
    session.flush()
    session.add(OrderItem(order_id=order.id, dish_id=dish.id, quantity=Decimal("1")))
    with pytest.raises(IntegrityError):
        session.flush()


def test_delivery_requires_address(session):
    with pytest.raises(IntegrityError):
        _order(session, fulfillment_type=FulfillmentType.delivery)


def test_foreign_keys_enforced(session):
    session.add(
        Event(
            customer_id=uuid.uuid4(), event_type="x", event_date=date.today(), adults=1, children=0
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_event_needs_guests(session):
    customer = Customer(full_name="A")
    session.add(customer)
    session.flush()
    session.add(
        Event(
            customer_id=customer.id, event_type="x", event_date=date.today(), adults=0, children=0
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_default_sqlite_path_is_outside_the_repo_and_honours_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    path = default_sqlite_path()
    assert path == tmp_path / "ai-catering-platform" / "catering.db"
    assert resolve_database_url(None) == f"sqlite:///{path}"
    assert Path(__file__).resolve().parents[2] not in path.parents


def test_make_engine_creates_missing_sqlite_directory(tmp_path):
    db = tmp_path / "nested" / "dir" / "x.db"
    make_engine(f"sqlite:///{db}")
    assert db.parent.is_dir()


def test_lockdown_statements_cover_every_table():
    init_db_tables = Base.metadata.sorted_tables
    with_revoke = lockdown_statements(init_db_tables, revoke_api_roles=True)
    without = lockdown_statements(init_db_tables, revoke_api_roles=False)
    for table in init_db_tables:
        assert f'ALTER TABLE "{table.name}" ENABLE ROW LEVEL SECURITY' in with_revoke
        assert f'REVOKE ALL ON TABLE "{table.name}" FROM anon, authenticated' in with_revoke
    assert len(without) == len(init_db_tables)
    assert not any(s.startswith("REVOKE") for s in without)


@pytest.mark.skipif(not os.environ.get("TEST_POSTGRES_URL"), reason="needs TEST_POSTGRES_URL")
def test_postgres_tables_have_rls_enabled():
    engine = make_engine(os.environ["TEST_POSTGRES_URL"])
    init_db(engine)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT relname, relrowsecurity FROM pg_class WHERE relname = ANY(:names)"),
            {"names": [t.name for t in Base.metadata.sorted_tables]},
        ).all()
    assert len(rows) == len(Base.metadata.sorted_tables)
    assert all(enabled for _, enabled in rows)
