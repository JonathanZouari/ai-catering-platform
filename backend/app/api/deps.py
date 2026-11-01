from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.errors import forbidden, unauthenticated
from app.core.security import SigningKeyResolver, get_signing_key_resolver, verify_access_token
from app.core.tenancy import CatererScope
from app.repositories.caterers import get_scope_for_user

_bearer = HTTPBearer(auto_error=False)

SessionDep = Annotated[Session, Depends(get_session)]


def get_caterer_scope(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    resolve_key: Annotated[SigningKeyResolver, Depends(get_signing_key_resolver)],
) -> CatererScope:
    if credentials is None:
        raise unauthenticated()
    auth_user_id = verify_access_token(credentials.credentials, resolve_key)
    scope = get_scope_for_user(session, auth_user_id)
    if scope is None:
        raise forbidden()
    return scope


ScopeDep = Annotated[CatererScope, Depends(get_caterer_scope)]
