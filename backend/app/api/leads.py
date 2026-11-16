from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.supabase import get_supabase
from app.schemas.leads import Lead
from app.services import leads

router = APIRouter(prefix="/api/admin/leads", tags=["leads"])

bearer = HTTPBearer(auto_error=False)


@router.get("")
def list_leads(
    supabase: Annotated[httpx.Client, Depends(get_supabase)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> list[Lead]:
    """Leads with purchase probability, for the admin.

    The caller's Supabase token is passed on to Supabase, where row level security allows
    only the admin to read leads. This endpoint holds no key that could read them itself.
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="not_authenticated")
    try:
        return [Lead(**lead) for lead in leads.list_leads(supabase, credentials.credentials)]
    except httpx.HTTPStatusError as error:
        if error.response.status_code in (401, 403):
            raise HTTPException(status_code=401, detail="not_authenticated") from error
        raise HTTPException(status_code=502, detail="leads_unavailable") from error
    except httpx.TransportError as error:
        raise HTTPException(status_code=502, detail="leads_unavailable") from error
