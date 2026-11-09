from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.auth import AdminUser, require_admin
from app.core.config import get_settings
from app.core.errors import ApiError

router = APIRouter(prefix="/api")


@router.get("/auth/config")
def auth_config() -> dict[str, str]:
    """Public values the login page needs. The publishable key is designed to be public."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise ApiError(503, "auth_not_configured", "Login is not configured on the server.")
    return {
        "supabase_url": settings.supabase_url,
        "publishable_key": settings.supabase_publishable_key,
    }


@router.get("/admin/me")
def admin_me(admin: Annotated[AdminUser, Depends(require_admin)]) -> dict[str, str | None]:
    return {"id": admin.id, "email": admin.email}
