"""Owner authentication: the browser signs in with Supabase Auth and sends its access token."""

from typing import Annotated

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.http import client

bearer = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    id: str
    email: str | None
    role: str | None


def fetch_user(token: str) -> CurrentUser | None:
    """Asks Supabase Auth who the token belongs to, so a signed-out session is rejected at once."""
    s = get_settings()
    if not (s.supabase_url and s.supabase_publishable_key):
        raise HTTPException(status_code=503, detail="Supabase Auth is not configured")
    try:
        response = client().get(
            f"{s.supabase_url}/auth/v1/user",
            headers={"apikey": s.supabase_publishable_key, "Authorization": f"Bearer {token}"},
            timeout=10,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Supabase Auth is unreachable") from exc
    if response.status_code != 200:
        return None
    body = response.json()
    # app_metadata, never user_metadata: users can edit their own user_metadata.
    role = (body.get("app_metadata") or {}).get("role")
    return CurrentUser(id=body["id"], email=body.get("email"), role=role)


def require_owner(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Sign in required")
    user = fetch_user(credentials.credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Session expired, sign in again")
    if user.role != "owner":
        raise HTTPException(status_code=403, detail="Owner access only")
    return user


OwnerDep = Annotated[CurrentUser, Depends(require_owner)]
