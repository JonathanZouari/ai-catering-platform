from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

PricingUnit = Literal["per_guest", "per_tray", "per_weight", "per_item"]
KashrutClass = Literal["meat", "dairy", "pareve"]


class Category(BaseModel):
    id: int
    name: str
    sort_order: int


class Dish(BaseModel):
    id: int
    category_id: int
    name: str
    description: str | None
    image_path: str | None
    pricing_unit: PricingUnit
    # Serialized as a string ("85.00") so clients never round a float price.
    unit_price: Decimal
    unit_label: str | None
    currency: str
    min_quantity: float | None
    # None means unknown, never "no" (decision 9).
    kashrut_class: KashrutClass | None
    is_vegetarian: bool | None
    is_vegan: bool | None


class AllergenStatus(BaseModel):
    name: str
    status: Literal["contains", "free", "unknown"]


class DishDetail(Dish):
    allergens: list[AllergenStatus]
