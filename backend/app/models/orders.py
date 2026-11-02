"""Customers, events, orders and order items, mirroring database/migrations/0003_orders.sql."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.availability import FulfillmentType
from app.models.base import Base, Timestamps
from app.models.catalog import PRICING_UNITS

ORDER_STATUSES = ("draft", "pending_approval", "approved", "rejected")


class Customer(Timestamps, Base):
    __tablename__ = "customers"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Supabase auth.users.id; null for customers created before accounts (e.g. sample data).
    auth_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, unique=True)
    full_name: Mapped[str] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(
            "adults >= 0 and children >= 0 and vegetarian_guests >= 0 and vegan_guests >= 0"
            " and restricted_guests >= 0",
            name="events_counts_non_negative",
        ),
        CheckConstraint("adults + children > 0", name="events_has_guests"),
        # Dietary groups are subsets of adults + children (OPEN_DECISIONS #4, decided 2026-11-02).
        CheckConstraint(
            "vegetarian_guests <= adults + children and vegan_guests <= adults + children"
            " and restricted_guests <= adults + children",
            name="events_dietary_subsets",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"))
    event_type: Mapped[str] = mapped_column(Text)
    event_date: Mapped[date] = mapped_column(Date)
    adults: Mapped[int] = mapped_column(Integer)
    children: Mapped[int] = mapped_column(Integer, default=0)
    vegetarian_guests: Mapped[int] = mapped_column(Integer, default=0)
    vegan_guests: Mapped[int] = mapped_column(Integer, default=0)
    restricted_guests: Mapped[int] = mapped_column(Integer, default=0)
    dietary_notes: Mapped[str | None] = mapped_column(Text)


class Order(Timestamps, Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "fulfillment_type <> 'delivery' or delivery_address is not null",
            name="orders_delivery_address",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"), unique=True)
    status: Mapped[str] = mapped_column(
        Enum(*ORDER_STATUSES, name="order_status"), default="draft", index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    fulfillment_type: Mapped[str] = mapped_column(FulfillmentType)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    delivery_address: Mapped[str | None] = mapped_column(Text)
    # shortcut: no delivery_zone_id until zones are defined (OPEN_DECISIONS #19).
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    delivery_fee: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    total: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)

    customer: Mapped[Customer] = relationship(lazy="joined")
    event: Mapped[Event] = relationship(lazy="joined")
    items: Mapped[list["OrderItem"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="OrderItem.snapshot_name"
    )


class OrderItem(Base):
    """While the order is a draft prices are live; from submission the snapshot is authoritative."""

    __tablename__ = "order_items"
    __table_args__ = (
        UniqueConstraint("order_id", "dish_id"),
        CheckConstraint("quantity > 0", name="order_items_quantity"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    dish_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dishes.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    snapshot_name: Mapped[str | None] = mapped_column(Text)
    snapshot_pricing_unit: Mapped[str | None] = mapped_column(
        Enum(*PRICING_UNITS, name="pricing_unit")
    )
    snapshot_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    snapshot_line_total: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
