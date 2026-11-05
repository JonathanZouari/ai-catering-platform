import uuid
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.errors import AppError

bearer = HTTPBearer(auto_error=False)


@lru_cache
def get_jwks_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{get_settings().supabase_url}/auth/v1/.well-known/jwks.json")


def _verify(creds: HTTPAuthorizationCredentials | None) -> dict:
    """The one JWT check for every role: fixed algorithms, aud, iss and exp are required."""
    supabase_url = get_settings().supabase_url
    if creds is None or not supabase_url:
        raise AppError(401, "Missing or invalid token")
    try:
        key = get_jwks_client().get_signing_key_from_jwt(creds.credentials).key
        return jwt.decode(
            creds.credentials,
            key,
            algorithms=["ES256", "RS256"],  # fixed list: never trust the token's own alg
            audience="authenticated",
            issuer=f"{supabase_url}/auth/v1",
            options={"require": ["exp", "aud", "iss"]},
        )
    except jwt.PyJWTError:
        raise AppError(401, "Missing or invalid token") from None


Creds = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


def require_admin(creds: Creds) -> dict:
    claims = _verify(creds)
    if claims.get("app_metadata", {}).get("role") != "admin":
        raise AppError(403, "Admin role required")
    return claims


def require_customer(creds: Creds) -> dict:
    """A signed-in, non-anonymous Supabase user; `sub` is the customer's auth_user_id."""
    claims = _verify(creds)
    try:
        uuid.UUID(str(claims.get("sub")))
    except ValueError:
        raise AppError(401, "Missing or invalid token") from None
    if claims.get("is_anonymous"):
        raise AppError(401, "Sign in to continue")
    return claims


def optional_customer(creds: Creds) -> dict | None:
    """No token = guest; a token that is present must be valid (never silently a guest)."""
    return None if creds is None else require_customer(creds)
