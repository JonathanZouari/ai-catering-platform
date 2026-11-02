"""Availability tables, mirroring database/migrations/0002_availability.sql."""

import uuid
from datetime import date, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum,
    Integer,
    SmallInteger,
    Text,
    Time,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

FULFILLMENT_TYPES = ("pickup", "delivery")
# One shared type: orders.fulfillment_type uses the same Postgres enum.
FulfillmentType = Enum(*FULFILLMENT_TYPES, name="fulfillment_type")


class TimeSlot(Base):
    __tablename__ = "time_slots"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="time_slots_order"),
        CheckConstraint("weekday between 0 and 6", name="time_slots_weekday"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    fulfillment_type: Mapped[str] = mapped_column(FulfillmentType)
    # 0 = Sunday ... 6 = Saturday (same as JS Date.getDay); null = every day.
    weekday: Mapped[int | None] = mapped_column(SmallInteger)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    # shortcut: stored but not enforced until OPEN_DECISIONS #5 defines capacity rules.
    capacity: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BlockedDate(Base):
    __tablename__ = "blocked_dates"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    date: Mapped[date] = mapped_column(Date, unique=True)
    reason: Mapped[str | None] = mapped_column(Text)
