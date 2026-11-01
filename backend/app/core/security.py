from collections.abc import Callable
from functools import lru_cache
from typing import Any
from uuid import UUID

import jwt

from app.core.config import get_settings
from app.core.errors import unauthenticated

# Asymmetric only: rejects "none" and HS256 tokens forged with a public key.
ALLOWED_ALGORITHMS = ["ES256", "RS256"]
SUPABASE_AUDIENCE = "authenticated"

SigningKeyResolver = Callable[[str], Any]


@lru_cache
def _get_jwk_client() -> jwt.PyJWKClient:
    supabase_url = get_settings().supabase_url
    if not supabase_url:
        raise RuntimeError("SUPABASE_URL is not configured")
    return jwt.PyJWKClient(f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json")


def get_signing_key_resolver() -> SigningKeyResolver:
    return lambda token: _get_jwk_client().get_signing_key_from_jwt(token).key


def verify_access_token(token: str, resolve_key: SigningKeyResolver) -> UUID:
    """Return the Supabase auth user ID from a valid token, or raise 401."""
    try:
        claims = jwt.decode(
            token,
            resolve_key(token),
            algorithms=ALLOWED_ALGORITHMS,
            audience=SUPABASE_AUDIENCE,
            options={"require": ["exp", "sub", "aud"]},
        )
        return UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError) as exc:
        raise unauthenticated() from exc
