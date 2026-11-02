"""Public availability: blocked dates in a range plus active time slots."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas import availability as s
from app.services import availability as svc

router = APIRouter(prefix="/api", tags=["availability"])


@router.get("/availability", response_model=s.AvailabilityOut)
def availability(
    start: date = Query(alias="from"),
    end: date = Query(alias="to"),
    db: Session = Depends(get_db),
):
    return svc.availability(db, start, end)
