from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Connection

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.schemas.leads import Lead, LeadStatusUpdate
from app.services import leads


def require_development(settings: Annotated[Settings, Depends(get_settings)]) -> None:
    """Serve the leads API only when APP_ENV is "development".

    Shortcut: the admin area has no login yet, and leads hold names and phone numbers. Until
    owner login exists, the API answers 404 in production and in any other environment name.
    APP_ENV defaults to "development", so a deploy that does not set it is open: development
    databases must hold sample leads only. Replace this with the owner check when
    authentication lands.
    """
    if settings.app_env != "development":
        raise HTTPException(status_code=404, detail="not_found")


router = APIRouter(
    prefix="/api/admin/leads", tags=["leads"], dependencies=[Depends(require_development)]
)

Db = Annotated[Connection, Depends(get_db)]


@router.get("")
def list_leads(db: Db) -> list[Lead]:
    return [Lead(**lead) for lead in leads.list_leads(db)]


@router.patch("/{lead_id}")
def update_lead_status(db: Db, lead_id: UUID, body: LeadStatusUpdate) -> Lead:
    lead = leads.set_status(db, lead_id, body.status)
    if lead is None:
        raise HTTPException(status_code=404, detail="not_found")
    return Lead(**lead)
