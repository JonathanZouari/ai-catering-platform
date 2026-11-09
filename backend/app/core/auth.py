"""Owner (admin) authentication via Supabase Auth.

The browser signs in with Supabase Auth and sends the access token as `Authorization: Bearer`.
We validate it by asking Supabase Auth (`GET /auth/v1/user`), which works for every JWT signing
setup and returns the user's *current* app_metadata, so revoking the admin role takes
effect at once.
The role lives in app_metadata (only settable with the secret key), never in user_metadata
(user-editable).
"""

from dataclasses import dataclass

import httpx
from fastapi import Header

from app.core.config import get_settings
from app.core.errors import ApiError

ADMIN_ROLE = "admin"


@dataclass(frozen=True)
class AdminUser:
    id: str
    email: str | None


async def fetch_supabase_user(token: str) -> dict | None:
    """Return the Supabase user for a valid access token, or None if the token is not valid."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise ApiError(503, "auth_not_configured", "Login is not configured on the server.")
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{settings.supabase_url}/auth/v1/user",
            headers={
                "apikey": settings.supabase_publishable_key,
                "Authorization": f"Bearer {token}",
            },
        )
    if response.status_code in (401, 403):
        return None
    response.raise_for_status()
    return response.json()


async def require_admin(authorization: str | None = Header(default=None)) -> AdminUser:
    """FastAPI dependency: the request must carry a valid token of a user with the admin role."""
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise ApiError(401, "unauthenticated", "Please log in.")
    user = await fetch_supabase_user(token)
    if user is None:
        raise ApiError(401, "unauthenticated", "Your session has expired. Please log in again.")
    if (user.get("app_metadata") or {}).get("role") != ADMIN_ROLE:
        raise ApiError(
            403, "forbidden", "This account is not allowed to open the business dashboard."
        )
    return AdminUser(id=user["id"], email=user.get("email"))
