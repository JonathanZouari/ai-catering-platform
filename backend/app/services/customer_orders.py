"""Customer side of orders, screen C1: create and edit a draft from the event configuration.

Rules (backend-authoritative, ADR 0003):
- the customer must have a profile; ownership comes from the token only (ADR 0005)
- event date: not in the past (Israel time) and not blocked
- the slot must be active, of the chosen fulfillment type, and valid for the event's weekday;
  pickup/delivery happens on the event date at the slot's start time
- dietary groups are subsets of adults + children (OPEN_DECISIONS #4)
- delivery needs an address; zone and fee wait for OPEN #19
- edits only while draft, and only against the version the client saw (optimistic lock)
shortcut: no lead time / same-day rule and no slot capacity until OPEN #5.
"""

import uuid
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.customer_auth import CustomerIdentity
from app.core.errors import AppError
from app.models.availability import TimeSlot
from app.models.orders import Customer, Event, Order
from app.repositories import availability as availability_repo
from app.repositories import customers as customers_repo
from app.schemas import customer_orders as s

BUSINESS_TZ = ZoneInfo("Asia/Jerusalem")


def today() -> date:
    return datetime.now(BUSINESS_TZ).date()


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
    if e.event_date < today():
        raise _invalid("event_date", "The event date is in the past", "date_unavailable")
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
    local = datetime.combine(e.event_date, slot.start_time, tzinfo=BUSINESS_TZ)
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


def update_draft(
    db: Session, who: CustomerIdentity, order_id: uuid.UUID, data: s.DraftUpdate
) -> s.CustomerOrderOut:
    order = _owned(db, who, order_id)
    if order.status != "draft":
        raise AppError(409, "invalid_transition", "Only a draft can be edited")
    if order.version != data.version:
        raise AppError(409, "order_version_conflict", "The order changed; reload it")
    requested_at = _validate(db, data)
    _apply(order, order.event, data, requested_at)
    db.flush()
    # The version bump is the lock: it only lands if nobody saved in between.
    bumped = db.execute(
        update(Order)
        .where(Order.id == order_id, Order.version == data.version, Order.status == "draft")
        .values(version=Order.version + 1)
    )
    if bumped.rowcount != 1:
        db.rollback()
        raise AppError(409, "order_version_conflict", "The order changed; reload it")
    db.commit()
    db.expire_all()
    return get_order(db, who, order_id)
