"""ORM models matching docs/DATABASE_SCHEMA.md.

Column types are portable so the same models run on SQLite (local default) and Postgres.
Unknown dietary data is NULL / a missing row and must never be read as "no".
"""

import enum
import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PricingUnit(enum.StrEnum):
    per_guest = "per_guest"
    per_tray = "per_tray"
    per_weight = "per_weight"
    per_item = "per_item"


class KashrutClass(enum.StrEnum):
    meat = "meat"
    dairy = "dairy"
    pareve = "pareve"


class FulfillmentType(enum.StrEnum):
    pickup = "pickup"
    delivery = "delivery"


class OrderStatus(enum.StrEnum):
    draft = "draft"
    pending_approval = "pending_approval"
    approved = "approved"
    rejected = "rejected"


class ProposalStatus(enum.StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"
    failed = "failed"


class AllergenStatus(enum.StrEnum):
    contains = "contains"
    free = "free"
    unknown = "unknown"


def _enum(cls: type[enum.Enum]) -> SAEnum:
    # Stored as text with a CHECK constraint: works on SQLite and Postgres alike.
    return SAEnum(
        cls, native_enum=False, create_constraint=True, length=32, name=cls.__name__.lower()
    )


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


def _updated() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


MONEY = Numeric(10, 2)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = _uuid_pk()
    auth_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, unique=True)
    full_name: Mapped[str] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("adults >= 0 AND children >= 0", name="guests_non_negative"),
        CheckConstraint("adults + children > 0", name="has_guests"),
        CheckConstraint(
            "vegetarian_guests >= 0 AND vegan_guests >= 0 AND restricted_guests >= 0",
            name="dietary_guests_non_negative",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"))
    event_type: Mapped[str] = mapped_column(Text)
    event_date: Mapped[date] = mapped_column(Date)
    adults: Mapped[int] = mapped_column(Integer)
    children: Mapped[int] = mapped_column(Integer)
    vegetarian_guests: Mapped[int] = mapped_column(Integer, default=0)
    vegan_guests: Mapped[int] = mapped_column(Integer, default=0)
    restricted_guests: Mapped[int] = mapped_column(Integer, default=0)
    dietary_notes: Mapped[str | None] = mapped_column(Text)


class DishCategory(Base):
    __tablename__ = "dish_categories"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text, unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(default=True)

    dishes: Mapped[list["Dish"]] = relationship(back_populates="category")


class Dish(Base):
    __tablename__ = "dishes"
    __table_args__ = (CheckConstraint("unit_price >= 0", name="unit_price_non_negative"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dish_categories.id"), index=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    image_path: Mapped[str | None] = mapped_column(Text)
    pricing_unit: Mapped[PricingUnit] = mapped_column(_enum(PricingUnit))
    unit_price: Mapped[Decimal] = mapped_column(MONEY)
    unit_label: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(String(3), default="ILS")  # OPEN #17
    min_quantity: Mapped[Decimal | None] = mapped_column(MONEY)
    is_available: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()

    category: Mapped[DishCategory] = relationship(back_populates="dishes")
    dietary: Mapped["DishDietary | None"] = relationship(back_populates="dish", uselist=False)
    allergens: Mapped[list["DishAllergen"]] = relationship(back_populates="dish")


class DishDietary(Base):
    __tablename__ = "dish_dietary"

    dish_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dishes.id"), primary_key=True)
    kashrut_class: Mapped[KashrutClass | None] = mapped_column(_enum(KashrutClass))
    is_vegetarian: Mapped[bool | None] = mapped_column()
    is_vegan: Mapped[bool | None] = mapped_column()
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    dish: Mapped[Dish] = relationship(back_populates="dietary")


class Allergen(Base):
    __tablename__ = "allergens"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, unique=True)


class DishAllergen(Base):
    """A missing row means the allergen status is unknown."""

    __tablename__ = "dish_allergens"

    dish_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dishes.id"), primary_key=True)
    allergen_id: Mapped[int] = mapped_column(ForeignKey("allergens.id"), primary_key=True)
    status: Mapped[AllergenStatus] = mapped_column(_enum(AllergenStatus))

    dish: Mapped[Dish] = relationship(back_populates="allergens")
    allergen: Mapped[Allergen] = relationship()


class DeliveryZone(Base):
    __tablename__ = "delivery_zones"
    __table_args__ = (CheckConstraint("fee >= 0", name="fee_non_negative"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text)
    fee: Mapped[Decimal] = mapped_column(MONEY)
    definition: Mapped[dict] = mapped_column(JSON)  # shape depends on OPEN #19
    is_active: Mapped[bool] = mapped_column(default=True)


class TimeSlot(Base):
    __tablename__ = "time_slots"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="slot_ends_after_start"),
        CheckConstraint("weekday IS NULL OR (weekday >= 0 AND weekday <= 6)", name="weekday_range"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    fulfillment_type: Mapped[FulfillmentType] = mapped_column(_enum(FulfillmentType))
    weekday: Mapped[int | None] = mapped_column(SmallInteger)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    capacity: Mapped[int | None] = mapped_column(Integer)  # OPEN #5
    is_active: Mapped[bool] = mapped_column(default=True)


class BlockedDate(Base):
    __tablename__ = "blocked_dates"

    id: Mapped[uuid.UUID] = _uuid_pk()
    date: Mapped[date] = mapped_column(Date, unique=True)
    reason: Mapped[str | None] = mapped_column(Text)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "fulfillment_type != 'delivery' OR delivery_address IS NOT NULL",
            name="delivery_needs_address",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"), unique=True)
    status: Mapped[OrderStatus] = mapped_column(
        _enum(OrderStatus), default=OrderStatus.draft, index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    fulfillment_type: Mapped[FulfillmentType] = mapped_column(_enum(FulfillmentType))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    delivery_address: Mapped[str | None] = mapped_column(Text)
    delivery_zone_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("delivery_zones.id"))
    subtotal: Mapped[Decimal | None] = mapped_column(MONEY)
    delivery_fee: Mapped[Decimal | None] = mapped_column(MONEY)
    total: Mapped[Decimal | None] = mapped_column(MONEY)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        UniqueConstraint("order_id", "dish_id"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    dish_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dishes.id"))
    quantity: Mapped[Decimal] = mapped_column(MONEY)
    # Price snapshot: filled on submission, authoritative once the order is pending_approval.
    snapshot_name: Mapped[str | None] = mapped_column(Text)
    snapshot_pricing_unit: Mapped[PricingUnit | None] = mapped_column(_enum(PricingUnit))
    snapshot_unit_price: Mapped[Decimal | None] = mapped_column(MONEY)
    snapshot_line_total: Mapped[Decimal | None] = mapped_column(MONEY)

    order: Mapped[Order] = relationship(back_populates="items")
    dish: Mapped[Dish] = relationship()


class AiConversation(Base):
    __tablename__ = "ai_conversations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    created_at: Mapped[datetime] = _created()


class AiMessage(Base):
    __tablename__ = "ai_messages"
    __table_args__ = (CheckConstraint("role IN ('user', 'assistant', 'tool')", name="role_valid"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_conversations.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[dict | list] = mapped_column(JSON)
    created_at: Mapped[datetime] = _created()


class AiChangeProposal(Base):
    __tablename__ = "ai_change_proposals"
    __table_args__ = (
        # At most one pending proposal per order (RECOMMENDATION in the schema doc).
        Index(
            "uq_one_pending_proposal_per_order",
            "order_id",
            unique=True,
            sqlite_where=text("status = 'pending'"),
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_conversations.id"))
    base_order_version: Mapped[int] = mapped_column(Integer)
    changes: Mapped[list] = mapped_column(JSON)
    price_before: Mapped[Decimal] = mapped_column(MONEY)
    price_after: Mapped[Decimal] = mapped_column(MONEY)
    status: Mapped[ProposalStatus] = mapped_column(
        _enum(ProposalStatus), default=ProposalStatus.pending
    )
    created_at: Mapped[datetime] = _created()
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
