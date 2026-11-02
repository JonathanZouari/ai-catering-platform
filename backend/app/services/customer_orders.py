"""Customer side of orders: the draft's event configuration (C1), items (C2), pricing (C3).

Rules (backend-authoritative, ADR 0003):
- the customer must have a profile; ownership comes from the token only (ADR 0005)
- event date: at least settings.lead_days after today (Israel time) and not blocked
- the slot must be active, of the chosen fulfillment type, and valid for the event's weekday;
  pickup/delivery happens on the event date at the slot's start time
- dietary groups are subsets of adults + children; vegetarian and vegan are separate groups,
  so vegetarian + vegan <= total too (OPEN_DECISIONS #4)
- delivery needs an address; zone and fee wait for OPEN #19
- edits only while draft, and only against the version the client saw (optimistic lock)
Slot capacity (OPEN #5) is enforced at submission, in a later slice.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core import clock
from app.core.customer_auth import CustomerIdentity
from app.core.errors import AppError
from app.models.availability import TimeSlot
from app.models.catalog import Dish
from app.models.orders import Customer, Event, Order, OrderItem
from app.repositories import availability as availability_repo
from app.repositories import catalog as catalog_repo
from app.repositories import customers as customers_repo
from app.schemas import customer_orders as s
from app.services import pricing, recommendations
from app.services import settings as settings_svc

HALF = Decimal("0.5")


def _customer(db: Session, who: CustomerIdentity) -> Customer:
    customer = customers_repo.by_auth_user(db, who.user_id)
    if customer is None:
        raise AppError(409, "profile_required", "Complete your name and phone first")
    return customer


def _owned(db: Session, who: CustomerIdentity, order_id: uuid.UUID) -> Order:
    customer = customers_repo.by_auth_user(db, who.user_id)
    order = db.get(Order, order_id)
    # Someone else's order is "not found", so ids can't be probed.
    if order is None or customer is None or order.customer_id != customer.id:
        raise AppError(404, "not_found", "Order not found")
    return order


def _invalid(field: str, message: str, code: str = "validation_error") -> AppError:
    return AppError(422, code, message, {"field": field})


def _validate(db: Session, data: s.DraftIn) -> datetime:
    """Check the configuration and return the requested pickup/delivery time (UTC)."""
    e = data.event
    guests = e.adults + e.children
    if guests == 0:
        raise _invalid("adults", "At least one guest is required")
    for field in ("vegetarian_guests", "vegan_guests", "restricted_guests"):
        if getattr(e, field) > guests:
            raise _invalid(field, "Dietary groups are part of the total guests")
    if e.vegetarian_guests + e.vegan_guests > guests:
        raise _invalid("vegan_guests", "Vegetarian and vegan guests together exceed the total")
    earliest = clock.today() + timedelta(days=settings_svc.get(db).lead_days)
    if e.event_date < earliest:
        raise _invalid("event_date", "Orders must be placed further ahead", "date_unavailable")
    if availability_repo.list_blocked(db, e.event_date, e.event_date):
        raise _invalid("event_date", "We are not taking orders for this date", "date_unavailable")

    slot = db.get(TimeSlot, data.slot_id)
    weekday = (e.event_date.weekday() + 1) % 7  # Python Mon=0 -> our Sun=0
    if (
        slot is None
        or not slot.is_active
        or slot.fulfillment_type != data.fulfillment_type
        or (slot.weekday is not None and slot.weekday != weekday)
    ):
        raise _invalid("slot_id", "This time is not available for that date", "slot_unavailable")

    if data.fulfillment_type == "delivery" and not data.delivery_address:
        raise _invalid("delivery_address", "A delivery address is required")
    local = datetime.combine(e.event_date, slot.start_time, tzinfo=clock.BUSINESS_TZ)
    return local.astimezone(UTC)


def _apply(order: Order, event: Event, data: s.DraftIn, requested_at: datetime) -> None:
    for key, value in data.event.model_dump().items():
        setattr(event, key, value)
    order.fulfillment_type = data.fulfillment_type
    order.requested_at = requested_at
    order.delivery_address = data.delivery_address if data.fulfillment_type == "delivery" else None


def create_draft(db: Session, who: CustomerIdentity, data: s.DraftIn) -> s.CustomerOrderOut:
    customer = _customer(db, who)
    requested_at = _validate(db, data)
    event = Event(customer_id=customer.id)
    order = Order(customer_id=customer.id, status="draft", version=1)
    _apply(order, event, data, requested_at)
    db.add(event)
    db.flush()
    order.event_id = event.id
    db.add(order)
    db.commit()
    return get_order(db, who, order.id)


def get_order(db: Session, who: CustomerIdentity, order_id: uuid.UUID) -> s.CustomerOrderOut:
    return s.CustomerOrderOut.model_validate(_owned(db, who, order_id))


def _editable(db: Session, who: CustomerIdentity, order_id: uuid.UUID, version: int) -> Order:
    order = _owned(db, who, order_id)
    if order.status != "draft":
        raise AppError(409, "invalid_transition", "Only a draft can be edited")
    if order.version != version:
        raise AppError(409, "order_version_conflict", "The order changed; reload it")
    return order


def _commit_bump(db: Session, who: CustomerIdentity, order_id: uuid.UUID, version: int):
    """Flush the pending change and bump the version in one transaction.

    The conditional UPDATE is the lock: it only lands if nobody saved in between.
    """
    db.flush()
    bumped = db.execute(
        update(Order)
        .where(Order.id == order_id, Order.version == version, Order.status == "draft")
        .values(version=Order.version + 1)
    )
    if bumped.rowcount != 1:
        db.rollback()
        raise AppError(409, "order_version_conflict", "The order changed; reload it")
    db.commit()
    db.expire_all()
    return get_order(db, who, order_id)


def update_draft(
    db: Session, who: CustomerIdentity, order_id: uuid.UUID, data: s.DraftUpdate
) -> s.CustomerOrderOut:
    order = _editable(db, who, order_id, data.version)
    requested_at = _validate(db, data)
    _apply(order, order.event, data, requested_at)
    return _commit_bump(db, who, order_id, data.version)


# items (C2)


def _check_quantity(dish: Dish, quantity: Decimal) -> None:
    step = HALF if dish.pricing_unit == "per_weight" else Decimal(1)  # kg in 0.5, else whole
    if quantity % step:
        raise _invalid("quantity", "Quantity must be whole units (or 0.5 kg steps by weight)")
    if dish.min_quantity and quantity < dish.min_quantity:
        raise AppError(
            422,
            "below_minimum",
            "Below this dish's minimum quantity",
            {"field": "quantity", "minimum": str(dish.min_quantity)},
        )


def set_item(
    db: Session, who: CustomerIdentity, order_id: uuid.UUID, dish_id: uuid.UUID, data: s.ItemIn
) -> s.CustomerOrderOut:
    order = _editable(db, who, order_id, data.version)
    dish = db.get(Dish, dish_id)
    if dish is None or not pricing.orderable(dish):
        raise _invalid("dish_id", "This dish can't be ordered", "dish_unavailable")
    _check_quantity(dish, data.quantity)
    item = next((i for i in order.items if i.dish_id == dish_id), None)
    if item is None:
        order.items.append(OrderItem(dish_id=dish_id, quantity=data.quantity))
    else:
        item.quantity = data.quantity
    return _commit_bump(db, who, order_id, data.version)


def remove_item(
    db: Session, who: CustomerIdentity, order_id: uuid.UUID, dish_id: uuid.UUID, version: int
) -> s.CustomerOrderOut:
    order = _editable(db, who, order_id, version)
    item = next((i for i in order.items if i.dish_id == dish_id), None)
    if item is None:
        raise AppError(404, "not_found", "This dish is not in the order")
    order.items.remove(item)
    return _commit_bump(db, who, order_id, version)


# pricing and recommendations (C3)


def get_pricing(db: Session, who: CustomerIdentity, order_id: uuid.UUID) -> s.PricingOut:
    order = _owned(db, who, order_id)
    dishes = {i.dish_id: db.get(Dish, i.dish_id) for i in order.items}
    return s.PricingOut.model_validate(pricing.price_order(order, dishes))


def get_recommendations(
    db: Session, who: CustomerIdentity, order_id: uuid.UUID
) -> list[s.RecommendationOut]:
    order = _owned(db, who, order_id)
    menu = catalog_repo.list_dishes(db, public=True)
    child = settings_svc.get(db).child_portion
    return [
        s.RecommendationOut.model_validate(r)
        for r in recommendations.recommend(order.event, menu, child)
    ]
