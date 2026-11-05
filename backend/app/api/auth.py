from fastapi import APIRouter

from app.core.auth import Admin, User
from app.core.config import get_settings

router = APIRouter(prefix="/api")


@router.get("/config")
def public_config() -> dict[str, str | None]:
    """Public values the browser needs to talk to Supabase Auth (anon key is public)."""
    s = get_settings()
    return {"supabase_url": s.supabase_url, "supabase_anon_key": s.supabase_anon_key}


@router.get("/me")
def me(user: User) -> dict[str, str | None]:
    return {"id": user.id, "email": user.email, "role": user.role}


@router.get("/admin/me")
def admin_me(user: Admin) -> dict[str, str | None]:
    return {"id": user.id, "email": user.email, "role": user.role}
