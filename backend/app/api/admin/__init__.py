from fastapi import APIRouter, Depends

from app.api.admin import catalog, logistics, profile
from app.api.deps import get_caterer_scope

# The router-level dependency makes login mandatory for every route added here.
router = APIRouter(prefix="/api/admin", dependencies=[Depends(get_caterer_scope)])
router.include_router(catalog.router)
router.include_router(logistics.router)
router.include_router(profile.router)
