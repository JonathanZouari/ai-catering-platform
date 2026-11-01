from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import ForeignKey, Numeric, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin
from app.models.enums import AllergenStatus, CategoryType, KashrutClass, PricingUnit, pg_enum


class DishCategory(TenantMixin, Base):
    __tablename__ = "dish_categories"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str]
    category_type: Mapped[CategoryType] = mapped_column(
        pg_enum(CategoryType, "category_type"), server_default=text("'other'")
    )
    sort_order: Mapped[int] = mapped_column(server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))


class Allergen(Base):
    __tablename__ = "allergens"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)


class Dish(TenantMixin, Base):
    __tablename__ = "dishes"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    category_id: Mapped[UUID] = mapped_column(ForeignKey("dish_categories.id"))
    name: Mapped[str]
    description: Mapped[str | None]
    image_path: Mapped[str | None]
    pricing_unit: Mapped[PricingUnit] = mapped_column(pg_enum(PricingUnit, "pricing_unit"))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    unit_label: Mapped[str | None]
    servings_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    calories_per_portion: Mapped[int | None]
    portion_description: Mapped[str | None]
    min_quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    is_available: Mapped[bool] = mapped_column(server_default=text("true"))

    category: Mapped[DishCategory] = relationship(lazy="joined")
    dietary: Mapped["DishDietary | None"] = relationship(
        cascade="all, delete-orphan", lazy="selectin", uselist=False
    )
    allergens: Mapped[list["DishAllergen"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class DishDietary(Base):
    __tablename__ = "dish_dietary"

    dish_id: Mapped[UUID] = mapped_column(ForeignKey("dishes.id"), primary_key=True)
    kashrut_class: Mapped[KashrutClass | None] = mapped_column(
        pg_enum(KashrutClass, "kashrut_class")
    )
    is_vegetarian: Mapped[bool | None]
    is_vegan: Mapped[bool | None]
    verified_at: Mapped[datetime | None]


class QuantityRule(Base):
    """A null caterer_id is a platform default, so this isn't a TenantMixin model."""

    __tablename__ = "quantity_rules"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    caterer_id: Mapped[UUID | None] = mapped_column(ForeignKey("caterers.id"))
    category_type: Mapped[CategoryType] = mapped_column(pg_enum(CategoryType, "category_type"))
    portions_per_adult: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    portions_per_child: Mapped[Decimal] = mapped_column(Numeric(5, 2))


class DishAllergen(Base):
    __tablename__ = "dish_allergens"

    dish_id: Mapped[UUID] = mapped_column(ForeignKey("dishes.id"), primary_key=True)
    allergen_id: Mapped[int] = mapped_column(ForeignKey("allergens.id"), primary_key=True)
    status: Mapped[AllergenStatus] = mapped_column(pg_enum(AllergenStatus, "allergen_status"))
