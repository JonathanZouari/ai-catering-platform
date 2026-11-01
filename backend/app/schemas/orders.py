from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from app.models.enums import FulfillmentType, OrderStatus, PricingUnit
from app.schemas.base import InputModel, OutputModel
from app.schemas.catalog import Quantity

Guests = Annotated[int, Field(ge=0, le=100_000)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


class CustomerIn(InputModel):
    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(pattern=r"^[0-9+\-\s]{9,20}$")
    email: str | None = Field(default=None, max_length=200)


class EventIn(InputModel):
    event_type: str = Field(min_length=1, max_length=60)
    event_date: date
    adults: Guests
    children: Guests
    vegetarian_guests: Guests = 0
    vegan_guests: Guests = 0
    restricted_guests: Guests = 0
    dietary_notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _counts_fit_within_guests(self) -> Self:
        total = self.adults + self.children
        if total == 0:
            raise ValueError("an event needs at least one guest")
        if self.vegetarian_guests + self.vegan_guests + self.restricted_guests > total:
            raise ValueError("special diets are counted within the guest total")
        return self


class OrderDetails(InputModel):
    customer: CustomerIn
    event: EventIn
    fulfillment_type: FulfillmentType
    time_slot_id: UUID
    delivery_city: str | None = Field(default=None, max_length=80)
    delivery_address: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _delivery_needs_an_address(self) -> Self:
        if self.fulfillment_type == FulfillmentType.DELIVERY and not (
            self.delivery_city and self.delivery_address
        ):
            raise ValueError("delivery needs a city and an address")
        return self


class OrderUpdate(OrderDetails):
    version: int


class ItemSet(InputModel):
    quantity: Quantity
    version: int


class SubmitRequest(InputModel):
    version: int
    acknowledge_kashrut_warning: bool = False


class ApproveRequest(InputModel):
    version: int
    note: Note | None = None


class RejectRequest(InputModel):
    version: int
    note: Note

    @field_validator("note")
    @classmethod
    def _note_is_not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("a rejection needs a note")
        return value


class CustomerOut(OutputModel):
    full_name: str
    phone: str
    email: str | None


class EventOut(OutputModel):
    event_type: str
    event_date: date
    adults: int
    children: int
    vegetarian_guests: int
    vegan_guests: int
    restricted_guests: int
    dietary_notes: str | None


class OrderLine(BaseModel):
    dish_id: UUID
    name: str
    pricing_unit: PricingUnit
    unit_price: Decimal
    quantity: Decimal
    line_total: Decimal
    recommended_quantity: Decimal | None


class KashrutCheck(BaseModel):
    status: Literal["ok", "warn", "blocked"]
    has_unknown: bool


class OrderOut(BaseModel):
    id: UUID
    status: OrderStatus
    version: int
    fulfillment_type: FulfillmentType
    requested_at: datetime
    time_slot_id: UUID
    delivery_city: str | None
    delivery_address: str | None
    customer: CustomerOut
    event: EventOut
    lines: list[OrderLine]
    subtotal: Decimal
    delivery_fee: Decimal
    total: Decimal
    kashrut: KashrutCheck
    decision_note: str | None


class AdminOrderOut(OrderOut):
    submitted_at: datetime | None
    decided_at: datetime | None
    kashrut_warning_acknowledged: bool


class OrderSummary(BaseModel):
    id: UUID
    status: OrderStatus
    customer_name: str
    event_date: date
    guests: int
    total: Decimal
    submitted_at: datetime | None


class OrderCreated(BaseModel):
    token: str
    order: OrderOut
