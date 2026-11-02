"""Owner delivery zones (screen A5): cities, fee, active."""

import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_admin
from app.schemas import delivery as s
from app.services import delivery as svc

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/delivery-zones", response_model=list[s.ZoneOut])
def list_zones(db: Session = Depends(get_db)):
    return svc.list_zones(db)


@router.post("/delivery-zones", response_model=s.ZoneOut, status_code=201)
def create_zone(data: s.ZoneCreate, db: Session = Depends(get_db)):
    return svc.create_zone(db, data)


@router.patch("/delivery-zones/{zone_id}", response_model=s.ZoneOut)
def update_zone(zone_id: uuid.UUID, data: s.ZoneUpdate, db: Session = Depends(get_db)):
    return svc.update_zone(db, zone_id, data)


@router.delete("/delivery-zones/{zone_id}", status_code=204)
def delete_zone(zone_id: uuid.UUID, db: Session = Depends(get_db)):
    svc.delete_zone(db, zone_id)
    return Response(status_code=204)
