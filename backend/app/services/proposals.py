"""AI change proposals. This is the only way the assistant can affect an order, and nothing
changes until the customer approves through the HTTP endpoint (ADR 0003)."""

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import AppError, not_found
from app.core.tenancy import CatererScope
from app.models import AiChangeProposal, Dish, Order, OrderItem
from app.models.enums import OrderStatus, ProposalStatus
from app.repositories.ai import ProposalRepository
from app.repositories.catalog import DishRepository
from app.repositories.caterers import get_own_caterer
from app.repositories.orders import OrderRepository
from app.schemas.ai import ProposeChanges, RemoveItem, SetQuantity, UpdateDetails
from app.services import kashrut, orders, pricing

DIET_FIELDS = ("vegetarian_guests", "vegan_guests", "restricted_guests")


def _invalid(message: str) -> AppError:
    return AppError(422, "invalid_proposal", message)


def _item_line(kind: str, dish: Dish, before: Decimal | None, after: Decimal | None) -> dict:
    return {
        "type": kind,
        "dish_id": str(dish.id),
        "name": dish.name,
        "before": None if before is None else str(before),
        "after": None if after is None else str(after),
    }


def _build_lines(
    session: Session, scope: CatererScope, order: Order, data: ProposeChanges
) -> list[dict[str, Any]]:
    """One stored line per change, holding the values the card shows and approval applies."""
    dishes = DishRepository(session, scope)
    quantities = {item.dish_id: item.quantity for item in order.items}
    lines: list[dict[str, Any]] = []
    seen: set[UUID] = set()

    for change in data.changes:
        if isinstance(change, UpdateDetails):
            for field, value in change.model_dump(exclude={"type"}, exclude_unset=True).items():
                before = getattr(order.event, field)
                lines.append(
                    {"type": "update_details", "field": field, "before": before, "after": value}
                )
            continue

        dish = dishes.get(change.dish_id)
        if dish is None:
            raise not_found()
        if dish.id in seen:
            raise _invalid(f'המנה "{dish.name}" מופיעה יותר מפעם אחת בהצעה')
        seen.add(dish.id)
        before = quantities.get(dish.id)
        if isinstance(change, RemoveItem | SetQuantity) and before is None:
            raise _invalid(f'המנה "{dish.name}" אינה בהזמנה')
        if isinstance(change, RemoveItem):
            del quantities[dish.id]
            lines.append(_item_line("remove_item", dish, before, None))
            continue
        orders.require_valid_quantity(dish, change.quantity)
        quantities[dish.id] = change.quantity
        lines.append(_item_line(change.type, dish, before, change.quantity))
    if not lines:
        raise _invalid("ההצעה ריקה")
    return lines


def _check_guests(order: Order, lines: list[dict[str, Any]]) -> None:
    event = order.event
    counts = {field: getattr(event, field) for field in ("adults", "children", *DIET_FIELDS)} | {
        line["field"]: line["after"]
        for line in lines
        if line["type"] == "update_details" and line["field"] != "dietary_notes"
    }
    if any(value is None for value in counts.values()):
        raise _invalid("מספר הסועדים חסר")
    total = counts["adults"] + counts["children"]
    if total == 0 or sum(counts[field] for field in DIET_FIELDS) > total:
        raise _invalid("מספרי התזונה המיוחדת חייבים להיכלל בסך הסועדים")


def _price_after(
    session: Session, scope: CatererScope, order: Order, lines: list[dict[str, Any]]
) -> Decimal:
    """Validates the order as it would be after these lines, without touching it."""
    dishes = {item.dish_id: item.dish for item in order.items}
    quantities = {item.dish_id: item.quantity for item in order.items}
    repo = DishRepository(session, scope)

    for line in lines:
        if line["type"] == "update_details":
            continue
        dish_id = UUID(line["dish_id"])
        if line["type"] == "remove_item":
            quantities.pop(dish_id, None)
        else:
            dishes[dish_id] = orders.require_orderable(repo.get(dish_id))
            quantities[dish_id] = Decimal(line["after"])

    _check_guests(order, lines)
    chosen = [dishes[dish_id] for dish_id in quantities]
    rule = get_own_caterer(session, scope).kashrut_mixing_rule
    if kashrut.check_order(chosen, rule).status == "blocked":
        raise AppError(
            409, "kashrut_mixing_blocked", "העסק לא מאפשר הזמנה שמערבת מנות בשריות וחלביות"
        )

    totals = [
        pricing.line_total(dishes[dish_id].unit_price, quantity)
        for dish_id, quantity in quantities.items()
    ]
    return pricing.order_total(totals, orders.delivery_fee(order))[1]


def _current_price(session: Session, scope: CatererScope, order: Order) -> Decimal:
    return orders.view(session, scope, order).total


def create_proposal(
    session: Session,
    scope: CatererScope,
    order_id: UUID,
    conversation_id: UUID | None,
    data: ProposeChanges,
) -> AiChangeProposal:
    repo = OrderRepository(session, scope)
    order = repo.lock(order_id)
    if order is None:
        raise not_found()
    if order.status != OrderStatus.DRAFT:
        raise AppError(409, "invalid_transition", "ההזמנה כבר נשלחה ואי אפשר לשנות אותה")

    lines = _build_lines(session, scope, order, data)
    price_after = _price_after(session, scope, order, lines)

    proposals = ProposalRepository(session, scope)
    for pending in proposals.for_order(order_id, ProposalStatus.PENDING):
        pending.status = ProposalStatus.EXPIRED
    session.flush()  # Only one may be pending, so the old one must go first.

    proposal = proposals.add(
        AiChangeProposal(
            order_id=order_id,
            conversation_id=conversation_id,
            base_order_version=order.version,
            changes=lines,
            rationale=data.rationale,
            price_before=_current_price(session, scope, order),
            price_after=price_after,
            status=ProposalStatus.PENDING,
        )
    )
    session.commit()
    return proposal


def list_proposals(
    session: Session, scope: CatererScope, order_id: UUID, status: ProposalStatus | None = None
) -> Sequence[AiChangeProposal]:
    return ProposalRepository(session, scope).for_order(order_id, status)


def _lock_pending(session: Session, scope: CatererScope, order_id: UUID, proposal_id: UUID):
    order = OrderRepository(session, scope).lock(order_id)
    proposal = ProposalRepository(session, scope).lock(order_id, proposal_id)
    if order is None or proposal is None:
        raise not_found()
    if proposal.status != ProposalStatus.PENDING:
        raise AppError(409, "proposal_not_pending", "ההצעה הזו כבר טופלה")
    return order, proposal


def _close(session: Session, proposal: AiChangeProposal, status: ProposalStatus) -> None:
    proposal.status = status
    proposal.decided_at = datetime.now(UTC)
    session.commit()


def _apply(scope: CatererScope, order: Order, lines: list[dict[str, Any]], session: Session):
    repo = DishRepository(session, scope)
    for line in lines:
        if line["type"] == "update_details":
            setattr(order.event, line["field"], line["after"])
            continue
        dish_id = UUID(line["dish_id"])
        item = next((row for row in order.items if row.dish_id == dish_id), None)
        if line["type"] == "remove_item":
            if item is not None:
                order.items.remove(item)
        elif item is not None:
            item.quantity = Decimal(line["after"])
        else:
            dish = repo.get(dish_id)
            order.items.append(
                OrderItem(
                    caterer_id=scope.caterer_id,
                    dish=dish,
                    dish_id=dish_id,
                    quantity=Decimal(line["after"]),
                )
            )


def approve_proposal(
    session: Session, scope: CatererScope, order_id: UUID, proposal_id: UUID
) -> tuple[AiChangeProposal, Order]:
    order, proposal = _lock_pending(session, scope, order_id, proposal_id)
    if order.status != OrderStatus.DRAFT:
        _close(session, proposal, ProposalStatus.EXPIRED)
        raise AppError(409, "invalid_transition", "ההזמנה כבר נשלחה ואי אפשר לשנות אותה")
    if order.version != proposal.base_order_version:
        _close(session, proposal, ProposalStatus.EXPIRED)
        raise AppError(409, "order_version_conflict", "ההזמנה השתנתה. בקשו הצעה חדשה")

    # The menu can have changed since the card was shown, so everything is checked again.
    try:
        price_after = _price_after(session, scope, order, proposal.changes)
    except AppError:
        _close(session, proposal, ProposalStatus.FAILED)
        raise
    if price_after != proposal.price_after:
        _close(session, proposal, ProposalStatus.EXPIRED)
        raise AppError(409, "order_version_conflict", "המחיר השתנה. בקשו הצעה חדשה")

    _apply(scope, order, proposal.changes, session)
    order.version += 1
    proposal.executed_at = datetime.now(UTC)
    _close(session, proposal, ProposalStatus.APPROVED)
    return proposal, order


def reject_proposal(
    session: Session, scope: CatererScope, order_id: UUID, proposal_id: UUID
) -> tuple[AiChangeProposal, Order]:
    order, proposal = _lock_pending(session, scope, order_id, proposal_id)
    _close(session, proposal, ProposalStatus.REJECTED)
    return proposal, order
