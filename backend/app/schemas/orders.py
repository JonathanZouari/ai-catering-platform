import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints

OrderStatus = Literal["draft", "pending_approval", "approved", "rejected"]
# Statuses the owner sees; drafts are still the customer's work in progress.
OwnerStatus = Literal["pending_approval", "approved", "rejected"]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
# Stored as UTC; SQLite hands it back without tzinfo, so mark it before it reaches the browser.


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


UtcDatetime = Annotated[datetime, AfterValidator(_as_utc)]


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
    requested_at: UtcDatetime
    total: Decimal | None
    submitted_at: UtcDatetime | None


class OrderDetailOut(_Out):
    id: uuid.UUID
    status: OrderStatus
    version: int
    fulfillment_type: Literal["pickup", "delivery"]
    requested_at: UtcDatetime
    delivery_address: str | None
    subtotal: Decimal | None
    delivery_fee: Decimal | None
    total: Decimal | None
    submitted_at: UtcDatetime | None
    decided_at: UtcDatetime | None
    decision_note: str | None
    customer: CustomerOut
    event: EventOut
    items: list[OrderItemOut]
