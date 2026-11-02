from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.availability import BlockedDate, TimeSlot


def list_blocked(
    db: Session, start: date | None = None, end: date | None = None
) -> list[BlockedDate]:
    q = select(BlockedDate).order_by(BlockedDate.date)
    if start:
        q = q.where(BlockedDate.date >= start)
    if end:
        q = q.where(BlockedDate.date <= end)
    return list(db.scalars(q))


def list_slots(db: Session, active_only: bool = False) -> list[TimeSlot]:
    q = select(TimeSlot).order_by(
        TimeSlot.fulfillment_type,
        TimeSlot.weekday.is_not(None),  # "every day" slots first
        TimeSlot.weekday,
        TimeSlot.start_time,
    )
    if active_only:
        q = q.where(TimeSlot.is_active)
    return list(db.scalars(q))
