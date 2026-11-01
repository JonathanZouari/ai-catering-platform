import hashlib
import secrets
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import AppError, not_found
from app.core.tenancy import CatererScope
from app.models import Caterer, Customer, Dish, Event, Order, OrderItem
from app.models.enums import FulfillmentType, OrderStatus, PricingUnit
from app.repositories.catalog import DishRepository
from app.repositories.caterers import get_own_caterer
from app.repositories.logistics import (
    BlockedDateRepository,
    DeliveryZoneRepository,
    TimeSlotRepository,
)
from app.repositories.orders import (
    CustomerRepository,
    EventRepository,
    OrderRepository,
    get_quantity_rules,
)
from app.schemas.orders import (
    CustomerOut,
    EventOut,
    ItemSet,
    KashrutCheck,
    OrderCreated,
    OrderDetails,
    OrderLine,
    OrderOut,
    OrderUpdate,
    SubmitRequest,
)
from app.services import availability, kashrut, pricing, quantities


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _apply_details(session: Session, scope: CatererScope, order: Order, data: OrderDetails) -> None:
    slot = availability.require_open_slot(
        TimeSlotRepository(session, scope),
        BlockedDateRepository(session, scope),
        data.event.event_date,
        data.time_slot_id,
        data.fulfillment_type,
    )
    order.fulfillment_type = data.fulfillment_type
    order.time_slot = slot
    order.time_slot_id = slot.id
    order.requested_at = availability.requested_at(data.event.event_date, slot)

    if data.fulfillment_type == FulfillmentType.DELIVERY:
        zones = DeliveryZoneRepository(session, scope).list_all()
        zone = availability.find_zone(zones, data.delivery_city)
        order.delivery_zone = zone
        order.delivery_zone_id = zone.id
        order.delivery_city = data.delivery_city
        order.delivery_address = data.delivery_address
    else:
        order.delivery_zone = None
        order.delivery_zone_id = None
        order.delivery_city = None
        order.delivery_address = None


def create_order(session: Session, caterer: Caterer, data: OrderDetails) -> OrderCreated:
    scope = CatererScope(caterer.id)
    customer = CustomerRepository(session, scope).add(Customer(**data.customer.model_dump()))
    session.flush()
    event = EventRepository(session, scope).add(
        Event(customer_id=customer.id, **data.event.model_dump())
    )
    session.flush()

    token = secrets.token_urlsafe(32)
    order = Order(
        access_token_hash=hash_token(token),
        customer=customer,
        customer_id=customer.id,
        event=event,
        event_id=event.id,
        status=OrderStatus.DRAFT,
        version=1,
        items=[],
    )
    _apply_details(session, scope, order, data)
    OrderRepository(session, scope).add(order)
    session.commit()
    return OrderCreated(token=token, order=view(session, scope, order))


def get_order(session: Session, scope: CatererScope, order_id: UUID) -> Order:
    order = OrderRepository(session, scope).get(order_id)
    if order is None:
        raise not_found()
    return order


def _lock_draft(repo: OrderRepository, order_id: UUID, version: int) -> Order:
    order = repo.lock(order_id)
    if order is None:
        raise not_found()
    if order.status != OrderStatus.DRAFT:
        raise AppError(409, "invalid_transition", "ההזמנה כבר נשלחה ואי אפשר לשנות אותה")
    if order.version != version:
        raise AppError(409, "order_version_conflict", "ההזמנה השתנתה. טענו את הדף מחדש")
    return order


def update_order(session: Session, scope: CatererScope, order_id: UUID, data: OrderUpdate) -> Order:
    order = _lock_draft(OrderRepository(session, scope), order_id, data.version)
    for field, value in data.customer.model_dump().items():
        setattr(order.customer, field, value)
    for field, value in data.event.model_dump().items():
        setattr(order.event, field, value)
    _apply_details(session, scope, order, data)
    order.version += 1
    session.commit()
    return order


def _require_orderable(dish: Dish | None) -> Dish:
    if dish is None:
        raise not_found()
    if not dish.is_available or not dish.category.is_active:
        raise AppError(409, "dish_unavailable", f'המנה "{dish.name}" אינה זמינה כרגע')
    return dish


def set_item(
    session: Session, scope: CatererScope, order_id: UUID, dish_id: UUID, data: ItemSet
) -> Order:
    order = _lock_draft(OrderRepository(session, scope), order_id, data.version)
    dish = _require_orderable(DishRepository(session, scope).get(dish_id))
    if dish.pricing_unit != PricingUnit.PER_WEIGHT and data.quantity != int(data.quantity):
        raise AppError(422, "validation_error", "הכמות חייבת להיות מספר שלם")

    item = next((row for row in order.items if row.dish_id == dish_id), None)
    if item is None:
        order.items.append(
            OrderItem(
                caterer_id=scope.caterer_id, dish=dish, dish_id=dish.id, quantity=data.quantity
            )
        )
    else:
        item.quantity = data.quantity
    order.version += 1
    session.commit()
    return order


def remove_item(
    session: Session, scope: CatererScope, order_id: UUID, dish_id: UUID, version: int
) -> Order:
    order = _lock_draft(OrderRepository(session, scope), order_id, version)
    item = next((row for row in order.items if row.dish_id == dish_id), None)
    if item is None:
        raise not_found()
    order.items.remove(item)
    order.version += 1
    session.commit()
    return order


def _delivery_fee(order: Order) -> Decimal:
    zone = order.delivery_zone
    return zone.fee if order.fulfillment_type == FulfillmentType.DELIVERY and zone else Decimal(0)


def _require_capacity(repo: OrderRepository, order: Order) -> None:
    capacity = order.time_slot.capacity
    if capacity is None:
        return
    repo.lock_slot(order.time_slot_id)
    booked = repo.count_booked(order.time_slot_id, order.event.event_date, order.id)
    if booked >= capacity:
        raise AppError(409, "slot_full", "השעה שנבחרה כבר מלאה. בחרו שעה אחרת")


def submit_order(
    session: Session, scope: CatererScope, order_id: UUID, data: SubmitRequest
) -> Order:
    repo = OrderRepository(session, scope)
    order = _lock_draft(repo, order_id, data.version)
    caterer = get_own_caterer(session, scope)
    if not caterer.is_active:
        raise not_found()
    if not order.items:
        raise AppError(422, "empty_order", "יש לבחור לפחות מנה אחת")

    # Everything can have changed since the draft was edited, so all of it is checked again.
    availability.require_open_slot(
        TimeSlotRepository(session, scope),
        BlockedDateRepository(session, scope),
        order.event.event_date,
        order.time_slot_id,
        order.fulfillment_type,
    )
    if order.fulfillment_type == FulfillmentType.DELIVERY:
        zones = DeliveryZoneRepository(session, scope).list_all()
        order.delivery_zone = availability.find_zone(zones, order.delivery_city)
        order.delivery_zone_id = order.delivery_zone.id
    _require_capacity(repo, order)

    dishes = [_require_orderable(item.dish) for item in order.items]
    for item in order.items:
        minimum = item.dish.min_quantity
        if minimum is not None and item.quantity < minimum:
            message = f'הכמות המינימלית של "{item.dish.name}" היא {minimum}'
            raise AppError(422, "below_minimum", message)

    check = kashrut.check_order(dishes, caterer.kashrut_mixing_rule)
    if check.status == "blocked":
        message = "העסק לא מאפשר הזמנה שמערבת מנות בשריות וחלביות"
        raise AppError(409, "kashrut_mixing_blocked", message)
    if check.status == "warn" and not data.acknowledge_kashrut_warning:
        message = "יש לאשר את האזהרה על מנות בשריות וחלביות באותה הזמנה"
        raise AppError(409, "kashrut_warning_not_acknowledged", message)

    for item in order.items:
        item.snapshot_name = item.dish.name
        item.snapshot_pricing_unit = item.dish.pricing_unit
        item.snapshot_unit_price = item.dish.unit_price
        item.snapshot_line_total = pricing.line_total(item.dish.unit_price, item.quantity)

    order.delivery_fee = _delivery_fee(order)
    order.subtotal, order.total = pricing.order_total(
        [item.snapshot_line_total for item in order.items], order.delivery_fee
    )
    order.kashrut_warning_acknowledged = check.status == "warn"
    order.status = OrderStatus.PENDING_APPROVAL
    order.submitted_at = datetime.now(UTC)
    order.version += 1
    session.commit()
    return order


def _submitted_lines(order: Order) -> list[OrderLine]:
    return [
        OrderLine(
            dish_id=item.dish_id,
            name=item.snapshot_name,
            pricing_unit=item.snapshot_pricing_unit,
            unit_price=item.snapshot_unit_price,
            quantity=item.quantity,
            line_total=item.snapshot_line_total,
            recommended_quantity=None,
        )
        for item in order.items
    ]


def _draft_lines(session: Session, scope: CatererScope, order: Order) -> list[OrderLine]:
    dishes = [item.dish for item in order.items]
    rules = get_quantity_rules(session, scope.caterer_id)
    recommended = quantities.recommend(dishes, order.event, rules)
    return [
        OrderLine(
            dish_id=item.dish_id,
            name=item.dish.name,
            pricing_unit=item.dish.pricing_unit,
            unit_price=item.dish.unit_price,
            quantity=item.quantity,
            line_total=pricing.line_total(item.dish.unit_price, item.quantity),
            recommended_quantity=recommended[item.dish_id],
        )
        for item in order.items
    ]


def view(session: Session, scope: CatererScope, order: Order) -> OrderOut:
    is_draft = order.status == OrderStatus.DRAFT
    lines = _draft_lines(session, scope, order) if is_draft else _submitted_lines(order)

    if is_draft:
        fee = _delivery_fee(order)
        subtotal, total = pricing.order_total([line.line_total for line in lines], fee)
    else:
        fee, subtotal, total = order.delivery_fee, order.subtotal, order.total

    rule = get_own_caterer(session, scope).kashrut_mixing_rule
    dishes = [item.dish for item in order.items]
    check: KashrutCheck = kashrut.check_order(dishes, rule)

    return OrderOut(
        id=order.id,
        status=order.status,
        version=order.version,
        fulfillment_type=order.fulfillment_type,
        requested_at=order.requested_at,
        time_slot_id=order.time_slot_id,
        delivery_city=order.delivery_city,
        delivery_address=order.delivery_address,
        customer=CustomerOut.model_validate(order.customer),
        event=EventOut.model_validate(order.event),
        lines=lines,
        subtotal=subtotal,
        delivery_fee=fee,
        total=total,
        kashrut=check,
        decision_note=order.decision_note,
    )
