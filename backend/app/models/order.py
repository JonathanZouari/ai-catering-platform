import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps
from app.models.menu import Money, PricingUnit


class OrderStatus(enum.StrEnum):
    draft = "draft"
    pending_approval = "pending_approval"
    approved = "approved"
    rejected = "rejected"


class FulfillmentType(enum.StrEnum):
    pickup = "pickup"
    delivery = "delivery"


# docs/DATABASE_SCHEMA.md "orders". delivery_zone_id waits for the delivery_zones table.
class Order(Timestamps, Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "fulfillment_type != 'delivery' OR delivery_address IS NOT NULL",
            name="delivery_needs_address",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), unique=True)
    status: Mapped[OrderStatus] = mapped_column(default=OrderStatus.draft, index=True)
    # Bumped on every change; AI proposals check it before executing.
    version: Mapped[int] = mapped_column(default=1)
    fulfillment_type: Mapped[FulfillmentType]
    requested_at: Mapped[datetime]
    delivery_address: Mapped[str | None]
    subtotal: Mapped[Decimal | None] = mapped_column(Money)
    delivery_fee: Mapped[Decimal | None] = mapped_column(Money)
    total: Mapped[Decimal | None] = mapped_column(Money)
    submitted_at: Mapped[datetime | None]
    decided_at: Mapped[datetime | None]
    decision_note: Mapped[str | None]


# docs/DATABASE_SCHEMA.md "order_items". snapshot_* are filled on submission.
class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        UniqueConstraint("order_id", "dish_id"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    dish_id: Mapped[int] = mapped_column(ForeignKey("dishes.id"))
    quantity: Mapped[Decimal] = mapped_column(Money)
    snapshot_name: Mapped[str | None]
    snapshot_pricing_unit: Mapped[PricingUnit | None]
    snapshot_unit_price: Mapped[Decimal | None] = mapped_column(Money)
    snapshot_line_total: Mapped[Decimal | None] = mapped_column(Money)
