from typing import Literal

from pydantic import BaseModel

PricingUnit = Literal["per_guest", "per_tray", "per_weight", "per_item"]
KashrutClass = Literal["meat", "dairy", "pareve"]
AllergenStatus = Literal["contains", "free", "unknown"]


def format_agorot(amount: int) -> str:
    """Integer agorot -> decimal string like the contract's "1200.00". Money is never a float."""
    return f"{amount // 100}.{amount % 100:02d}"


class Category(BaseModel):
    id: str
    name: str
    sort_order: int


class Dish(BaseModel):
    id: str
    category_id: str
    name: str
    description: str | None
    image_path: str | None
    pricing_unit: PricingUnit
    unit_price: str
    unit_label: str | None
    currency: str
    min_quantity: float | None
    # None = not provided. Clients must show it as unknown, never as "no".
    kashrut_class: KashrutClass | None
    is_vegetarian: bool | None
    is_vegan: bool | None


class DishAllergen(BaseModel):
    id: int
    name: str
    status: AllergenStatus


class DishDetail(Dish):
    # Every known allergen is listed; "unknown" is explicit, never an omission.
    allergens: list[DishAllergen]
