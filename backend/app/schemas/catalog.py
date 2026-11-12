import uuid
from decimal import Decimal

from pydantic import BaseModel

from app.core.storage import DISH_IMAGES, public_url
from app.models import AllergenStatus, Dish, DishCategory, KashrutClass, PricingUnit


class CategoryOut(BaseModel):
    id: uuid.UUID
    name: str
    sort_order: int

    @classmethod
    def of(cls, category: DishCategory) -> "CategoryOut":
        return cls(id=category.id, name=category.name, sort_order=category.sort_order)


class DietaryOut(BaseModel):
    """Every null means unknown, never "no"."""

    kashrut: KashrutClass | None = None
    is_vegetarian: bool | None = None
    is_vegan: bool | None = None


class AllergenOut(BaseModel):
    name: str
    status: AllergenStatus


class DishOut(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    name: str
    description: str | None
    image_path: str | None
    image_url: str | None
    pricing_unit: PricingUnit
    # Serialized as a string ("85.00") so money never passes through a float.
    unit_price: Decimal
    unit_label: str | None
    currency: str
    per_guest: float | None
    qty_step: int | None
    is_available: bool
    dietary: DietaryOut
    # One entry per allergen in the owner's list; no row in the database is reported as unknown.
    allergens: list[AllergenOut]

    @classmethod
    def of(cls, dish: Dish, allergen_names: list[str]) -> "DishOut":
        d = dish.dietary
        statuses = {a.allergen.name: a.status for a in dish.allergens}
        return cls(
            id=dish.id,
            category_id=dish.category_id,
            name=dish.name,
            description=dish.description,
            image_path=dish.image_path,
            image_url=public_url(DISH_IMAGES, dish.image_path),
            pricing_unit=dish.pricing_unit,
            unit_price=(Decimal(dish.unit_price_agorot) / 100).quantize(Decimal("0.01")),
            unit_label=dish.unit_label,
            currency=dish.currency,
            per_guest=dish.per_guest,
            qty_step=dish.qty_step,
            is_available=dish.is_available,
            dietary=DietaryOut(
                kashrut=d.kashrut_class, is_vegetarian=d.is_vegetarian, is_vegan=d.is_vegan
            )
            if d
            else DietaryOut(),
            allergens=[
                AllergenOut(name=n, status=statuses.get(n, AllergenStatus.UNKNOWN))
                for n in allergen_names
            ],
        )
