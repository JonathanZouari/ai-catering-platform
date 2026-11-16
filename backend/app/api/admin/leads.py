"""Owner leads: customers who left their details but have not submitted the order."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_admin
from app.schemas.leads import LeadsOut
from app.services import leads as svc

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/leads", response_model=LeadsOut)
def list_leads(db: Session = Depends(get_db)):
    return svc.list_leads(db)
