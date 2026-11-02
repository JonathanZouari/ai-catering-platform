import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

OrderStatus = Literal["draft", "pending_approval", "approved", "rejected"]
# Statuses the owner sees; drafts are still the customer's work in progress.
OwnerStatus = Literal["pending_approval", "approved", "rejected"]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: Note | None = None


class CustomerOut(_Out):
    full_name: str
    email: str | None
    phone: str | None


class EventOut(_Out):
    event_type: str
    event_date: date
    adults: int
    children: int
    vegetarian_guests: int
    vegan_guests: int
    restricted_guests: int
    dietary_notes: str | None


class OrderItemOut(BaseModel):
    dish_id: uuid.UUID
    name: str | None
    pricing_unit: str | None
    unit_price: Decimal | None
    quantity: Decimal
    line_total: Decimal | None


class OrderSummaryOut(BaseModel):
    id: uuid.UUID
    status: OrderStatus
    customer_name: str
    event_type: str
    event_date: date
    guests: int
    fulfillment_type: Literal["pickup", "delivery"]
    requested_at: datetime
    total: Decimal | None
    submitted_at: datetime | None


class OrderDetailOut(_Out):
    id: uuid.UUID
    status: OrderStatus
    version: int
    fulfillment_type: Literal["pickup", "delivery"]
    requested_at: datetime
    delivery_address: str | None
    subtotal: Decimal | None
    delivery_fee: Decimal | None
    total: Decimal | None
    submitted_at: datetime | None
    decided_at: datetime | None
    decision_note: str | None
    customer: CustomerOut
    event: EventOut
    items: list[OrderItemOut]
