"""Customer identity from a Supabase Auth access token (ADR 0005).

The browser signs in with a 6-digit email code through supabase-js and sends the access token as
a Bearer header. We only verify it: signature against the project's public JWKS, `aud`, `iss`
and `exp`. Fails closed: no Supabase URL, an unreachable JWKS or any bad claim answers 401.
"""

import uuid
from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.errors import AppError

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CustomerIdentity:
    user_id: uuid.UUID  # Supabase auth.users.id (the token's `sub`)
    email: str


def _auth_base() -> str:
    url = get_settings().supabase_url
    if not url:
        raise AppError(401, "unauthenticated", "Customer login is not configured")
    return f"{url.rstrip('/')}/auth/v1"


@lru_cache
def _jwks(base: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{base}/.well-known/jwks.json", cache_keys=True, lifespan=3600)


def signing_key(token: str):
    # shortcut: asymmetric JWT signing keys only (JWKS). A project still on the legacy shared
    # secret publishes no keys here, so every login fails closed; switch the project's signing
    # keys in Supabase rather than adding the secret path.
    return _jwks(_auth_base()).get_signing_key_from_jwt(token).key


def require_customer(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CustomerIdentity:
    if creds is None:
        raise AppError(401, "unauthenticated", "Customer login required")
    base = _auth_base()
    try:
        claims = jwt.decode(
            creds.credentials,
            signing_key(creds.credentials),
            algorithms=["ES256", "RS256"],
            audience="authenticated",
            issuer=base,
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
        email = claims.get("email")
        if not email:
            raise ValueError("token has no email")
        return CustomerIdentity(uuid.UUID(claims["sub"]), email.lower())
    except (jwt.PyJWTError, ValueError) as exc:
        raise AppError(401, "unauthenticated", "Customer login required") from exc
