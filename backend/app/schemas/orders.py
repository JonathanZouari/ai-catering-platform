from typing import Literal

from pydantic import BaseModel, Field


class OrderEvent(BaseModel):
    type: str = ""
    date: str = ""
    slot: str = ""
    fulfillment: Literal["pickup", "delivery"] = "pickup"
    city: str = ""
    address: str = ""
    adults: int = Field(0, ge=0)
    children: int = Field(0, ge=0)
    vegetarian: int = Field(0, ge=0)
    vegan: int = Field(0, ge=0)
    restricted: int = Field(0, ge=0)
    notes: str = ""


class OrderContact(BaseModel):
    name: str = ""
    phone: str = ""


class OrderItem(BaseModel):
    dish_id: str
    quantity: float = Field(gt=0)


class OrderCreate(BaseModel):
    event: OrderEvent
    contact: OrderContact
    items: list[OrderItem] = []
