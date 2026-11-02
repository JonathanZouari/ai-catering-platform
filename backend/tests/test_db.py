from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.db import Base
from app.models import (
    Customer,
    Dish,
    DishCategory,
    Event,
    FulfillmentType,
    Order,
    OrderItem,
    OrderStatus,
    PricingUnit,
)


@pytest.fixture
def db():
    # In-memory DB: each test starts empty and never touches yummai.db.
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _order_with_dish(db: Session) -> tuple[Order, Dish]:
    customer = Customer(full_name="דנה כהן", phone="050-1234567")
    category = DishCategory(name="סלטים")
    db.add_all([customer, category])
    db.flush()
    event = Event(
        customer_id=customer.id, event_type="בר מצווה", event_date=date(2026, 12, 1),
        adults=40, children=10,
    )
    dish = Dish(
        category_id=category.id, name="טבולה", pricing_unit=PricingUnit.per_tray,
        unit_price=Decimal("120.00"), currency="ILS",
    )
    db.add_all([event, dish])
    db.flush()
    order = Order(
        customer_id=customer.id, event_id=event.id, fulfillment_type=FulfillmentType.pickup,
        requested_at=datetime(2026, 12, 1, 18, tzinfo=UTC),
    )
    db.add(order)
    db.flush()
    return order, dish


def test_full_order_saved_and_read_back(db):
    order, dish = _order_with_dish(db)
    db.add(OrderItem(order_id=order.id, dish_id=dish.id, quantity=Decimal("3")))
    db.commit()

    saved = db.query(Order).one()
    assert saved.status is OrderStatus.draft
    assert saved.version == 1
    item = db.query(OrderItem).one()
    assert db.get(Dish, item.dish_id).name == "טבולה"
    assert db.get(Event, saved.event_id).adults == 40


def test_foreign_keys_are_enforced(db):
    db.add(
        Event(customer_id=999, event_type="x", event_date=date(2026, 1, 1), adults=1, children=0)
    )
    with pytest.raises(IntegrityError):
        db.flush()


@pytest.mark.parametrize(
    "bad",
    [
        lambda o, d: OrderItem(order_id=o.id, dish_id=d.id, quantity=Decimal("0")),
        lambda o, d: Order(
            customer_id=o.customer_id, event_id=o.event_id + 1,
            fulfillment_type=FulfillmentType.delivery, requested_at=o.requested_at,
        ),
        lambda o, d: Event(
            customer_id=o.customer_id, event_type="x", event_date=date(2026, 1, 1),
            adults=0, children=0,
        ),
    ],
    ids=["zero_quantity", "delivery_without_address", "event_without_guests"],
)
def test_check_constraints(db, bad):
    order, dish = _order_with_dish(db)
    db.add(bad(order, dish))
    with pytest.raises(IntegrityError):
        db.flush()


def test_same_dish_twice_in_order_rejected(db):
    order, dish = _order_with_dish(db)
    db.add(OrderItem(order_id=order.id, dish_id=dish.id, quantity=Decimal("1")))
    db.flush()
    db.add(OrderItem(order_id=order.id, dish_id=dish.id, quantity=Decimal("2")))
    with pytest.raises(IntegrityError):
        db.flush()
