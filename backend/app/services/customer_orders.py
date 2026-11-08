"""Customer side of orders: event (C1), items (C2), pricing (C3), submit and withdraw (C5).

Rules (backend-authoritative, ADR 0003):
- the customer must have a profile; ownership comes from the token only (ADR 0005)
- event date: at least settings.lead_days after today (Israel time) and not blocked
- the slot must be active, of the chosen fulfillment type, and valid for the event's weekday;
  pickup/delivery happens on the event date at the slot's start time
- dietary groups are subsets of adults + children; vegetarian and vegan are separate groups,
  so vegetarian + vegan <= total too (OPEN_DECISIONS #4)
- delivery needs a street address and a city served by an active zone (OPEN #19); the fee is
  the zone's current fee while draft and is frozen at submission
- edits only while draft, and only against the version the client saw (optimistic lock)
- submit: everything above is checked again, every dish must still be orderable, and the slot
  must have room (capacity per slot per event date, OPEN #5); prices are then frozen into the
  snapshot. Withdraw (OPEN #7) only while awaiting approval; it unfreezes the prices.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core import clock
from app.core.customer_auth import CustomerIdentity
from app.core.errors import AppError
from app.models.availability import TimeSlot
from app.models.catalog import Dish
from app.models.orders import Customer, Event, Order, OrderItem
from app.models.proposals import OrderProposal
from app.repositories import availability as availability_repo
from app.repositories import catalog as catalog_repo
from app.repositories import customers as customers_repo
from app.repositories import orders as orders_repo
from app.schemas import customer_orders as s
from app.services import delivery as delivery_svc
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

    if data.fulfillment_type == "delivery":
        if not data.delivery_address:
            raise _invalid("delivery_address", "A delivery address is required")
        served = data.delivery_city and delivery_svc.delivery_for(db, data.delivery_city)
        if not served:
            raise _invalid("delivery_city", "We don't deliver to this city", "city_not_served")
        data.delivery_city = served[0]  # one spelling per city: the zone's, or the CBS one
    local = datetime.combine(e.event_date, slot.start_time, tzinfo=clock.BUSINESS_TZ)
    return local.astimezone(UTC)


def _apply(order: Order, event: Event, data: s.DraftIn, requested_at: datetime) -> None:
    for key, value in data.event.model_dump().items():
        setattr(event, key, value)
    order.fulfillment_type = data.fulfillment_type
    order.slot_id = data.slot_id
    order.requested_at = requested_at
    delivery = data.fulfillment_type == "delivery"
    order.delivery_address = data.delivery_address if delivery else None
    order.delivery_city = data.delivery_city if delivery else None


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


def _commit_bump(
    db: Session,
    who: CustomerIdentity,
    order_id: uuid.UUID,
    version: int,
    *,
    from_status: str = "draft",
    to_status: str | None = None,
):
    """Flush the pending change, bump the version (and maybe move status) in one transaction.

    The conditional UPDATE is the lock: it only lands if nobody saved or decided in between.
    """
    db.flush()
    values = {"version": Order.version + 1}
    if to_status:
        values["status"] = to_status
    bumped = db.execute(
        update(Order)
        .where(Order.id == order_id, Order.version == version, Order.status == from_status)
        .values(**values)
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


def check_quantity(dish: Dish, quantity: Decimal) -> None:
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
    check_quantity(dish, data.quantity)
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


def _live_fee(db: Session, order: Order) -> Decimal | None:
    if order.fulfillment_type != "delivery" or not order.delivery_city:
        return None
    served = delivery_svc.delivery_for(db, order.delivery_city)
    return served[1] if served else None


def get_pricing(db: Session, who: CustomerIdentity, order_id: uuid.UUID) -> s.PricingOut:
    order = _owned(db, who, order_id)
    dishes = {i.dish_id: db.get(Dish, i.dish_id) for i in order.items}
    return s.PricingOut.model_validate(pricing.price_order(order, dishes, _live_fee(db, order)))


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


# submit and withdraw (C5)


def _as_draft_in(order: Order) -> s.DraftIn:
    if order.slot_id is None:  # the slot was deleted, or the order predates slot_id
        raise _invalid("slot_id", "Pick a time again", "slot_unavailable")
    event = {k: getattr(order.event, k) for k in s.EventIn.model_fields}
    return s.DraftIn(
        event=event,
        fulfillment_type=order.fulfillment_type,
        slot_id=order.slot_id,
        delivery_address=order.delivery_address,
        delivery_city=order.delivery_city,
    )


def _expire_proposals(db: Session, order_id: uuid.UUID) -> None:
    """The order changes stage: an open proposal no longer applies (same transaction)."""
    db.execute(
        update(OrderProposal)
        .where(OrderProposal.order_id == order_id, OrderProposal.status == "pending")
        .values(status="expired", decided_at=datetime.now(UTC))
    )


def submit(
    db: Session,
    who: CustomerIdentity,
    order_id: uuid.UUID,
    version: int,
    adult_confirmed: bool = False,
) -> s.CustomerOrderOut:
    order = _editable(db, who, order_id, version)
    if not order.items:
        raise AppError(422, "empty_order", "Add at least one dish")
    dishes = {i.dish_id: db.get(Dish, i.dish_id) for i in order.items}
    gone = sorted(d.name for d in dishes.values() if not pricing.orderable(d))
    if gone:
        raise AppError(
            409, "items_unavailable", "Some dishes can't be ordered anymore", {"dishes": gone}
        )
    has_alcohol = any(d.contains_alcohol for d in dishes.values())
    if has_alcohol and not adult_confirmed:
        raise AppError(422, "age_confirmation_required", "Alcohol is sold to 18+ only")
    order.adult_confirmed_at = datetime.now(UTC) if has_alcohol else None
    order.requested_at = _validate(db, _as_draft_in(order))  # date, lead time, slot, guests

    # Lock the slot row (Postgres) so two last-minute submits can't both take the last place.
    slot = db.execute(select(TimeSlot).where(TimeSlot.id == order.slot_id).with_for_update())
    slot = slot.scalar_one()
    taken = orders_repo.slot_load(db, slot.id, order.event.event_date, exclude=order.id)
    if slot.capacity is not None and taken >= slot.capacity:
        raise AppError(409, "slot_full", "This time is fully booked for that date")

    # _validate made sure a delivery city is served
    priced = pricing.price_order(order, dishes, _live_fee(db, order))
    for item in order.items:
        dish = dishes[item.dish_id]
        item.snapshot_name = dish.name
        item.snapshot_pricing_unit = dish.pricing_unit
        item.snapshot_unit_price = dish.unit_price
        item.snapshot_line_total = pricing.line_total(item.quantity, dish.unit_price)
    order.subtotal = priced.subtotal
    order.delivery_fee = priced.delivery_fee  # frozen with the prices
    order.total = priced.total
    order.submitted_at = datetime.now(UTC)
    _expire_proposals(db, order_id)  # an assistant proposal was for the draft
    return _commit_bump(db, who, order_id, version, to_status="pending_approval")


def withdraw(
    db: Session, who: CustomerIdentity, order_id: uuid.UUID, version: int
) -> s.CustomerOrderOut:
    order = _owned(db, who, order_id)
    if order.status != "pending_approval":
        raise AppError(
            409, "invalid_transition", "Only an order awaiting approval can be withdrawn"
        )
    if order.version != version:
        raise AppError(409, "order_version_conflict", "The order changed; reload it")
    for item in order.items:  # back to live prices
        item.snapshot_name = item.snapshot_pricing_unit = None
        item.snapshot_unit_price = item.snapshot_line_total = None
    order.subtotal = order.total = order.submitted_at = order.adult_confirmed_at = None
    order.delivery_fee = None  # live from the zone again
    _expire_proposals(db, order_id)  # an owner proposal was for the submitted order
    return _commit_bump(
        db, who, order_id, version, from_status="pending_approval", to_status="draft"
    )
