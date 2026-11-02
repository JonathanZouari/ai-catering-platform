"""Delivery zones as lists of cities (OPEN_DECISIONS #19), mirroring migration 0008."""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class DeliveryZone(Base):
    __tablename__ = "delivery_zones"
    __table_args__ = (CheckConstraint("fee >= 0", name="delivery_zones_fee"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, unique=True)
    fee: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # ILS, VAT included (#14)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    cities: Mapped[list["DeliveryZoneCity"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="DeliveryZoneCity.city"
    )


class DeliveryZoneCity(Base):
    """A city belongs to at most one zone: the city itself is the key."""

    __tablename__ = "delivery_zone_cities"
    city: Mapped[str] = mapped_column(Text, primary_key=True)
    zone_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("delivery_zones.id", ondelete="CASCADE"), index=True
    )
