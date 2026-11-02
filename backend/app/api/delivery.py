"""Public: the cities we deliver to and their fee (active zones only)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas import delivery as s
from app.services import delivery as svc

router = APIRouter(prefix="/api/delivery", tags=["delivery"])


@router.get("/cities", response_model=list[s.CityOut])
def cities(db: Session = Depends(get_db)):
    return svc.public_cities(db)
