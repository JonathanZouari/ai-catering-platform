import secrets
from dataclasses import asdict
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.core.config import get_settings
from app.services.lead_scoring import LeadService


def require_admin(authorization: str | None = Header(default=None)) -> None:
    """Leads contain names and phone numbers. Open in development; a bearer token elsewhere.

    TODO: replace with real owner authentication (Supabase Auth) when the admin login exists.
    """
    settings = get_settings()
    if settings.app_env == "development":
        return
    token = settings.admin_api_token
    if not token:
        raise HTTPException(status_code=503, detail="Admin access is not configured")
    supplied = (authorization or "").removeprefix("Bearer ")
    if not secrets.compare_digest(supplied, token):
        raise HTTPException(status_code=401, detail="Unauthorized")


router = APIRouter(prefix="/api/leads", tags=["leads"], dependencies=[Depends(require_admin)])

Tier = Literal["hot", "warm", "cold"]


@lru_cache
def get_lead_service() -> LeadService:
    path = Path(get_settings().leads_data_path)
    if not path.exists():
        raise HTTPException(status_code=503, detail="Lead data file is not configured")
    return LeadService.from_csv(path)


@router.get("")
def list_leads(
    tier: Tier | None = None,
    kind: Literal["prospect", "open_order"] | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    as_of: date | None = None,
) -> dict:
    leads = get_lead_service().leads(as_of)
    if tier:
        leads = [lead for lead in leads if lead.tier == tier]
    if kind:
        leads = [lead for lead in leads if lead.kind == kind]
    return {
        "total": len(leads),
        "items": [asdict(lead) for lead in leads[offset : offset + limit]],
    }


@router.get("/forecast")
def forecast(as_of: date | None = None) -> dict:
    return get_lead_service().forecast(as_of)


@router.get("/{customer_id}")
def get_lead(customer_id: str, as_of: date | None = None) -> dict:
    lead = get_lead_service().get(customer_id, as_of)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return asdict(lead)
