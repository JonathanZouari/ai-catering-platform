import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PricingUnit(enum.StrEnum):
    """Decision 6. Values match docs/DATABASE_SCHEMA.md."""

    PER_GUEST = "per_guest"
    PER_TRAY = "per_tray"
    PER_WEIGHT = "per_weight"
    PER_ITEM = "per_item"


class KashrutClass(enum.StrEnum):
    """Decision 9."""

    MEAT = "meat"
    DAIRY = "dairy"
    PAREVE = "pareve"


class AllergenStatus(enum.StrEnum):
    """Decision 9: unknown is never the same as free. A missing dish_allergens row means unknown."""

    CONTAINS = "contains"
    FREE = "free"
    UNKNOWN = "unknown"


def _str_enum(enum_cls: type[enum.Enum], length: int) -> Enum:
    # Stored as checked text so the same schema works on SQLite and Postgres.
    return Enum(
        enum_cls,
        native_enum=False,
        create_constraint=True,
        length=length,
        values_callable=lambda e: [m.value for m in e],
    )


class DishCategory(Base):
    __tablename__ = "dish_categories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, unique=True)
    sort_order: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)

    dishes: Mapped[list["Dish"]] = relationship(back_populates="category")


class Dish(Base):
    __tablename__ = "dishes"
    __table_args__ = (
        CheckConstraint("unit_price_agorot >= 0", name="ck_dishes_price_non_negative"),
        CheckConstraint("per_guest IS NULL OR per_guest > 0", name="ck_dishes_per_guest_positive"),
        CheckConstraint("qty_step IS NULL OR qty_step > 0", name="ck_dishes_qty_step_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dish_categories.id"), index=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    image_path: Mapped[str | None] = mapped_column(Text)
    pricing_unit: Mapped[PricingUnit] = mapped_column(_str_enum(PricingUnit, 16))
    # Money is stored in agorot (integer) so SQLite never rounds it.
    unit_price_agorot: Mapped[int]
    unit_label: Mapped[str | None] = mapped_column(Text)  # OPEN #18
    currency: Mapped[str] = mapped_column(String(3), default="ILS")  # OPEN #17
    # PLACEHOLDER quantity hints until quantity_rules exist (OPEN #3).
    per_guest: Mapped[float | None]
    qty_step: Mapped[int | None]
    is_available: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    category: Mapped[DishCategory] = relationship(back_populates="dishes")
    dietary: Mapped["DishDietary | None"] = relationship(
        back_populates="dish", cascade="all, delete-orphan"
    )
    allergens: Mapped[list["DishAllergen"]] = relationship(
        back_populates="dish", cascade="all, delete-orphan"
    )


class DishDietary(Base):
    """1:1 with dishes. Every null means "not provided" and must be shown as unknown."""

    __tablename__ = "dish_dietary"

    dish_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dishes.id", ondelete="CASCADE"), primary_key=True
    )
    kashrut_class: Mapped[KashrutClass | None] = mapped_column(_str_enum(KashrutClass, 8))
    is_vegetarian: Mapped[bool | None]
    is_vegan: Mapped[bool | None]
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    dish: Mapped[Dish] = relationship(back_populates="dietary")


class Allergen(Base):
    """The allergen list is maintained by the owner."""

    __tablename__ = "allergens"

    # SQLite only auto-numbers an INTEGER primary key; Postgres keeps smallint (DATABASE_SCHEMA.md).
    id: Mapped[int] = mapped_column(
        SmallInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(Text, unique=True)


class DishAllergen(Base):
    __tablename__ = "dish_allergens"

    dish_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dishes.id", ondelete="CASCADE"), primary_key=True
    )
    allergen_id: Mapped[int] = mapped_column(ForeignKey("allergens.id"), primary_key=True)
    status: Mapped[AllergenStatus] = mapped_column(_str_enum(AllergenStatus, 8))

    dish: Mapped[Dish] = relationship(back_populates="allergens")
    allergen: Mapped[Allergen] = relationship()
