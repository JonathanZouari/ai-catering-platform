"""Owner leads screen: open drafts with a purchase-probability score."""

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.schemas.orders import UtcDatetime


class LeadOut(BaseModel):
    order_id: uuid.UUID
    customer_name: str
    phone: str | None
    email: str | None
    event_type: str
    event_date: date
    guests: int
    fulfillment_type: Literal["pickup", "delivery"]
    created_at: UtcDatetime
    score: float


class LeadsOut(BaseModel):
    # "synthetic" until the model is retrained on real orders; the screen warns about it.
    model_source: Literal["synthetic", "db"]
    model_kind: Literal["linear", "logistic"]
    trained_at: UtcDatetime
    leads: list[LeadOut]
