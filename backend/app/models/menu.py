import enum
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps

# shortcut: SQLite stores Numeric as float, so cents can drift locally; Postgres is exact.
Money = Numeric(10, 2)


class PricingUnit(enum.StrEnum):
    per_guest = "per_guest"
    per_tray = "per_tray"
    per_weight = "per_weight"
    per_item = "per_item"


# docs/DATABASE_SCHEMA.md "dish_categories" and "dishes".
class DishCategory(Base):
    __tablename__ = "dish_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    sort_order: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)


class Dish(Timestamps, Base):
    __tablename__ = "dishes"
    __table_args__ = (CheckConstraint("unit_price >= 0", name="price_non_negative"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("dish_categories.id"), index=True)
    name: Mapped[str]
    description: Mapped[str | None]
    image_path: Mapped[str | None]
    pricing_unit: Mapped[PricingUnit]
    unit_price: Mapped[Decimal] = mapped_column(Money)
    unit_label: Mapped[str | None]
    # No default: the currency is still OPEN #17.
    currency: Mapped[str] = mapped_column(String(3))
    min_quantity: Mapped[Decimal | None] = mapped_column(Money)
    is_available: Mapped[bool] = mapped_column(default=True)
