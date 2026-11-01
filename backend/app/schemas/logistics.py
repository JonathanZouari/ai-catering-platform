from datetime import date, time
from typing import Annotated, Self
from uuid import UUID

from pydantic import Field, model_validator

from app.models.enums import FulfillmentType
from app.schemas.base import InputModel, OutputModel, PatchModel
from app.schemas.catalog import Money, Name

City = Annotated[str, Field(min_length=1, max_length=80)]
Cities = Annotated[list[City], Field(min_length=1)]
Weekday = Annotated[int, Field(ge=0, le=6)]
Capacity = Annotated[int, Field(ge=0)]


class ZoneCreate(InputModel):
    name: Name
    fee: Money
    cities: Cities


class ZoneUpdate(PatchModel):
    required_fields = {"name", "fee", "cities", "is_active"}

    name: Name | None = None
    fee: Money | None = None
    cities: Cities | None = None
    is_active: bool | None = None


class ZoneOut(OutputModel):
    id: UUID
    name: str
    fee: Money
    cities: list[str]
    is_active: bool


class SlotCreate(InputModel):
    fulfillment_type: FulfillmentType
    weekday: Weekday | None = None  # Null = every day.
    start_time: time
    end_time: time
    capacity: Capacity | None = None

    @model_validator(mode="after")
    def _end_after_start(self) -> Self:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class SlotUpdate(PatchModel):
    required_fields = {"fulfillment_type", "start_time", "end_time", "is_active"}

    fulfillment_type: FulfillmentType | None = None
    weekday: Weekday | None = None
    start_time: time | None = None
    end_time: time | None = None
    capacity: Capacity | None = None
    is_active: bool | None = None


class SlotOut(OutputModel):
    id: UUID
    fulfillment_type: FulfillmentType
    weekday: int | None
    start_time: time
    end_time: time
    capacity: int | None
    is_active: bool


class BlockedDateCreate(InputModel):
    date: date
    reason: str | None = None


class BlockedDateOut(OutputModel):
    id: UUID
    date: date
    reason: str | None
