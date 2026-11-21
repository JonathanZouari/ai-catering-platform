"""Owner-only access for API routes. The browser sends its Supabase access token; Supabase
confirms who it belongs to, and only app_metadata.role = 'admin' passes (same rule as RLS)."""

import httpx
from fastapi import Header, HTTPException

from app.core.config import get_settings


def fetch_supabase_user(token: str) -> dict | None:
    s = get_settings()
    try:
        r = httpx.get(
            f"{s.supabase_url}/auth/v1/user",
            headers={"apikey": s.supabase_publishable_key, "Authorization": f"Bearer {token}"},
            timeout=5,
        )
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="Auth service unavailable") from None
    return r.json() if r.status_code == 200 else None


def require_admin(authorization: str | None = Header(default=None)) -> dict:
    s = get_settings()
    if not (s.supabase_url and s.supabase_publishable_key):
        raise HTTPException(status_code=503, detail="Supabase is not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sign in required")
    user = fetch_supabase_user(authorization.removeprefix("Bearer ").strip())
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in required")
    if (user.get("app_metadata") or {}).get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    return user
