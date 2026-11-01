from fastapi import APIRouter

from app.api.deps import SessionDep
from app.core.errors import not_found
from app.repositories.caterers import get_active_caterer_by_slug
from app.schemas.caterers import CatererPublic

router = APIRouter(prefix="/api/c")


@router.get("/{slug}", response_model=CatererPublic)
def get_caterer(slug: str, session: SessionDep):
    caterer = get_active_caterer_by_slug(session, slug)
    if caterer is None:
        raise not_found()
    return caterer
