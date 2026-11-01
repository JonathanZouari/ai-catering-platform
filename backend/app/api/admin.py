from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import ScopeDep, SessionDep, get_caterer_scope
from app.repositories.catalog import CategoryRepository
from app.schemas.catalog import CategoryCreate, CategoryOut, CategoryUpdate
from app.services import catalog

# The router-level dependency makes login mandatory for every route added here.
router = APIRouter(prefix="/api/admin", dependencies=[Depends(get_caterer_scope)])


def _category_repo(session: SessionDep, scope: ScopeDep) -> CategoryRepository:
    return CategoryRepository(session, scope)


CategoryRepoDep = Annotated[CategoryRepository, Depends(_category_repo)]


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(repo: CategoryRepoDep):
    return catalog.list_categories(repo)


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(data: CategoryCreate, repo: CategoryRepoDep):
    return catalog.create_category(repo, data)


@router.get("/categories/{category_id}", response_model=CategoryOut)
def get_category(category_id: UUID, repo: CategoryRepoDep):
    return catalog.get_category(repo, category_id)


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(category_id: UUID, data: CategoryUpdate, repo: CategoryRepoDep):
    return catalog.update_category(repo, category_id, data)
