"""Leads: draft orders scored with the chance that the customer submits them.

The model is trained offline (`app/ml/train.py`) and stored as plain coefficients in
`app/ml/lead_model.json`, so scoring needs no ML library on the server.
"""

import json
import math
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from app.core import clock
from app.models.orders import Order
from app.repositories import orders as repo
from app.schemas import leads as s

MODEL_PATH = Path(__file__).resolve().parents[1] / "ml" / "lead_model.json"

# Same list as EVENT_TYPES in frontend/js/event.js; any other text is the baseline ("other").
EVENT_TYPE_FEATURES = {
    "בר / בת מצווה": "type_bar_mitzvah",
    "ברית": "type_brit",
    "חתונה": "type_wedding",
    "אירוסין": "type_engagement",
    "יום הולדת": "type_birthday",
    "אירוע חברה": "type_company",
    "שבת": "type_shabbat",
}

# Only what is known when the customer leaves their details: items and totals change later.
FEATURES: tuple[str, ...] = (
    "guests",
    "has_children",
    "days_to_event",
    "is_delivery",
    "has_phone",
    "dietary_share",
    *EVENT_TYPE_FEATURES.values(),
)


def features(order: Order) -> dict[str, float]:
    """The model inputs for one order; training and scoring both go through here."""
    event = order.event
    guests = event.adults + event.children
    dietary = event.vegetarian_guests + event.vegan_guests + event.restricted_guests
    row = {
        "guests": float(guests),
        "has_children": float(event.children > 0),
        "days_to_event": float(max((event.event_date - order.created_at.date()).days, 0)),
        "is_delivery": float(order.fulfillment_type == "delivery"),
        "has_phone": float(bool(order.customer.phone)),
        "dietary_share": min(dietary / guests, 1.0),
        **dict.fromkeys(EVENT_TYPE_FEATURES.values(), 0.0),
    }
    if name := EVENT_TYPE_FEATURES.get(event.event_type):
        row[name] = 1.0
    return row


def score(row: dict[str, float], model: dict) -> float:
    """Purchase probability in 0..1 from the chosen model's coefficients."""
    kind = model["chosen"]
    weights = model["models"][kind]
    z = weights["intercept"] + sum(
        coef * (row[name] - mean) / scale
        for name, coef, mean, scale in zip(
            model["features"], weights["coef"], model["mean"], model["scale"], strict=True
        )
    )
    if kind == "linear":
        return min(1.0, max(0.0, z))  # a linear model can leave 0..1
    return 1 / (1 + math.exp(-z))


@lru_cache
def load_model() -> dict:
    model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    if tuple(model["features"]) != FEATURES:
        raise RuntimeError("lead_model.json does not match FEATURES; rerun app.ml.train")
    return model


def list_leads(db: Session) -> s.LeadsOut:
    model = load_model()
    leads = [
        s.LeadOut(
            order_id=o.id,
            customer_name=o.customer.full_name,
            phone=o.customer.phone,
            email=o.customer.email,
            event_type=o.event.event_type,
            event_date=o.event.event_date,
            guests=o.event.adults + o.event.children,
            fulfillment_type=o.fulfillment_type,
            created_at=o.created_at,
            score=round(score(features(o), model), 3),
        )
        for o in repo.list_orders(db, ("draft",))
        if o.event.event_date >= clock.today()  # a past event can no longer be ordered
    ]
    return s.LeadsOut(
        model_source=model["source"],
        model_kind=model["chosen"],
        trained_at=model["trained_at"],
        leads=sorted(leads, key=lambda lead: lead.score, reverse=True),
    )
