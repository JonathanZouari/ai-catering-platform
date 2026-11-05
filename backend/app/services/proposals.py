"""Owner change proposals on orders awaiting approval (OPEN_DECISIONS #6, decided 2026-11-02).

- The owner sends the full item list they want; changes are derived from the current order.
  Only dishes and quantities change (no custom prices). Prices are frozen in the proposal:
  dishes already in the order keep the price frozen at submission, added dishes take today's
  catalog price. The delivery fee is unchanged.
- One open proposal per order. While it is open the owner can't approve or reject, only cancel.
- Accept (customer): applies the lines and approves the order, atomically and only if the order
  is still at base_order_version; otherwise the proposal expires.
- Decline (customer): the order stays as it was, awaiting the owner's decision.
- Withdrawing the order expires an open proposal.
The AI assistant (Phase 4) proposes on drafts instead: changes are ops on the current items,
prices are today's catalog prices, a new proposal replaces its open one, and accepting applies
the items and keeps the order a draft. No email either way.
JSON columns hold decimals and ids as strings.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.customer_auth import CustomerIdentity
from app.core.errors import AppError
from app.models.catalog import Dish
from app.models.orders import Order, OrderItem
from app.models.proposals import OrderProposal
from app.schemas import proposals as s
from app.services import customer_orders, pricing


def _pending(db: Session, order_id: uuid.UUID) -> OrderProposal | None:
    return db.scalar(
        select(OrderProposal).where(
            OrderProposal.order_id == order_id, OrderProposal.status == "pending"
        )
    )


def has_pending(db: Session, order_id: uuid.UUID) -> bool:
    return _pending(db, order_id) is not None


def list_for_order(db: Session, order_id: uuid.UUID) -> list[s.ProposalOut]:
    rows = db.scalars(
        select(OrderProposal)
        .where(OrderProposal.order_id == order_id)
        .order_by(OrderProposal.created_at.desc())
    )
    return [s.ProposalOut.model_validate(p) for p in rows]


def _proposed_lines(db: Session, order: Order, items: list[s.ProposedItem]) -> list[dict]:
    if len({i.dish_id for i in items}) != len(items):
        raise AppError(422, "validation_error", "Each dish once", {"field": "items"})
    # Submitted orders keep their frozen prices; a draft is priced live from the catalog.
    current = {i.dish_id: i for i in order.items} if order.status != "draft" else {}
    lines = []
    for wanted in items:
        dish = db.get(Dish, wanted.dish_id)
        if dish is None:
            raise AppError(422, "dish_unavailable", "Unknown dish", {"field": "items"})
        existing = current.get(dish.id)
        if existing is None and not pricing.orderable(dish):
            raise AppError(
                422, "dish_unavailable", "This dish can't be ordered", {"dish": dish.name}
            )
        customer_orders.check_quantity(dish, wanted.quantity)
        unit_price = existing.snapshot_unit_price if existing else dish.unit_price
        name = existing.snapshot_name if existing else dish.name
        unit = existing.snapshot_pricing_unit if existing else dish.pricing_unit
        lines.append(
            {
                "dish_id": str(dish.id),
                "name": name,
                "pricing_unit": unit,
                "quantity": str(wanted.quantity),
                "unit_price": str(unit_price),
                "line_total": str(pricing.line_total(wanted.quantity, unit_price)),
            }
        )
    return sorted(lines, key=lambda line: line["name"])


def _changes(db: Session, order: Order, lines: list[dict]) -> list[dict]:
    before = {
        str(i.dish_id): (i.snapshot_name or db.get(Dish, i.dish_id).name, i.quantity)
        for i in order.items
    }
    after = {line["dish_id"]: (line["name"], Decimal(line["quantity"])) for line in lines}
    changes = []
    for dish_id, (name, qty) in after.items():
        if dish_id not in before:
            changes.append(
                {
                    "op": "add_item",
                    "dish_id": dish_id,
                    "name": name,
                    "from_quantity": None,
                    "to_quantity": str(qty),
                }
            )
        elif before[dish_id][1] != qty:
            changes.append(
                {
                    "op": "set_quantity",
                    "dish_id": dish_id,
                    "name": name,
                    "from_quantity": str(before[dish_id][1]),
                    "to_quantity": str(qty),
                }
            )
    for dish_id, (name, qty) in before.items():
        if dish_id not in after:
            changes.append(
                {
                    "op": "remove_item",
                    "dish_id": dish_id,
                    "name": name,
                    "from_quantity": str(qty),
                    "to_quantity": None,
                }
            )
    return changes


def _awaiting(db: Session, order_id: uuid.UUID) -> Order:
    order = db.get(Order, order_id)
    if order is None or order.status not in ("pending_approval", "approved", "rejected"):
        raise AppError(404, "not_found", "Order not found")
    if order.status != "pending_approval":
        raise AppError(409, "invalid_transition", "Only orders awaiting approval can change")
    return order


# owner


def create(db: Session, order_id: uuid.UUID, data: s.ProposalCreate) -> s.ProposalOut:
    order = _awaiting(db, order_id)
    if has_pending(db, order_id):
        raise AppError(409, "proposal_pending", "Cancel the open proposal first")
    lines = _proposed_lines(db, order, data.items)
    current = {str(i.dish_id) for i in order.items}  # only added dishes need the 18+ check
    if order.adult_confirmed_at is None and any(
        db.get(Dish, uuid.UUID(line["dish_id"])).contains_alcohol
        for line in lines
        if line["dish_id"] not in current
    ):
        raise AppError(422, "age_confirmation_required", "The customer hasn't confirmed 18+")
    changes = _changes(db, order, lines)
    if not changes:
        raise AppError(422, "no_changes", "The proposal changes nothing")
    subtotal = sum((Decimal(line["line_total"]) for line in lines), Decimal("0.00"))
    proposal = OrderProposal(
        order_id=order.id,
        proposed_by="owner",
        base_order_version=order.version,
        changes=changes,
        lines=lines,
        price_before=order.total,
        price_after=subtotal + (order.delivery_fee or 0),
        note=data.note or None,
        status="pending",
    )
    db.add(proposal)
    try:
        db.commit()
    except IntegrityError as exc:  # a second proposal raced in (one-pending index)
        db.rollback()
        raise AppError(409, "proposal_pending", "Cancel the open proposal first") from exc
    return s.ProposalOut.model_validate(proposal)


# assistant (Phase 4)


def propose_for_draft(
    db: Session,
    who: CustomerIdentity,
    order_id: uuid.UUID,
    ops: list[s.ChangeIn],
    note: str | None,
) -> s.ProposalOut:
    order = customer_orders._owned(db, who, order_id)
    if order.status != "draft":
        raise AppError(409, "invalid_transition", "Only a draft can be changed here")
    wanted = {i.dish_id: i.quantity for i in order.items}
    for op in ops:
        if op.op == "remove_item":
            if wanted.pop(op.dish_id, None) is None:
                raise AppError(
                    422,
                    "not_in_order",
                    "This dish is not in the order",
                    {"dish_id": str(op.dish_id)},
                )
        else:
            wanted[op.dish_id] = op.quantity
    items = [s.ProposedItem(dish_id=d, quantity=q) for d, q in wanted.items()]
    lines = _proposed_lines(db, order, items)
    changes = _changes(db, order, lines)
    if not changes:
        raise AppError(422, "no_changes", "The proposal changes nothing")
    fee = customer_orders._live_fee(db, order) or 0
    dishes = {i.dish_id: db.get(Dish, i.dish_id) for i in order.items}
    subtotal = sum((Decimal(line["line_total"]) for line in lines), Decimal("0.00"))
    if open_one := _pending(db, order.id):  # the newest suggestion replaces the last one
        _close(db, open_one.id, order.id, "cancelled")
    proposal = OrderProposal(
        order_id=order.id,
        proposed_by="assistant",
        base_order_version=order.version,
        changes=changes,
        lines=lines,
        price_before=pricing.price_order(order, dishes, fee).total,
        price_after=subtotal + fee,
        note=note or None,
        status="pending",
    )
    db.add(proposal)
    try:
        db.commit()
    except IntegrityError as exc:  # another proposal raced in
        db.rollback()
        raise AppError(409, "proposal_pending", "Try again") from exc
    return s.ProposalOut.model_validate(proposal)


def _close(db: Session, proposal_id: uuid.UUID, order_id: uuid.UUID, status: str, **extra) -> bool:
    """Atomic pending -> status. False if it was not pending (anymore)."""
    done = db.execute(
        update(OrderProposal)
        .where(
            OrderProposal.id == proposal_id,
            OrderProposal.order_id == order_id,
            OrderProposal.status == "pending",
        )
        .values(status=status, decided_at=datetime.now(UTC), **extra)
    )
    return done.rowcount == 1


def cancel(db: Session, order_id: uuid.UUID, proposal_id: uuid.UUID) -> s.ProposalOut:
    if not _close(db, proposal_id, order_id, "cancelled"):
        db.rollback()
        raise AppError(409, "proposal_not_pending", "This proposal is no longer open")
    db.commit()
    return s.ProposalOut.model_validate(db.get(OrderProposal, proposal_id))


def expire_open(db: Session, order_id: uuid.UUID) -> None:
    """Called inside the caller's transaction when the order changes under the proposal."""
    pending = _pending(db, order_id)
    if pending:
        _close(db, pending.id, order_id, "expired")


# customer


def _customer_proposal(
    db: Session, who: CustomerIdentity, order_id: uuid.UUID, proposal_id: uuid.UUID
) -> tuple[Order, OrderProposal]:
    order = customer_orders._owned(db, who, order_id)  # 404 for other customers' orders
    proposal = db.get(OrderProposal, proposal_id)
    if proposal is None or proposal.order_id != order.id:
        raise AppError(404, "not_found", "Proposal not found")
    if proposal.status != "pending":
        raise AppError(409, "proposal_not_pending", "This proposal is no longer open")
    return order, proposal


def list_for_customer(
    db: Session, who: CustomerIdentity, order_id: uuid.UUID
) -> list[s.ProposalOut]:
    customer_orders._owned(db, who, order_id)
    return list_for_order(db, order_id)


def accept(
    db: Session, who: CustomerIdentity, order_id: uuid.UUID, proposal_id: uuid.UUID
) -> s.ProposalOut:
    order, proposal = _customer_proposal(db, who, order_id, proposal_id)
    on_draft = proposal.proposed_by == "assistant"
    status = "draft" if on_draft else "pending_approval"
    if order.status != status or order.version != proposal.base_order_version:
        _close(db, proposal.id, order.id, "expired")
        db.commit()
        raise AppError(409, "proposal_expired", "The order changed since this proposal")

    by_dish = {i.dish_id: i for i in order.items}
    keep = set()
    for line in proposal.lines:
        dish_id = uuid.UUID(line["dish_id"])
        keep.add(dish_id)
        item = by_dish.get(dish_id)
        if item is None:
            item = OrderItem(dish_id=dish_id)
            order.items.append(item)
        item.quantity = Decimal(line["quantity"])
        if on_draft:  # prices stay live until submission
            continue
        item.snapshot_name = line["name"]
        item.snapshot_pricing_unit = line["pricing_unit"]
        item.snapshot_unit_price = Decimal(line["unit_price"])
        item.snapshot_line_total = Decimal(line["line_total"])
    for item in [i for i in order.items if i.dish_id not in keep]:
        order.items.remove(item)
    values = {"version": Order.version + 1}
    if not on_draft:  # the owner's proposal: accepting it approves the order
        order.subtotal = sum((Decimal(line["line_total"]) for line in proposal.lines), Decimal(0))
        order.total = order.subtotal + (order.delivery_fee or 0)
        values |= {
            "status": "approved",
            "decided_at": datetime.now(UTC),
            "decision_note": proposal.note,
        }
    db.flush()

    approved = db.execute(
        update(Order)
        .where(
            Order.id == order.id,
            Order.version == proposal.base_order_version,
            Order.status == status,
        )
        .values(**values)
    )
    if approved.rowcount != 1 or not _close(db, proposal.id, order.id, "accepted"):
        db.rollback()
        raise AppError(409, "proposal_expired", "The order changed since this proposal")
    db.commit()
    db.expire_all()
    return s.ProposalOut.model_validate(db.get(OrderProposal, proposal.id))


def decline(
    db: Session,
    who: CustomerIdentity,
    order_id: uuid.UUID,
    proposal_id: uuid.UUID,
    data: s.DeclineIn,
) -> s.ProposalOut:
    _, proposal = _customer_proposal(db, who, order_id, proposal_id)
    if not _close(db, proposal.id, order_id, "declined", customer_note=data.note or None):
        db.rollback()
        raise AppError(409, "proposal_not_pending", "This proposal is no longer open")
    db.commit()
    db.expire_all()
    return s.ProposalOut.model_validate(db.get(OrderProposal, proposal.id))
