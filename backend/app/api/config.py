from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(prefix="/api", tags=["config"])


class PublicConfig(BaseModel):
    """Only values that are safe in the browser (RLS protects the data)."""

    supabase_url: str | None
    supabase_publishable_key: str | None


@router.get("/config")
def public_config() -> PublicConfig:
    s = get_settings()
    return PublicConfig(
        supabase_url=s.supabase_url, supabase_publishable_key=s.supabase_publishable_key
    )
