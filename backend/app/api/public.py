from fastapi import APIRouter

from app.api.deps import SessionDep
from app.core.config import get_settings
from app.core.errors import not_found
from app.core.storage import public_storage_url
from app.repositories.caterers import get_active_caterer_by_slug
from app.schemas.caterers import CatererPublic, ClientConfig

router = APIRouter(prefix="/api")


@router.get("/config", response_model=ClientConfig)
def get_client_config():
    # Only values safe for a browser. The service-role key must never appear here.
    settings = get_settings()
    return ClientConfig(
        supabase_url=settings.supabase_url,
        supabase_anon_key=settings.supabase_anon_key,
        storage_public_url=public_storage_url(),
    )


@router.get("/c/{slug}", response_model=CatererPublic)
def get_caterer(slug: str, session: SessionDep):
    caterer = get_active_caterer_by_slug(session, slug)
    if caterer is None:
        raise not_found()
    return caterer
