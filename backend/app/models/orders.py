from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin
from app.models.catalog import Dish
from app.models.enums import FulfillmentType, OrderStatus, PricingUnit, db_enum
from app.models.logistics import DeliveryZone, TimeSlot
from app.models.types import Hundredths, UtcDateTime


class Customer(TenantMixin, Base):
    __tablename__ = "customers"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    full_name: Mapped[str]
    phone: Mapped[str]
    email: Mapped[str | None]


class Event(TenantMixin, Base):
    __tablename__ = "events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
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

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    access_token_hash: Mapped[str] = mapped_column(unique=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id"))
    event_id: Mapped[UUID] = mapped_column(ForeignKey("events.id"))
    status: Mapped[OrderStatus] = mapped_column(
        db_enum(OrderStatus), server_default=text("'draft'")
    )
    version: Mapped[int] = mapped_column(server_default=text("1"))
    fulfillment_type: Mapped[FulfillmentType] = mapped_column(db_enum(FulfillmentType))
    requested_at: Mapped[datetime] = mapped_column(UtcDateTime)
    time_slot_id: Mapped[UUID] = mapped_column(ForeignKey("time_slots.id"))
    delivery_city: Mapped[str | None]
    delivery_address: Mapped[str | None]
    delivery_zone_id: Mapped[UUID | None] = mapped_column(ForeignKey("delivery_zones.id"))
    subtotal: Mapped[Decimal | None] = mapped_column(Hundredths)
    delivery_fee: Mapped[Decimal | None] = mapped_column(Hundredths)
    total: Mapped[Decimal | None] = mapped_column(Hundredths)
    kashrut_warning_acknowledged: Mapped[bool] = mapped_column(server_default=text("false"))
    submitted_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    decided_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    decision_note: Mapped[str | None]

    customer: Mapped[Customer] = relationship(lazy="selectin")
    event: Mapped[Event] = relationship(lazy="selectin")
    time_slot: Mapped[TimeSlot] = relationship(lazy="selectin")
    delivery_zone: Mapped[DeliveryZone | None] = relationship(lazy="selectin")
    items: Mapped[list["OrderItem"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class OrderItem(TenantMixin, Base):
    __tablename__ = "order_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id"))
    dish_id: Mapped[UUID] = mapped_column(ForeignKey("dishes.id"))
    quantity: Mapped[Decimal] = mapped_column(Hundredths)
    snapshot_name: Mapped[str | None]
    snapshot_pricing_unit: Mapped[PricingUnit | None] = mapped_column(db_enum(PricingUnit))
    snapshot_unit_price: Mapped[Decimal | None] = mapped_column(Hundredths)
    snapshot_line_total: Mapped[Decimal | None] = mapped_column(Hundredths)

    dish: Mapped[Dish] = relationship(lazy="selectin")
