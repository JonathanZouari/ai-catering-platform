import datetime
import math
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field(min_length=1, max_length=100)
    date: datetime.date
    slot: str = Field(min_length=1, max_length=20)
    fulfillment: Literal["pickup", "delivery"]
    city: str = Field(default="", max_length=100)
    address: str = Field(default="", max_length=300)
    adults: int = Field(ge=1, le=10000)
    children: int = Field(ge=0, le=10000)
    vegetarian: int = Field(ge=0, le=10000)
    vegan: int = Field(ge=0, le=10000)
    restricted: int = Field(ge=0, le=10000)
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def check_consistency(self) -> "Event":
        if self.vegetarian + self.vegan + self.restricted > self.adults + self.children:
            raise ValueError("dietary guests exceed total guests")
        if self.fulfillment == "delivery" and not (self.city and self.address.strip()):
            raise ValueError("delivery requires city and address")
        return self


class Contact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    phone: str

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        v = v.strip()
        if not 1 <= len(v) <= 100:
            raise ValueError("name must be 1-100 characters")
        return v

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, v: str) -> str:
        v = re.sub(r"[\s-]", "", v)
        if not re.fullmatch(r"0\d{8,9}", v):
            raise ValueError("invalid phone")
        return v


class OrderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Event
    items: dict[str, float] = Field(min_length=1, max_length=100)
    contact: Contact

    @field_validator("items")
    @classmethod
    def check_quantities(cls, v: dict[str, float]) -> dict[str, float]:
        if not all(math.isfinite(q) and 0 < q <= 100000 for q in v.values()):
            raise ValueError("quantity must be > 0 and <= 100000")
        return v
