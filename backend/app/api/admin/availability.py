"""Owner availability management (screens A4 blocked dates, A5 time slots)."""

import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_admin
from app.schemas import availability as s
from app.services import availability as svc

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/blocked-dates", response_model=list[s.BlockedDateOut])
def list_blocked(db: Session = Depends(get_db)):
    return svc.list_blocked(db)


@router.post("/blocked-dates", response_model=s.BlockedDateOut, status_code=201)
def block_date(data: s.BlockedDateCreate, db: Session = Depends(get_db)):
    return svc.block_date(db, data)


@router.delete("/blocked-dates/{blocked_id}", status_code=204)
def unblock_date(blocked_id: uuid.UUID, db: Session = Depends(get_db)):
    svc.unblock_date(db, blocked_id)
    return Response(status_code=204)


@router.get("/time-slots", response_model=list[s.TimeSlotOut])
def list_slots(db: Session = Depends(get_db)):
    return svc.list_slots(db)


@router.post("/time-slots", response_model=s.TimeSlotOut, status_code=201)
def create_slot(data: s.TimeSlotCreate, db: Session = Depends(get_db)):
    return svc.create_slot(db, data)


@router.patch("/time-slots/{slot_id}", response_model=s.TimeSlotOut)
def update_slot(slot_id: uuid.UUID, data: s.TimeSlotUpdate, db: Session = Depends(get_db)):
    return svc.update_slot(db, slot_id, data)


@router.delete("/time-slots/{slot_id}", status_code=204)
def delete_slot(slot_id: uuid.UUID, db: Session = Depends(get_db)):
    svc.delete_slot(db, slot_id)
    return Response(status_code=204)
