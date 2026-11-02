import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.orders import Event, Order, OrderItem


def list_orders(db: Session, statuses: tuple[str, ...]) -> list[Order]:
    q = (
        select(Order)
        .join(Order.event)
        .where(Order.status.in_(statuses))
        .order_by(Event.event_date, Order.submitted_at)
    )
    return list(db.scalars(q).unique())


def decide(db: Session, order_id: uuid.UUID, status: str, note: str | None) -> bool:
    """Atomic pending_approval -> status. False if the order is not pending (or missing)."""
    result = db.execute(
        update(Order)
        .where(Order.id == order_id, Order.status == "pending_approval")
        .values(
            status=status,
            decision_note=note,
            decided_at=datetime.now(UTC),
            version=Order.version + 1,
        )
    )
    return result.rowcount == 1


# Orders that hold a slot's capacity: submitted and not rejected.
HOLDING = ("pending_approval", "approved")


def slot_load(db: Session, slot_id: uuid.UUID, day: date, exclude: uuid.UUID | None = None) -> int:
    q = (
        select(func.count())
        .select_from(Order)
        .join(Order.event)
        .where(Order.slot_id == slot_id, Event.event_date == day, Order.status.in_(HOLDING))
    )
    if exclude:
        q = q.where(Order.id != exclude)
    return db.scalar(q) or 0


def slot_loads(db: Session, start: date, end: date) -> dict[tuple[uuid.UUID, date], int]:
    """(slot_id, event_date) -> number of orders holding it, for dates in [start, end]."""
    q = (
        select(Order.slot_id, Event.event_date, func.count())
        .join(Order.event)
        .where(
            Order.slot_id.is_not(None),
            Order.status.in_(HOLDING),
            Event.event_date.between(start, end),
        )
        .group_by(Order.slot_id, Event.event_date)
    )
    return {(slot, day): n for slot, day, n in db.execute(q)}


def dish_in_orders(db: Session, dish_id: uuid.UUID) -> bool:
    return db.scalar(select(OrderItem.id).where(OrderItem.dish_id == dish_id).limit(1)) is not None
