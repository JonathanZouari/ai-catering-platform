import uuid
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.orders import UtcDatetime

Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
Quantity = Annotated[Decimal, Field(gt=0, le=10_000, max_digits=7, decimal_places=2)]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProposedItem(_In):
    dish_id: uuid.UUID
    quantity: Quantity


class ProposalCreate(_In):
    """The full item list the owner wants; the server works out the changes."""

    items: list[ProposedItem] = Field(min_length=1, max_length=100)
    note: Note | None = None


class DeclineIn(_In):
    note: Note | None = None


class ChangeOut(BaseModel):
    op: Literal["add_item", "set_quantity", "remove_item"]
    dish_id: uuid.UUID
    name: str
    from_quantity: Decimal | None = None
    to_quantity: Decimal | None = None


class ProposalLineOut(BaseModel):
    dish_id: uuid.UUID
    name: str
    pricing_unit: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


class ProposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    proposed_by: Literal["owner", "assistant"]
    status: Literal["pending", "accepted", "declined", "cancelled", "expired"]
    base_order_version: int
    changes: list[ChangeOut]
    lines: list[ProposalLineOut]
    price_before: Decimal
    price_after: Decimal
    note: str | None
    customer_note: str | None
    created_at: UtcDatetime
    decided_at: UtcDatetime | None
