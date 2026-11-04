from datetime import date, time
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import JSON, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin
from app.models.enums import FulfillmentType, db_enum
from app.models.types import Hundredths


class DeliveryZone(TenantMixin, Base):
    __tablename__ = "delivery_zones"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str]
    fee: Mapped[Decimal] = mapped_column(Hundredths)
    definition: Mapped[dict] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))

    @property
    def cities(self) -> list[str]:
        return self.definition.get("cities", [])


class TimeSlot(TenantMixin, Base):
    __tablename__ = "time_slots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    fulfillment_type: Mapped[FulfillmentType] = mapped_column(db_enum(FulfillmentType))
    weekday: Mapped[int | None]
    start_time: Mapped[time]
    end_time: Mapped[time]
    capacity: Mapped[int | None]
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))


class BlockedDate(TenantMixin, Base):
    __tablename__ = "blocked_dates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    date: Mapped[date]
    reason: Mapped[str | None]
