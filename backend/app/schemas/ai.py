from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import KashrutClass, ProposalStatus
from app.schemas.base import InputModel, OutputModel
from app.schemas.catalog import Quantity
from app.schemas.orders import Guests, OrderOut


class AddItem(InputModel):
    type: Literal["add_item"]
    dish_id: UUID
    quantity: Quantity


class RemoveItem(InputModel):
    type: Literal["remove_item"]
    dish_id: UUID


class SetQuantity(InputModel):
    type: Literal["set_quantity"]
    dish_id: UUID
    quantity: Quantity


class UpdateDetails(InputModel):
    """Only these fields can change here. Date, time and delivery stay in the form."""

    type: Literal["update_details"]
    adults: Guests | None = None
    children: Guests | None = None
    vegetarian_guests: Guests | None = None
    vegan_guests: Guests | None = None
    restricted_guests: Guests | None = None
    dietary_notes: str | None = Field(default=None, max_length=1000)


Change = Annotated[AddItem | RemoveItem | SetQuantity | UpdateDetails, Field(discriminator="type")]


class ProposeChanges(InputModel):
    changes: list[Change] = Field(min_length=1, max_length=20)
    rationale: str = Field(min_length=1, max_length=500)


class NoArguments(InputModel):
    pass


class DishFilters(InputModel):
    category_id: UUID | None = None
    vegetarian: bool = False
    vegan: bool = False
    kashrut: KashrutClass | None = None


class DishLookup(InputModel):
    dish_id: UUID


class ChatRequest(InputModel):
    message: str = Field(min_length=1, max_length=1000)

    @field_validator("message")
    @classmethod
    def _storable(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("a message cannot hold a null character")
        return value


class ProposalOut(OutputModel):
    id: UUID
    status: ProposalStatus
    rationale: str
    changes: list[dict[str, Any]]
    price_before: Decimal
    price_after: Decimal


class ChatMessageOut(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class ChatReply(BaseModel):
    reply: str
    proposals: list[ProposalOut]


class ChatState(BaseModel):
    available: bool
    messages: list[ChatMessageOut]
    proposals: list[ProposalOut]


class ProposalDecision(BaseModel):
    proposal: ProposalOut
    order: OrderOut
