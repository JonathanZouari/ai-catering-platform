"""Customer order DTOs: event configuration (C1), items, pricing, recommendations (C2/C3)."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.orders import OrderStatus, UtcDatetime

EventType = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=60)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
Address = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]
Count = Annotated[int, Field(ge=0, le=5000)]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EventIn(_In):
    event_type: EventType
    event_date: date
    adults: Count
    children: Count = 0
    # Subsets of adults + children (OPEN_DECISIONS #4).
    vegetarian_guests: Count = 0
    vegan_guests: Count = 0
    restricted_guests: Count = 0
    dietary_notes: Notes | None = None


class DraftIn(_In):
    """Full event configuration. The slot fixes the pickup/delivery time on the event date."""

    event: EventIn
    fulfillment_type: Literal["pickup", "delivery"]
    slot_id: uuid.UUID
    delivery_address: Address | None = None


class DraftUpdate(DraftIn):
    version: int  # the version the client last saw; stale -> 409 order_version_conflict


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    event_type: str
    event_date: date
    adults: int
    children: int
    vegetarian_guests: int
    vegan_guests: int
    restricted_guests: int
    dietary_notes: str | None


class CustomerOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    status: OrderStatus
    version: int
    fulfillment_type: Literal["pickup", "delivery"]
    slot_id: uuid.UUID | None
    requested_at: UtcDatetime
    delivery_address: str | None
    subtotal: Decimal | None
    delivery_fee: Decimal | None
    total: Decimal | None
    submitted_at: UtcDatetime | None
    decided_at: UtcDatetime | None
    decision_note: str | None
    event: EventOut
    items: list["OrderItemOut"]


class ItemIn(_In):
    """Set a dish's quantity. Units: whole units, or kg in 0.5 steps for per_weight dishes."""

    quantity: Decimal = Field(gt=0, le=10_000, max_digits=7, decimal_places=2)
    version: int


class VersionIn(_In):
    version: int


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    dish_id: uuid.UUID
    quantity: Decimal


class PricingLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    dish_id: uuid.UUID
    name: str
    pricing_unit: str
    unit_label: str | None
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal
    available: bool  # false: the dish can't be ordered anymore and is left out of the total


class PricingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    currency: Literal["ILS"] = "ILS"
    vat_included: Literal[True] = True
    lines: list[PricingLineOut]
    subtotal: Decimal
    delivery_fee: Decimal | None
    total: Decimal


class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    dish_id: uuid.UUID
    quantity: Decimal
    eligible_guests: int
