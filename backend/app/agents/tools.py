"""Typed tools. The session, scope and order are bound by the server (from the private link
token), so nothing the model sends can point a tool at another order or caterer."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.tenancy import CatererScope
from app.schemas.ai import DishFilters, DishLookup, NoArguments, ProposalOut, ProposeChanges
from app.services import assistant, proposals


@dataclass
class ToolContext:
    session: Session
    scope: CatererScope
    order_id: UUID
    conversation_id: UUID


@dataclass
class Tool:
    description: str
    arguments: type[BaseModel]
    run: Callable[[ToolContext, Any], dict[str, Any]]


def _propose(context: ToolContext, data: ProposeChanges) -> dict[str, Any]:
    proposal = proposals.create_proposal(
        context.session, context.scope, context.order_id, context.conversation_id, data
    )
    return {
        "proposal": ProposalOut.model_validate(proposal).model_dump(mode="json"),
        "order_changed": False,
        "next_step": "הלקוח צריך לאשר או לדחות את הכרטיס שעל המסך",
    }


def _order_tool(read: Callable[..., dict[str, Any]]) -> Callable[[ToolContext, Any], dict]:
    return lambda context, _: read(context.session, context.scope, context.order_id)


TOOLS: dict[str, Tool] = {
    "get_menu_categories": Tool(
        "קטגוריות התפריט הפעילות של העסק.",
        NoArguments,
        lambda context, _: assistant.menu_categories(context.session, context.scope),
    ),
    "get_available_dishes": Tool(
        "מנות זמינות עם מחיר, יחידה, תזונה וקלוריות. סינון מחזיר רק ערכים מאושרים.",
        DishFilters,
        lambda context, args: assistant.available_dishes(context.session, context.scope, args),
    ),
    "get_dish_details": Tool(
        "כל פרטי המנה, כולל סטטוס של כל אלרגן.",
        DishLookup,
        lambda context, args: assistant.dish_details(context.session, context.scope, args.dish_id),
    ),
    "get_current_order": Tool(
        "ההזמנה הנוכחית: מנות, כמויות והרכב הסועדים.",
        NoArguments,
        _order_tool(assistant.current_order),
    ),
    "get_order_pricing": Tool(
        "תמחור ההזמנה כפי שחושב במערכת, כולל מע״מ.",
        NoArguments,
        _order_tool(assistant.order_pricing),
    ),
    "get_quantity_recommendations": Tool(
        "כמויות מומלצות למנות שבהזמנה, לפי מספר הסועדים.",
        NoArguments,
        _order_tool(assistant.quantity_recommendations),
    ),
    "get_kashrut_check": Tool(
        "סטטוס הכשרות של העסק ובדיקת ערבוב בשר וחלב בהזמנה.",
        NoArguments,
        _order_tool(assistant.kashrut_summary),
    ),
    "propose_order_change": Tool(
        "מציע שינוי בהזמנה ללקוח. ההזמנה לא משתנה עד שהלקוח מאשר את הכרטיס.",
        ProposeChanges,
        _propose,
    ),
}


def definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "description": tool.description,
            "input_schema": tool.arguments.model_json_schema(),
        }
        for name, tool in TOOLS.items()
    ]


def run_tool(context: ToolContext, name: str, arguments: Any) -> tuple[str, bool]:
    """Returns (result JSON, is_error). Failures go back to the model, never to a partial write."""
    tool = TOOLS.get(name)
    try:
        if tool is None:
            return json.dumps({"error": "unknown_tool"}), True
        result = tool.run(context, tool.arguments.model_validate(arguments))
    except ValidationError as error:
        problems = [item["type"] for item in error.errors()]
        return json.dumps({"error": "invalid_arguments", "details": problems}), True
    except AppError as error:
        context.session.rollback()
        body = {"error": error.code, "message": error.message}
        return json.dumps(body, ensure_ascii=False), True
    except SQLAlchemyError:
        # For example a quantity too large to store. The model gets an error, not the customer.
        context.session.rollback()
        return json.dumps({"error": "invalid_proposal"}), True
    return json.dumps(result, ensure_ascii=False), False
