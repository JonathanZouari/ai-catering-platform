from datetime import date, time
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Numeric, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin
from app.models.enums import FulfillmentType, pg_enum


class DeliveryZone(TenantMixin, Base):
    __tablename__ = "delivery_zones"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str]
    fee: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    definition: Mapped[dict] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))

    @property
    def cities(self) -> list[str]:
        return self.definition.get("cities", [])


class TimeSlot(TenantMixin, Base):
    __tablename__ = "time_slots"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    fulfillment_type: Mapped[FulfillmentType] = mapped_column(
        pg_enum(FulfillmentType, "fulfillment_type")
    )
    weekday: Mapped[int | None]
    start_time: Mapped[time]
    end_time: Mapped[time]
    capacity: Mapped[int | None]
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))


class BlockedDate(TenantMixin, Base):
    __tablename__ = "blocked_dates"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    date: Mapped[date]
    reason: Mapped[str | None]
