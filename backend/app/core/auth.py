"""Supabase Auth JWT verification (asymmetric signing keys via the project's JWKS)."""

from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str | None
    role: str  # "admin" or "customer"

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    base = get_settings().supabase_url
    if not base:
        raise RuntimeError("SUPABASE_URL is not configured")
    return jwt.PyJWKClient(f"{base}/auth/v1/.well-known/jwks.json", cache_keys=True)


def decode_token(token: str) -> dict:
    key = _jwks_client().get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        key.key,
        algorithms=["ES256", "RS256"],
        audience="authenticated",
        issuer=f"{get_settings().supabase_url}/auth/v1",
    )


def _unauthenticated() -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail={"code": "unauthenticated", "message": "Sign in required"},
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CurrentUser:
    if creds is None:
        raise _unauthenticated()
    try:
        claims = decode_token(creds.credentials)
    except jwt.PyJWTError as exc:
        raise _unauthenticated() from exc
    # app_metadata is server-controlled; never authorize on user_metadata.
    role = (claims.get("app_metadata") or {}).get("role")
    return CurrentUser(
        id=claims["sub"],
        email=claims.get("email"),
        role="admin" if role == "admin" else "customer",
    )


def require_admin(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    if not user.is_admin:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Admin access required"},
        )
    return user


User = Annotated[CurrentUser, Depends(get_current_user)]
Admin = Annotated[CurrentUser, Depends(require_admin)]
