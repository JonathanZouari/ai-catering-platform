from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile

from app.api.deps import ScopeDep, SessionDep, StorageDep
from app.repositories.catalog import CategoryRepository, DishRepository, list_allergens
from app.schemas.catalog import (
    AllergenOut,
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    DietaryUpdate,
    DishCreate,
    DishOut,
    DishUpdate,
)
from app.services import catalog
from app.services.common import get_or_404
from app.services.uploads import store_upload

router = APIRouter()


def _category_repo(session: SessionDep, scope: ScopeDep) -> CategoryRepository:
    return CategoryRepository(session, scope)


def _dish_repo(session: SessionDep, scope: ScopeDep) -> DishRepository:
    return DishRepository(session, scope)


CategoryRepoDep = Annotated[CategoryRepository, Depends(_category_repo)]
DishRepoDep = Annotated[DishRepository, Depends(_dish_repo)]


@router.get("/allergens", response_model=list[AllergenOut])
def get_allergens(session: SessionDep):
    return list_allergens(session)


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(repo: CategoryRepoDep):
    return repo.list_all()


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(data: CategoryCreate, repo: CategoryRepoDep):
    return catalog.create_category(repo, data)


@router.get("/categories/{category_id}", response_model=CategoryOut)
def get_category(category_id: UUID, repo: CategoryRepoDep):
    return get_or_404(repo, category_id)


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(category_id: UUID, data: CategoryUpdate, repo: CategoryRepoDep):
    return catalog.update_category(repo, category_id, data)


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: UUID, repo: CategoryRepoDep) -> None:
    catalog.delete_category(repo, category_id)


@router.get("/dishes", response_model=list[DishOut])
def list_dishes(repo: DishRepoDep, category_id: UUID | None = None):
    return catalog.list_dishes(repo, category_id)


@router.post("/dishes", response_model=DishOut, status_code=201)
def create_dish(data: DishCreate, repo: DishRepoDep):
    return catalog.create_dish(repo, data)


@router.get("/dishes/{dish_id}", response_model=DishOut)
def get_dish(dish_id: UUID, repo: DishRepoDep):
    return get_or_404(repo, dish_id)


@router.patch("/dishes/{dish_id}", response_model=DishOut)
def update_dish(dish_id: UUID, data: DishUpdate, repo: DishRepoDep):
    return catalog.update_dish(repo, dish_id, data)


@router.delete("/dishes/{dish_id}", status_code=204)
def delete_dish(dish_id: UUID, repo: DishRepoDep) -> None:
    catalog.delete_dish(repo, dish_id)


@router.put("/dishes/{dish_id}/dietary", response_model=DishOut)
def set_dietary(dish_id: UUID, data: DietaryUpdate, repo: DishRepoDep):
    return catalog.set_dietary(repo, dish_id, data)


@router.post("/dishes/{dish_id}/image", response_model=DishOut)
def upload_dish_image(
    dish_id: UUID, file: UploadFile, repo: DishRepoDep, storage: StorageDep, scope: ScopeDep
):
    dish = get_or_404(repo, dish_id)
    dish.image_path = store_upload(storage, scope, "dishes", file.file)
    repo.session.commit()
    return dish
