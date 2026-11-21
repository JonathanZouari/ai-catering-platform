from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import require_admin
from app.repositories.leads import StorageFull
from app.schemas.leads import LeadIn, LeadOut
from app.services import leads as service

router = APIRouter()


@router.post("/api/leads", status_code=status.HTTP_201_CREATED)
def create_lead(lead: LeadIn) -> dict[str, bool]:
    """Public. The visitor never gets the score back."""
    try:
        service.submit_lead(lead)
    except StorageFull:
        raise HTTPException(status_code=503, detail="Please try again later") from None
    return {"ok": True}


@router.get("/api/admin/leads", dependencies=[Depends(require_admin)])
def list_leads() -> list[LeadOut]:
    return service.scored_leads()
