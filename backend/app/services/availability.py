"""Availability rules: blocked dates and pickup/delivery time slots.

shortcut: capacity, lead time and same-day orders are not enforced until OPEN_DECISIONS #5.
"""

import uuid
from datetime import date, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.availability import BlockedDate, TimeSlot
from app.repositories import availability as repo
from app.schemas import availability as s

MAX_RANGE = timedelta(days=366)


def _get[T](db: Session, model: type[T], id_, what: str) -> T:
    obj = db.get(model, id_)
    if obj is None:
        raise AppError(404, "not_found", f"{what} not found")
    return obj


# blocked dates


def list_blocked(db: Session) -> list[BlockedDate]:
    return repo.list_blocked(db)


def block_date(db: Session, data: s.BlockedDateCreate) -> BlockedDate:
    blocked = BlockedDate(**data.model_dump())
    db.add(blocked)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "conflict", "This date is already blocked") from exc
    return blocked


def unblock_date(db: Session, blocked_id: uuid.UUID) -> None:
    db.delete(_get(db, BlockedDate, blocked_id, "Blocked date"))
    db.commit()


# time slots


def _check_order(slot: TimeSlot) -> None:
    if slot.end_time <= slot.start_time:
        raise AppError(
            422, "validation_error", "end_time must be after start_time", {"field": "end_time"}
        )


def list_slots(db: Session) -> list[TimeSlot]:
    return repo.list_slots(db)


def create_slot(db: Session, data: s.TimeSlotCreate) -> TimeSlot:
    slot = TimeSlot(**data.model_dump())
    _check_order(slot)
    db.add(slot)
    db.commit()
    return slot


def update_slot(db: Session, slot_id: uuid.UUID, data: s.TimeSlotUpdate) -> TimeSlot:
    slot = _get(db, TimeSlot, slot_id, "Time slot")
    changes = data.model_dump(exclude_unset=True)
    for key in {"fulfillment_type", "start_time", "end_time", "is_active"} & changes.keys():
        if changes[key] is None:
            raise AppError(422, "validation_error", f"{key} cannot be null", {"field": key})
    for key, value in changes.items():
        setattr(slot, key, value)
    try:
        _check_order(slot)
    except AppError:
        db.rollback()  # drop the half-applied change
        raise
    db.commit()
    return slot


def delete_slot(db: Session, slot_id: uuid.UUID) -> None:
    db.delete(_get(db, TimeSlot, slot_id, "Time slot"))
    db.commit()


# public


def availability(db: Session, start: date, end: date) -> s.AvailabilityOut:
    if end < start or end - start > MAX_RANGE:
        raise AppError(
            422, "validation_error", "from must be <= to, at most a year apart", {"field": "to"}
        )
    return s.AvailabilityOut(
        blocked_dates=[b.date for b in repo.list_blocked(db, start, end)],
        time_slots=[
            s.PublicSlotOut.model_validate(t) for t in repo.list_slots(db, active_only=True)
        ],
    )
