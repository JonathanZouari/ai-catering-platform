from collections.abc import Sequence
from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from app.core.errors import AppError
from app.models import DeliveryZone, TimeSlot
from app.models.enums import FulfillmentType
from app.repositories.logistics import BlockedDateRepository, TimeSlotRepository

TIMEZONE = ZoneInfo("Asia/Jerusalem")


def today() -> date:
    return datetime.now(TIMEZONE).date()


def _weekday(day: date) -> int:
    """Our convention, matching time_slots.weekday: 0 = Sunday."""
    return (day.weekday() + 1) % 7


def require_open_slot(
    slots: TimeSlotRepository,
    blocked: BlockedDateRepository,
    day: date,
    slot_id: UUID,
    fulfillment: FulfillmentType,
) -> TimeSlot:
    if day < today() or day in {item.date for item in blocked.list_all()}:
        raise AppError(422, "date_unavailable", "התאריך שנבחר אינו זמין")
    slot = slots.get(slot_id)
    if (
        slot is None
        or not slot.is_active
        or slot.fulfillment_type != fulfillment
        or (slot.weekday is not None and slot.weekday != _weekday(day))
    ):
        raise AppError(422, "slot_unavailable", "השעה שנבחרה אינה זמינה בתאריך הזה")
    return slot


def requested_at(day: date, slot: TimeSlot) -> datetime:
    return datetime.combine(day, slot.start_time, TIMEZONE)


def find_zone(zones: Sequence[DeliveryZone], city: str) -> DeliveryZone:
    for zone in zones:
        if zone.is_active and city in zone.cities:
            return zone
    raise AppError(422, "delivery_unavailable", "אין משלוחים לעיר שנבחרה")
