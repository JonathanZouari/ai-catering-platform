"""Tenant lookups. These run before a scope exists, so they aren't scoped repositories."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tenancy import CatererScope
from app.models import Caterer, CatererUser


def get_active_caterer_by_slug(session: Session, slug: str) -> Caterer | None:
    query = select(Caterer).where(Caterer.slug == slug, Caterer.is_active)
    return session.scalar(query)


def get_scope_for_user(session: Session, auth_user_id: UUID) -> CatererScope | None:
    """Scope for a logged-in user, or None if they have no active caterer."""
    query = (
        select(CatererUser.caterer_id)
        .join(Caterer, Caterer.id == CatererUser.caterer_id)
        .where(CatererUser.auth_user_id == auth_user_id, Caterer.is_active)
    )
    caterer_id = session.scalar(query)
    return CatererScope(caterer_id) if caterer_id else None
