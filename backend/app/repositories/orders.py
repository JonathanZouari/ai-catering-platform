import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
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


def dish_in_orders(db: Session, dish_id: uuid.UUID) -> bool:
    return db.scalar(select(OrderItem.id).where(OrderItem.dish_id == dish_id).limit(1)) is not None
