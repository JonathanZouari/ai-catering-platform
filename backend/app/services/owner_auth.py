"""The catering owner, as Supabase Auth reports it.

The server asks Auth who a bearer token belongs to (GET /auth/v1/user); nothing here decodes a JWT.
Only app_metadata.role counts: users cannot edit app_metadata, unlike user_metadata. Any doubt
denies: no configuration or no answer from Auth is 503, never a fallback to an unchecked identity.
"""

import logging
import re
from typing import Annotated

import httpx
from fastapi import Depends, Header, HTTPException

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)
OWNER_ROLE = "catering_owner"
BEARER = re.compile(r"Bearer ([A-Za-z0-9._~+/=-]{1,4096})", re.IGNORECASE)
NO_STORE = {"Cache-Control": "no-store"}


def deny(status: int, message: str) -> HTTPException:
    headers = NO_STORE | ({"WWW-Authenticate": "Bearer"} if status == 401 else {})
    return HTTPException(status_code=status, detail=message, headers=headers)


def unavailable() -> HTTPException:
    return deny(503, "אימות המנהל אינו זמין כרגע. אפשר לנסות שוב בעוד רגע.")


def new_client(settings: Settings, transport: httpx.BaseTransport | None = None) -> httpx.Client:
    return httpx.Client(
        base_url=f"{settings.supabase_url.rstrip('/')}/auth/v1/",
        # The publishable key identifies the project to Auth; the secret key is not needed here.
        headers={"apikey": settings.supabase_publishable_key},
        timeout=10.0,
        trust_env=False,
        transport=transport,
    )


def require_owner(authorization: Annotated[str | None, Header()] = None) -> dict:
    match = BEARER.fullmatch(authorization or "")
    if not match:
        raise deny(401, "נדרשת התחברות של בעל העסק")
    settings = get_settings()
    if not (settings.supabase_url or "").startswith("https://") or not (
        settings.supabase_publishable_key or ""
    ).startswith("sb_publishable_"):
        logger.error("Owner sign-in needs an https:// SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY")
        raise unavailable()
    try:
        with new_client(settings) as client:
            response = client.get("user", headers={"Authorization": f"Bearer {match[1]}"})
    except httpx.HTTPError as exc:
        logger.error("Supabase Auth user lookup failed: %s", type(exc).__name__)
        raise unavailable() from None
    if response.status_code in (401, 403):
        raise deny(401, "ההתחברות אינה תקפה. יש להתחבר מחדש.")
    if response.status_code != 200:
        logger.error("Supabase Auth user lookup returned HTTP %s", response.status_code)
        raise unavailable()
    try:
        user = response.json()
    except ValueError:
        logger.error("Supabase Auth user lookup returned no JSON")
        raise unavailable() from None
    if not isinstance(user, dict) or not isinstance(user.get("id"), str):
        logger.error("Supabase Auth returned an unexpected user shape")
        raise unavailable()
    app_metadata = user.get("app_metadata")
    if not isinstance(app_metadata, dict) or app_metadata.get("role") != OWNER_ROLE:
        raise deny(403, "אין הרשאה לפעולה זו")
    return user


Owner = Annotated[dict, Depends(require_owner)]
