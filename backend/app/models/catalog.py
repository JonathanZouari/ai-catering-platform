"""Catalog tables, mirroring database/migrations/0001_catalog.sql (docs/DATABASE_SCHEMA.md)."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps

PRICING_UNITS = ("per_guest", "per_tray", "per_weight", "per_item")
# The kitchen is kosher and meat-only (OPEN_DECISIONS #9): no dairy dishes. The Postgres enum
# still has 'dairy' (migration 0001); a check constraint (0011) keeps it out.
KASHRUT_CLASSES = ("meat", "pareve")
ALLERGEN_STATUSES = ("contains", "free", "unknown")


class DishCategory(Base):
    __tablename__ = "dish_categories"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Dish(Timestamps, Base):
    __tablename__ = "dishes"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dish_categories.id"), index=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    image_path: Mapped[str | None] = mapped_column(Text)
    pricing_unit: Mapped[str] = mapped_column(Enum(*PRICING_UNITS, name="pricing_unit"))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    unit_label: Mapped[str | None] = mapped_column(Text)
    # shortcut: fixed ILS until currency is decided (OPEN_DECISIONS #17).
    currency: Mapped[str] = mapped_column(String(3), default="ILS")
    min_quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    # How many adult portions one unit serves (OPEN_DECISIONS #3); null = no recommendation.
    serves_adults: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)

    category: Mapped[DishCategory] = relationship(lazy="joined")
    dietary: Mapped["DishDietary | None"] = relationship(
        cascade="all, delete-orphan", lazy="joined"
    )
    allergens: Mapped[list["DishAllergen"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class DishDietary(Base):
    """Null = unknown, never "no" (DATABASE_SCHEMA.md). Kashrut is always known: meat or pareve."""

    __tablename__ = "dish_dietary"
    __table_args__ = (
        CheckConstraint("kashrut_class in ('meat', 'pareve')", name="dish_dietary_meat_or_pareve"),
    )
    dish_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dishes.id", ondelete="CASCADE"), primary_key=True
    )
    kashrut_class: Mapped[str] = mapped_column(
        Enum(*KASHRUT_CLASSES, name="kashrut_class"), default="pareve", server_default="pareve"
    )
    is_vegetarian: Mapped[bool | None] = mapped_column(Boolean)
    is_vegan: Mapped[bool | None] = mapped_column(Boolean)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Allergen(Base):
    __tablename__ = "allergens"
    # smallint identity in the SQL migration; Integer so SQLite autoincrements in tests.
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True)


class DishAllergen(Base):
    """A missing row = unknown."""

    __tablename__ = "dish_allergens"
    dish_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dishes.id", ondelete="CASCADE"), primary_key=True
    )
    allergen_id: Mapped[int] = mapped_column(ForeignKey("allergens.id"), primary_key=True)
    status: Mapped[str] = mapped_column(Enum(*ALLERGEN_STATUSES, name="allergen_status"))
    allergen: Mapped[Allergen] = relationship(lazy="joined")
