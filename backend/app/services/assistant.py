"""What the assistant may read, and its chat history and limits. Everything here is scoped,
and the customer's name, phone and address never leave this module toward the model."""

from collections.abc import Sequence
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, not_found
from app.core.tenancy import CatererScope
from app.models import AiConversation, AiMessage, Dish
from app.models.enums import OrderStatus
from app.repositories import ai as repo
from app.repositories.catalog import CategoryRepository, DishRepository, list_allergens
from app.repositories.caterers import get_own_caterer
from app.schemas.ai import ChatMessageOut, DishFilters
from app.schemas.orders import OrderOut
from app.services import availability, orders

MESSAGES_PER_ORDER = 100
UNKNOWN = "unknown"


def _known(value: Any) -> Any:
    """Unknown stays unknown: the model sees the word, never an empty value it might fill."""
    return UNKNOWN if value is None else value


def _dish_summary(dish: Dish) -> dict[str, Any]:
    dietary = dish.dietary
    return {
        "dish_id": str(dish.id),
        "category_id": str(dish.category_id),
        "name": dish.name,
        "description": dish.description,
        "pricing_unit": dish.pricing_unit.value,
        "unit_price": str(dish.unit_price),
        "unit_label": dish.unit_label,
        "calories_per_portion": _known(dish.calories_per_portion),
        "kashrut_class": _known(
            dietary.kashrut_class.value if dietary and dietary.kashrut_class else None
        ),
        "is_vegetarian": _known(dietary.is_vegetarian if dietary else None),
        "is_vegan": _known(dietary.is_vegan if dietary else None),
    }


def menu_categories(session: Session, scope: CatererScope) -> dict[str, Any]:
    categories = CategoryRepository(session, scope).list_all()
    return {
        "categories": [
            {"category_id": str(item.id), "name": item.name}
            for item in categories
            if item.is_active
        ]
    }


def available_dishes(session: Session, scope: CatererScope, filters: DishFilters) -> dict[str, Any]:
    dishes = DishRepository(session, scope).list_orderable()
    # A filter only matches confirmed values, the same as on the customer's menu.
    chosen = [
        dish
        for dish in dishes
        if (filters.category_id is None or dish.category_id == filters.category_id)
        and (not filters.vegetarian or (dish.dietary and dish.dietary.is_vegetarian is True))
        and (not filters.vegan or (dish.dietary and dish.dietary.is_vegan is True))
        and (
            filters.kashrut is None
            or (dish.dietary and dish.dietary.kashrut_class == filters.kashrut)
        )
    ]
    return {"dishes": [_dish_summary(dish) for dish in chosen]}


def dish_details(session: Session, scope: CatererScope, dish_id: UUID) -> dict[str, Any]:
    dish = orders.require_orderable(DishRepository(session, scope).get(dish_id))
    statuses = {row.allergen_id: row.status.value for row in dish.allergens}
    allergens = {
        allergen.name: statuses.get(allergen.id, UNKNOWN) for allergen in list_allergens(session)
    }
    return _dish_summary(dish) | {
        "portion_description": dish.portion_description,
        "min_quantity": None if dish.min_quantity is None else str(dish.min_quantity),
        "allergens": allergens,
    }


def _order(session: Session, scope: CatererScope, order_id: UUID) -> OrderOut:
    return orders.view(session, scope, orders.get_order(session, scope, order_id))


def current_order(session: Session, scope: CatererScope, order_id: UUID) -> dict[str, Any]:
    order = _order(session, scope, order_id)
    return {
        "status": order.status.value,
        "fulfillment_type": order.fulfillment_type.value,
        "event": order.event.model_dump(mode="json"),
        "lines": [
            {
                "dish_id": str(line.dish_id),
                "name": line.name,
                "quantity": str(line.quantity),
            }
            for line in order.lines
        ],
    }


def order_pricing(session: Session, scope: CatererScope, order_id: UUID) -> dict[str, Any]:
    order = _order(session, scope, order_id)
    return {
        "lines": [
            {
                "name": line.name,
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
                "line_total": str(line.line_total),
            }
            for line in order.lines
        ],
        "subtotal": str(order.subtotal),
        "delivery_fee": str(order.delivery_fee),
        "total_including_vat": str(order.total),
    }


def quantity_recommendations(
    session: Session, scope: CatererScope, order_id: UUID
) -> dict[str, Any]:
    order = _order(session, scope, order_id)
    return {
        "recommendations": [
            {
                "name": line.name,
                "current_quantity": str(line.quantity),
                "recommended_quantity": _known(
                    None if line.recommended_quantity is None else str(line.recommended_quantity)
                ),
            }
            for line in order.lines
        ]
    }


def kashrut_summary(session: Session, scope: CatererScope, order_id: UUID) -> dict[str, Any]:
    check = _order(session, scope, order_id).kashrut
    return {
        "caterer_kashrut_status": _known(get_own_caterer(session, scope).kashrut_status),
        "order_mixing_status": check.status,
        "some_dishes_have_unknown_kashrut": check.has_unknown,
    }


def caterer_name(session: Session, scope: CatererScope) -> str:
    return get_own_caterer(session, scope).name


def require_draft(session: Session, scope: CatererScope, order_id: UUID) -> None:
    if not get_own_caterer(session, scope).is_active:
        raise not_found()
    if orders.get_order(session, scope, order_id).status != OrderStatus.DRAFT:
        raise AppError(409, "invalid_transition", "ההזמנה כבר נשלחה ואי אפשר לשנות אותה")


def get_conversation(
    session: Session, scope: CatererScope, order_id: UUID
) -> AiConversation | None:
    return repo.ConversationRepository(session, scope).for_order(order_id)


def _this_month() -> date:
    return availability.today().replace(day=1)


def consume_allowance(session: Session, scope: CatererScope, order_id: UUID) -> None:
    """Called before the AI runs. At the limit, chat stops and hand ordering carries on."""
    limit_reached = AppError(429, "ai_limit_reached", "העוזר אינו זמין כרגע. אפשר להמשיך בתפריט")
    conversation = get_conversation(session, scope, order_id)
    if conversation is not None:
        sent = repo.MessageRepository(session, scope).count_from_customer(conversation.id)
        if sent >= MESSAGES_PER_ORDER:
            raise limit_reached
    limit = get_settings().ai_monthly_message_limit
    if not repo.consume_message(session, scope.caterer_id, _this_month(), limit):
        session.rollback()
        raise limit_reached
    session.commit()


def open_conversation(session: Session, scope: CatererScope, order_id: UUID) -> AiConversation:
    conversation = get_conversation(session, scope, order_id)
    if conversation is None:
        conversation = repo.ConversationRepository(session, scope).add(
            AiConversation(order_id=order_id)
        )
        session.commit()
    return conversation


def recent_messages(
    session: Session, scope: CatererScope, conversation_id: UUID, limit: int
) -> Sequence[AiMessage]:
    return repo.MessageRepository(session, scope).latest(conversation_id, limit)


def history(session: Session, scope: CatererScope, order_id: UUID) -> list[ChatMessageOut]:
    conversation = get_conversation(session, scope, order_id)
    if conversation is None:
        return []
    messages = recent_messages(session, scope, conversation.id, 2 * MESSAGES_PER_ORDER)
    return [ChatMessageOut(role=item.role, text=item.content["text"]) for item in messages]


def save_exchange(
    session: Session, scope: CatererScope, conversation_id: UUID, question: str, answer: str
) -> None:
    messages = repo.MessageRepository(session, scope)
    for role, text in (("user", question), ("assistant", answer)):
        messages.add(AiMessage(conversation_id=conversation_id, role=role, content={"text": text}))
    session.commit()
