import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
Money = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]
Quantity = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]
PricingUnit = Literal["per_guest", "per_tray", "per_weight", "per_item"]
Kashrut = Literal["meat", "pareve"]  # kosher meat kitchen, no dairy (OPEN_DECISIONS #9)


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CategoryCreate(_In):
    name: Name
    sort_order: int = Field(0, ge=0, le=10_000)
    is_active: bool = True


class CategoryUpdate(_In):
    name: Name | None = None
    sort_order: int | None = Field(None, ge=0, le=10_000)
    is_active: bool | None = None


class CategoryOut(_Out):
    id: uuid.UUID
    name: str
    sort_order: int
    is_active: bool


class DishCreate(_In):
    category_id: uuid.UUID
    name: Name
    description: LongText | None = None
    pricing_unit: PricingUnit
    unit_price: Money
    unit_label: Name | None = None
    min_quantity: Quantity | None = None
    # Adults one unit serves (child = settings.child_portion); null = no recommendation.
    serves_adults: Quantity | None = None
    is_available: bool = True
    contains_alcohol: bool = False


class DishUpdate(_In):
    category_id: uuid.UUID | None = None
    name: Name | None = None
    description: LongText | None = None
    pricing_unit: PricingUnit | None = None
    unit_price: Money | None = None
    unit_label: Name | None = None
    min_quantity: Quantity | None = None
    # Adults one unit serves (child = settings.child_portion); null = no recommendation.
    serves_adults: Quantity | None = None
    is_available: bool | None = None
    contains_alcohol: bool | None = None


class AllergenCreate(_In):
    name: Name


class AllergenOut(_Out):
    id: int
    name: str


class AllergenStatusIn(_In):
    allergen_id: int
    status: Literal["contains", "free", "unknown"]


class DietaryUpdate(_In):
    """Full replacement. null / "unknown" / an omitted allergen all mean unknown."""

    kashrut_class: Kashrut = "pareve"
    is_vegetarian: bool | None = None
    is_vegan: bool | None = None
    allergens: list[AllergenStatusIn] = Field(default_factory=list, max_length=100)


class DietaryOut(_Out):
    kashrut_class: Kashrut = "pareve"
    is_vegetarian: bool | None = None
    is_vegan: bool | None = None
    verified_at: datetime | None = None


class DishAllergenOut(_Out):
    allergen_id: int
    name: str
    status: Literal["contains", "free"]


class DishOut(_Out):
    id: uuid.UUID
    category_id: uuid.UUID
    name: str
    description: str | None
    image_path: str | None
    pricing_unit: PricingUnit
    unit_price: Decimal
    unit_label: str | None
    currency: str
    min_quantity: Decimal | None
    serves_adults: Decimal | None
    is_available: bool
    contains_alcohol: bool
    dietary: DietaryOut
    allergens: list[DishAllergenOut]
