from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import ScopeDep, SessionDep
from app.repositories.logistics import (
    BlockedDateRepository,
    DeliveryZoneRepository,
    TimeSlotRepository,
)
from app.schemas.logistics import (
    BlockedDateCreate,
    BlockedDateOut,
    SlotCreate,
    SlotOut,
    SlotUpdate,
    ZoneCreate,
    ZoneOut,
    ZoneUpdate,
)
from app.services import logistics

router = APIRouter()


def _zone_repo(session: SessionDep, scope: ScopeDep) -> DeliveryZoneRepository:
    return DeliveryZoneRepository(session, scope)


def _slot_repo(session: SessionDep, scope: ScopeDep) -> TimeSlotRepository:
    return TimeSlotRepository(session, scope)


def _blocked_repo(session: SessionDep, scope: ScopeDep) -> BlockedDateRepository:
    return BlockedDateRepository(session, scope)


ZoneRepoDep = Annotated[DeliveryZoneRepository, Depends(_zone_repo)]
SlotRepoDep = Annotated[TimeSlotRepository, Depends(_slot_repo)]
BlockedRepoDep = Annotated[BlockedDateRepository, Depends(_blocked_repo)]


@router.get("/delivery-zones", response_model=list[ZoneOut])
def list_zones(repo: ZoneRepoDep):
    return repo.list_all()


@router.post("/delivery-zones", response_model=ZoneOut, status_code=201)
def create_zone(data: ZoneCreate, repo: ZoneRepoDep):
    return logistics.create_zone(repo, data)


@router.patch("/delivery-zones/{zone_id}", response_model=ZoneOut)
def update_zone(zone_id: UUID, data: ZoneUpdate, repo: ZoneRepoDep):
    return logistics.update_zone(repo, zone_id, data)


@router.delete("/delivery-zones/{zone_id}", status_code=204)
def delete_zone(zone_id: UUID, repo: ZoneRepoDep) -> None:
    logistics.delete_zone(repo, zone_id)


@router.get("/time-slots", response_model=list[SlotOut])
def list_slots(repo: SlotRepoDep):
    return repo.list_all()


@router.post("/time-slots", response_model=SlotOut, status_code=201)
def create_slot(data: SlotCreate, repo: SlotRepoDep):
    return logistics.create_slot(repo, data)


@router.patch("/time-slots/{slot_id}", response_model=SlotOut)
def update_slot(slot_id: UUID, data: SlotUpdate, repo: SlotRepoDep):
    return logistics.update_slot(repo, slot_id, data)


@router.delete("/time-slots/{slot_id}", status_code=204)
def delete_slot(slot_id: UUID, repo: SlotRepoDep) -> None:
    logistics.delete_slot(repo, slot_id)


@router.get("/blocked-dates", response_model=list[BlockedDateOut])
def list_blocked_dates(repo: BlockedRepoDep):
    return repo.list_all()


@router.post("/blocked-dates", response_model=BlockedDateOut, status_code=201)
def create_blocked_date(data: BlockedDateCreate, repo: BlockedRepoDep):
    return logistics.create_blocked_date(repo, data)


@router.delete("/blocked-dates/{blocked_id}", status_code=204)
def delete_blocked_date(blocked_id: UUID, repo: BlockedRepoDep) -> None:
    logistics.delete_blocked_date(repo, blocked_id)
