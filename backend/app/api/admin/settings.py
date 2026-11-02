"""Owner business settings: child portion and booking lead time."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_admin
from app.schemas.settings import SettingsIn, SettingsOut
from app.services import settings as svc

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/settings", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db)):
    return svc.get(db)


@router.put("/settings", response_model=SettingsOut)
def update_settings(data: SettingsIn, db: Session = Depends(get_db)):
    return svc.update(db, data)
