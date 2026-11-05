"""The assistant's tools: thin typed wrappers over services (docs/AI_AGENT_DESIGN.md).

The order is bound by the server from the request (`ctx`); no tool takes an order id, so the
model can't reach another order. Only `propose_order_change` writes, and only a pending
proposal: the order changes when the customer accepts it in the UI, never here.
"""

import json
import logging
import uuid
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from app.core.customer_auth import CustomerIdentity
from app.core.errors import AppError
from app.schemas import proposals as ps
from app.schemas.proposals import Note
from app.services import catalog, customer_orders, proposals, settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Ctx:
    db: Session
    who: CustomerIdentity
    order_id: uuid.UUID


class _Empty(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Propose(BaseModel):
    model_config = ConfigDict(extra="forbid")
    changes: list[ps.ChangeIn] = Field(min_length=1, max_length=50)
    rationale: Note


def _menu(ctx: Ctx, _: _Empty) -> dict:
    dishes = []
    for dish in catalog.list_dishes(ctx.db, public=True):
        out = catalog.to_out(dish)
        dishes.append(
            {
                "dish_id": str(out.id),
                "name": out.name,
                "category": dish.category.name,
                "description": out.description,
                "pricing_unit": out.pricing_unit,
                "unit_label": out.unit_label,
                "unit_price": str(out.unit_price),
                "min_quantity": str(out.min_quantity) if out.min_quantity else None,
                "serves_adults_per_unit": str(out.serves_adults) if out.serves_adults else None,
                "kashrut": out.dietary.kashrut_class,
                "alcohol_18_plus": out.contains_alcohol,
                "vegetarian": out.dietary.is_vegetarian,
                "vegan": out.dietary.is_vegan,
                "allergens": {a.name: a.status for a in out.allergens},
            }
        )
    return {
        "currency": "ILS",
        "prices_include_vat": True,
        "kashrut": "kosher meat kitchen: every dish is meat or pareve, no dairy",
        "kashrut_certificate": settings.get(ctx.db).kashrut_certificate,
        "note": "null dietary value = unknown; an allergen not listed = unknown",
        "dishes": dishes,
    }


def _order(ctx: Ctx, _: _Empty) -> dict:
    order = customer_orders.get_order(ctx.db, ctx.who, ctx.order_id)
    priced = customer_orders.get_pricing(ctx.db, ctx.who, ctx.order_id)
    return {
        "status": order.status,
        "event": order.event.model_dump(mode="json"),
        "fulfillment_type": order.fulfillment_type,
        "delivery_city": order.delivery_city,
        "pricing": priced.model_dump(mode="json"),
    }


def _recommendations(ctx: Ctx, _: _Empty) -> dict:
    recs = customer_orders.get_recommendations(ctx.db, ctx.who, ctx.order_id)
    return {
        "note": "suggested quantity per dish for this event's guests; dishes without a "
        "serving size have no recommendation",
        "recommendations": [r.model_dump(mode="json") for r in recs],
    }


def _propose(ctx: Ctx, args: _Propose) -> dict:
    p = proposals.propose_for_draft(ctx.db, ctx.who, ctx.order_id, args.changes, args.rationale)
    return {
        "proposal_id": str(p.id),
        "status": "pending: shown to the customer as a card to accept or decline",
        "changes": [c.model_dump(mode="json") for c in p.changes],
        "price_before": str(p.price_before),
        "price_after": str(p.price_after),
    }


_NO_ARGS = {"type": "object", "properties": {}, "additionalProperties": False}

TOOLS = [
    {
        "name": "get_menu",
        "description": "The dishes the customer can order now, with price per unit, pricing "
        "unit, minimum quantity, servings per unit, kashrut, vegetarian/vegan, allergens and "
        "whether it is alcohol (sold to 18+ only).",
        "input_schema": _NO_ARGS,
        "strict": True,
    },
    {
        "name": "get_current_order",
        "description": "The customer's draft order: the event (date, adults, children, "
        "vegetarian and vegan guests, dietary notes), pickup or delivery, and the dishes "
        "with backend-computed prices and totals.",
        "input_schema": _NO_ARGS,
        "strict": True,
    },
    {
        "name": "get_quantity_recommendations",
        "description": "Backend-computed suggested quantity per dish for this event's guests.",
        "input_schema": _NO_ARGS,
        "strict": True,
    },
    {
        "name": "propose_order_change",
        "description": "Propose changes to the order's dishes. Nothing changes until the "
        "customer accepts the proposal in the card shown under your reply. A new proposal "
        "replaces your previous open one, so put every change you suggest into one call.",
        "input_schema": {
            "type": "object",
            "properties": {
                "changes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "op": {
                                "type": "string",
                                "enum": ["add_item", "set_quantity", "remove_item"],
                            },
                            "dish_id": {"type": "string", "description": "From get_menu"},
                            "quantity": {
                                "type": ["string", "null"],
                                "description": 'Decimal as a string, e.g. "3" or "2.5" '
                                "(per-weight dishes in 0.5 steps, others whole); null for "
                                "remove_item",
                            },
                        },
                        "required": ["op", "dish_id", "quantity"],
                        "additionalProperties": False,
                    },
                },
                "rationale": {
                    "type": "string",
                    "description": "One or two sentences in Hebrew for the customer",
                },
            },
            "required": ["changes", "rationale"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]

_RUN = {
    "get_menu": (_Empty, _menu),
    "get_current_order": (_Empty, _order),
    "get_quantity_recommendations": (_Empty, _recommendations),
    "propose_order_change": (_Propose, _propose),
}


def run(ctx: Ctx, name: str, raw_input: object) -> tuple[str, bool]:
    """Run one tool call; returns (JSON result, is_error). Errors go back to the model."""
    if name not in _RUN:
        log.info("assistant called an unknown tool")
        return json.dumps({"error": {"code": "unknown_tool", "message": "No such tool"}}), True
    args_model, fn = _RUN[name]
    try:
        result = fn(ctx, args_model.model_validate(raw_input))
        log.info("assistant tool %s ok", name)
        return json.dumps(result, ensure_ascii=False), False
    except ValidationError as exc:
        error = {
            "code": "invalid_arguments",
            "message": "; ".join(
                f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()
            ),
        }
    except AppError as exc:
        ctx.db.rollback()  # nothing half-written stays in the session
        error = {"code": exc.code, "message": exc.message, "details": exc.details}
    log.info("assistant tool %s failed: %s", name, error["code"])
    return json.dumps({"error": error}, ensure_ascii=False, default=str), True
