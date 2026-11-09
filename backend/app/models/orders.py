from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin
from app.models.catalog import Dish
from app.models.enums import FulfillmentType, OrderStatus, PricingUnit, pg_enum
from app.models.logistics import DeliveryZone, TimeSlot


class Customer(TenantMixin, Base):
    __tablename__ = "customers"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    full_name: Mapped[str]
    phone: Mapped[str]
    email: Mapped[str | None]


class Event(TenantMixin, Base):
    __tablename__ = "events"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id"))
    event_type: Mapped[str]
    event_date: Mapped[date]
    adults: Mapped[int]
    children: Mapped[int]
    vegetarian_guests: Mapped[int]
    vegan_guests: Mapped[int]
    restricted_guests: Mapped[int]
    dietary_notes: Mapped[str | None]


class Order(TenantMixin, Base):
    __tablename__ = "orders"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    access_token_hash: Mapped[str] = mapped_column(unique=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id"))
    event_id: Mapped[UUID] = mapped_column(ForeignKey("events.id"))
    status: Mapped[OrderStatus] = mapped_column(
        pg_enum(OrderStatus, "order_status"), server_default=text("'draft'")
    )
    version: Mapped[int] = mapped_column(server_default=text("1"))
    fulfillment_type: Mapped[FulfillmentType] = mapped_column(
        pg_enum(FulfillmentType, "fulfillment_type")
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    time_slot_id: Mapped[UUID] = mapped_column(ForeignKey("time_slots.id"))
    delivery_city: Mapped[str | None]
    delivery_address: Mapped[str | None]
    delivery_zone_id: Mapped[UUID | None] = mapped_column(ForeignKey("delivery_zones.id"))
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    delivery_fee: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    total: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    kashrut_warning_acknowledged: Mapped[bool] = mapped_column(server_default=text("false"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None]

    customer: Mapped[Customer] = relationship(lazy="selectin")
    event: Mapped[Event] = relationship(lazy="selectin")
    time_slot: Mapped[TimeSlot] = relationship(lazy="selectin")
    delivery_zone: Mapped[DeliveryZone | None] = relationship(lazy="selectin")
    items: Mapped[list["OrderItem"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class OrderItem(TenantMixin, Base):
    __tablename__ = "order_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id"))
    dish_id: Mapped[UUID] = mapped_column(ForeignKey("dishes.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    snapshot_name: Mapped[str | None]
    snapshot_pricing_unit: Mapped[PricingUnit | None] = mapped_column(
        pg_enum(PricingUnit, "pricing_unit")
    )
    snapshot_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    snapshot_line_total: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    dish: Mapped[Dish] = relationship(lazy="selectin")
