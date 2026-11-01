from collections.abc import Sequence
from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Customer, Event, Order, QuantityRule, TimeSlot
from app.models.enums import CategoryType, OrderStatus
from app.repositories.base import ScopedRepository

COUNTS_AGAINST_CAPACITY = (OrderStatus.PENDING_APPROVAL, OrderStatus.APPROVED)


class CustomerRepository(ScopedRepository[Customer]):
    model = Customer


class EventRepository(ScopedRepository[Event]):
    model = Event


class OrderRepository(ScopedRepository[Order]):
    model = Order

    def lock(self, order_id: UUID) -> Order | None:
        query = (
            self._select()
            .where(Order.id == order_id)
            .with_for_update(of=Order)
            .execution_options(populate_existing=True)
        )
        return self.session.scalar(query)

    def lock_slot(self, slot_id: UUID) -> None:
        """Serializes capacity checks, so two submissions can't take the last place."""
        query = select(TimeSlot.id).where(
            TimeSlot.id == slot_id, TimeSlot.caterer_id == self.scope.caterer_id
        )
        self.session.scalar(query.with_for_update())

    def count_booked(self, slot_id: UUID, event_date: date, excluding: UUID) -> int:
        query = (
            select(func.count())
            .select_from(Order)
            .join(Event, Event.id == Order.event_id)
            .where(
                Order.caterer_id == self.scope.caterer_id,
                Order.time_slot_id == slot_id,
                Order.id != excluding,
                Order.status.in_(COUNTS_AGAINST_CAPACITY),
                Event.event_date == event_date,
            )
        )
        return self.session.scalar(query) or 0


def get_order_by_token_hash(session: Session, token_hash: str) -> Order | None:
    """The token is the credential, so this runs before a scope exists."""
    return session.scalar(select(Order).where(Order.access_token_hash == token_hash))


def get_quantity_rules(session: Session, caterer_id: UUID) -> dict[CategoryType, QuantityRule]:
    """Platform defaults with the caterer's own rules applied over them."""
    query = select(QuantityRule).where(
        (QuantityRule.caterer_id.is_(None)) | (QuantityRule.caterer_id == caterer_id)
    )
    rules: Sequence[QuantityRule] = session.scalars(query).all()
    ordered = sorted(rules, key=lambda rule: rule.caterer_id is not None)
    return {rule.category_type: rule for rule in ordered}
