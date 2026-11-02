"""Customer-side order DTOs (screen C1: event configuration and draft order)."""

import uuid
from datetime import date
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
    requested_at: UtcDatetime
    delivery_address: str | None
    decision_note: str | None
    event: EventOut
