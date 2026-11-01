from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.errors import forbidden, not_found, unauthenticated
from app.core.security import SigningKeyResolver, get_signing_key_resolver, verify_access_token
from app.core.storage import Storage, get_storage
from app.core.tenancy import CatererScope
from app.repositories.caterers import get_scope_for_user
from app.repositories.orders import get_order_by_token_hash
from app.services.orders import hash_token

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
StorageDep = Annotated[Storage, Depends(get_storage)]


def get_order_scope(
    order_id: UUID,
    session: SessionDep,
    x_order_token: Annotated[str | None, Header()] = None,
) -> CatererScope:
    """The private link is the credential, and the scope comes from its order (ADR 0006)."""
    if not x_order_token:
        raise unauthenticated()
    order = get_order_by_token_hash(session, hash_token(x_order_token))
    if order is None or order.id != order_id:
        raise not_found()
    return CatererScope(order.caterer_id)


OrderScopeDep = Annotated[CatererScope, Depends(get_order_scope)]
