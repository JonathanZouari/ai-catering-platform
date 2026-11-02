import secrets

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.errors import AppError

_bearer = HTTPBearer(auto_error=False)


def require_admin(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> None:
    expected = get_settings().admin_token
    supplied = creds.credentials if creds else ""
    # Fails closed when ADMIN_TOKEN is unset; constant-time compare.
    if not expected or not secrets.compare_digest(supplied.encode(), expected.encode()):
        raise AppError(401, "unauthenticated", "Owner login required")
