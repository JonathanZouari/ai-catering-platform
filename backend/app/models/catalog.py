from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import ForeignKey, Numeric, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin
from app.models.enums import AllergenStatus, KashrutClass, PricingUnit, pg_enum


class DishCategory(TenantMixin, Base):
    __tablename__ = "dish_categories"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str]
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
    calories_per_portion: Mapped[int | None]
    portion_description: Mapped[str | None]
    min_quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    is_available: Mapped[bool] = mapped_column(server_default=text("true"))

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


class DishAllergen(Base):
    __tablename__ = "dish_allergens"

    dish_id: Mapped[UUID] = mapped_column(ForeignKey("dishes.id"), primary_key=True)
    allergen_id: Mapped[int] = mapped_column(ForeignKey("allergens.id"), primary_key=True)
    status: Mapped[AllergenStatus] = mapped_column(pg_enum(AllergenStatus, "allergen_status"))
