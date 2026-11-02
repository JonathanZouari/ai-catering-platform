import uuid
from datetime import date, time
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Reason = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Fulfillment = Literal["pickup", "delivery"]
Weekday = Annotated[int, Field(ge=0, le=6)]
Capacity = Annotated[int, Field(ge=1, le=10_000)]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class BlockedDateCreate(_In):
    date: date
    reason: Reason | None = None


class BlockedDateOut(_Out):
    id: uuid.UUID
    date: date
    reason: str | None


class TimeSlotCreate(_In):
    fulfillment_type: Fulfillment
    weekday: Weekday | None = None
    start_time: time
    end_time: time
    capacity: Capacity | None = None
    is_active: bool = True


class TimeSlotUpdate(_In):
    fulfillment_type: Fulfillment | None = None
    weekday: Weekday | None = None
    start_time: time | None = None
    end_time: time | None = None
    capacity: Capacity | None = None
    is_active: bool | None = None


class PublicSlotOut(_Out):
    id: uuid.UUID
    fulfillment_type: Fulfillment
    weekday: int | None
    start_time: time
    end_time: time


class TimeSlotOut(PublicSlotOut):
    capacity: int | None
    is_active: bool


class AvailabilityOut(BaseModel):
    """Public view: dates only (the owner's reason stays private) and active slots."""

    blocked_dates: list[date]
    time_slots: list[PublicSlotOut]
