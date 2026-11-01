from decimal import Decimal
from typing import Annotated, Self
from uuid import UUID

from pydantic import Field, model_validator

from app.models.enums import AllergenStatus, CategoryType, KashrutClass, PricingUnit
from app.schemas.base import InputModel, OutputModel, PatchModel

Name = Annotated[str, Field(min_length=1, max_length=120)]
Money = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]
Quantity = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]
Calories = Annotated[int, Field(ge=0, le=100_000)]


class CategoryCreate(InputModel):
    name: Name
    category_type: CategoryType = CategoryType.OTHER
    sort_order: int = 0


class CategoryUpdate(PatchModel):
    required_fields = {"name", "category_type", "sort_order", "is_active"}

    name: Name | None = None
    category_type: CategoryType | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class CategoryOut(OutputModel):
    id: UUID
    name: str
    category_type: CategoryType
    sort_order: int
    is_active: bool


class AllergenOut(OutputModel):
    id: int
    name: str


class DishCreate(InputModel):
    category_id: UUID
    name: Name
    description: str | None = None
    pricing_unit: PricingUnit
    unit_price: Money
    unit_label: str | None = None
    servings_per_unit: Quantity | None = None
    calories_per_portion: Calories | None = None
    portion_description: str | None = None
    min_quantity: Quantity | None = None
    is_available: bool = True

    @model_validator(mode="after")
    def _weight_needs_a_label(self) -> Self:
        if self.pricing_unit == PricingUnit.PER_WEIGHT and not self.unit_label:
            raise ValueError("unit_label is required for per_weight pricing")
        return self


class DishUpdate(PatchModel):
    required_fields = {"category_id", "name", "pricing_unit", "unit_price", "is_available"}

    category_id: UUID | None = None
    name: Name | None = None
    description: str | None = None
    pricing_unit: PricingUnit | None = None
    unit_price: Money | None = None
    unit_label: str | None = None
    servings_per_unit: Quantity | None = None
    calories_per_portion: Calories | None = None
    portion_description: str | None = None
    min_quantity: Quantity | None = None
    is_available: bool | None = None


class AllergenEntry(InputModel):
    allergen_id: int
    status: AllergenStatus


class DietaryUpdate(InputModel):
    """Full replacement. Null means unknown; an allergen left out stays unknown."""

    kashrut_class: KashrutClass | None = None
    is_vegetarian: bool | None = None
    is_vegan: bool | None = None
    allergens: list[AllergenEntry] = []

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.is_vegan and self.is_vegetarian is False:
            raise ValueError("a vegan dish is vegetarian")
        if self.kashrut_class == KashrutClass.MEAT and (self.is_vegetarian or self.is_vegan):
            raise ValueError("a meat dish can't be vegetarian or vegan")
        if self.kashrut_class == KashrutClass.DAIRY and self.is_vegan:
            raise ValueError("a dairy dish can't be vegan")
        ids = [entry.allergen_id for entry in self.allergens]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate allergen")
        return self


class DietaryOut(OutputModel):
    kashrut_class: KashrutClass | None
    is_vegetarian: bool | None
    is_vegan: bool | None


class DishAllergenOut(OutputModel):
    allergen_id: int
    status: AllergenStatus


class DishOut(OutputModel):
    id: UUID
    category_id: UUID
    name: str
    description: str | None
    image_path: str | None
    pricing_unit: PricingUnit
    unit_price: Decimal
    unit_label: str | None
    servings_per_unit: Decimal | None
    calories_per_portion: int | None
    portion_description: str | None
    min_quantity: Decimal | None
    is_available: bool
    dietary: DietaryOut | None
    allergens: list[DishAllergenOut]
