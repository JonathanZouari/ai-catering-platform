from uuid import UUID

from app.core.errors import AppError, conflict
from app.models import BlockedDate, DeliveryZone, TimeSlot
from app.repositories.logistics import (
    BlockedDateRepository,
    DeliveryZoneRepository,
    TimeSlotRepository,
)
from app.schemas.logistics import BlockedDateCreate, SlotCreate, SlotUpdate, ZoneCreate, ZoneUpdate
from app.services.common import apply_patch, commit_or_conflict, get_or_404

DUPLICATE_ZONE = "כבר קיים אזור משלוח בשם הזה"
ZONE_IN_USE = "אי אפשר למחוק אזור שמופיע בהזמנות. סמנו אותו כלא פעיל"
INVALID_SLOT = "שעת הסיום חייבת להיות אחרי שעת ההתחלה"


def _require_unique_cities(
    repo: DeliveryZoneRepository, cities: list[str], zone_id: UUID | None = None
) -> None:
    """A city in two zones would make its delivery fee ambiguous."""
    taken = {city for zone in repo.list_all() if zone.id != zone_id for city in zone.cities}
    clashes = sorted(taken.intersection(cities))
    if clashes:
        raise conflict(f"הערים האלה כבר שייכות לאזור אחר: {', '.join(clashes)}")


def create_zone(repo: DeliveryZoneRepository, data: ZoneCreate) -> DeliveryZone:
    _require_unique_cities(repo, data.cities)
    zone = repo.add(DeliveryZone(name=data.name, fee=data.fee, definition={"cities": data.cities}))
    commit_or_conflict(repo.session, DUPLICATE_ZONE)
    return zone


def update_zone(repo: DeliveryZoneRepository, zone_id: UUID, data: ZoneUpdate) -> DeliveryZone:
    zone = get_or_404(repo, zone_id)
    if data.cities is not None:
        _require_unique_cities(repo, data.cities, zone_id)
    apply_patch(zone, data, skip={"cities"})
    if data.cities is not None:
        zone.definition = {"cities": data.cities}
    commit_or_conflict(repo.session, DUPLICATE_ZONE)
    return zone


def delete_zone(repo: DeliveryZoneRepository, zone_id: UUID) -> None:
    repo.delete(get_or_404(repo, zone_id))
    commit_or_conflict(repo.session, ZONE_IN_USE)


def create_slot(repo: TimeSlotRepository, data: SlotCreate) -> TimeSlot:
    slot = repo.add(TimeSlot(**data.model_dump()))
    commit_or_conflict(repo.session, INVALID_SLOT)
    return slot


def update_slot(repo: TimeSlotRepository, slot_id: UUID, data: SlotUpdate) -> TimeSlot:
    slot = get_or_404(repo, slot_id)
    apply_patch(slot, data)
    if slot.end_time <= slot.start_time:
        repo.session.rollback()
        raise AppError(422, "validation_error", INVALID_SLOT)
    commit_or_conflict(repo.session, INVALID_SLOT)
    return slot


def delete_slot(repo: TimeSlotRepository, slot_id: UUID) -> None:
    repo.delete(get_or_404(repo, slot_id))
    commit_or_conflict(repo.session, "אי אפשר למחוק חלון זמן שמופיע בהזמנות. סמנו אותו כלא פעיל")


def create_blocked_date(repo: BlockedDateRepository, data: BlockedDateCreate) -> BlockedDate:
    blocked = repo.add(BlockedDate(**data.model_dump()))
    commit_or_conflict(repo.session, "התאריך הזה כבר חסום")
    return blocked


def delete_blocked_date(repo: BlockedDateRepository, blocked_id: UUID) -> None:
    repo.delete(get_or_404(repo, blocked_id))
    repo.session.commit()
