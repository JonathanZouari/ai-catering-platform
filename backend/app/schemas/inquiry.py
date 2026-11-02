from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

EventType = Literal["birthday", "family_celebration", "bar_bat_mitzvah", "shabbat_holiday", "other"]


class InquiryCreate(BaseModel):
    """Landing-page event inquiry. Not an order: no dishes, no pricing."""

    name: str = Field(min_length=1, max_length=120)
    email: str = Field(max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    phone: str | None = Field(default=None, max_length=40, pattern=r"^[\d\s()+\-.]{6,40}$")
    event_type: EventType
    event_date: date
    guests: int = Field(ge=1, le=2000)
    fulfillment: Literal["pickup", "delivery"]
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be blank")
        return v.strip()

    @field_validator("event_date")
    @classmethod
    def not_in_past(cls, v: date) -> date:
        if v < date.today():
            raise ValueError("event_date must be today or later")
        return v
