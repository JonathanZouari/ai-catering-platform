"""Owner side of orders (screen A1): list, detail, approve, reject.

Customers create and submit orders in Phase 3; this module only reads submitted orders and
records the owner's decision. Transitions: pending_approval -> approved | rejected only.
"""

import uuid
from typing import get_args

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.orders import Order
from app.repositories import orders as repo
from app.schemas import orders as s

OWNER_STATUSES: tuple[str, ...] = get_args(s.OwnerStatus)


def list_orders(db: Session, status: str | None = None) -> list[s.OrderSummaryOut]:
    found = repo.list_orders(db, (status,) if status else OWNER_STATUSES)
    return [
        s.OrderSummaryOut(
            id=o.id,
            status=o.status,
            customer_name=o.customer.full_name,
            event_type=o.event.event_type,
            event_date=o.event.event_date,
            guests=o.event.adults + o.event.children,
            fulfillment_type=o.fulfillment_type,
            requested_at=o.requested_at,
            total=o.total,
            submitted_at=o.submitted_at,
        )
        for o in found
    ]


def _get_visible(db: Session, order_id: uuid.UUID) -> Order:
    order = db.get(Order, order_id)
    if order is None or order.status not in OWNER_STATUSES:
        raise AppError(404, "not_found", "Order not found")
    return order


def to_detail(order: Order) -> s.OrderDetailOut:
    # Submitted orders are read from the price snapshot frozen at submission.
    items = [
        s.OrderItemOut(
            dish_id=i.dish_id,
            name=i.snapshot_name,
            pricing_unit=i.snapshot_pricing_unit,
            unit_price=i.snapshot_unit_price,
            quantity=i.quantity,
            line_total=i.snapshot_line_total,
        )
        for i in order.items
    ]
    plain = {k: getattr(order, k) for k in s.OrderDetailOut.model_fields if k != "items"}
    return s.OrderDetailOut.model_validate({**plain, "items": items})


def get_order(db: Session, order_id: uuid.UUID) -> s.OrderDetailOut:
    return to_detail(_get_visible(db, order_id))


def decide(db: Session, order_id: uuid.UUID, approve: bool, data: s.DecisionIn) -> s.OrderDetailOut:
    _get_visible(db, order_id)  # 404 before 409
    if not approve and not data.note:
        raise AppError(
            422, "validation_error", "A note is required when rejecting", {"field": "note"}
        )
    if not repo.decide(db, order_id, "approved" if approve else "rejected", data.note or None):
        db.rollback()
        raise AppError(409, "invalid_transition", "Only orders awaiting approval can be decided")
    db.commit()
    db.expire_all()
    return get_order(db, order_id)
