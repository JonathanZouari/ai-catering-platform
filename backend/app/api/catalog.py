import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.models import KashrutClass
from app.repositories import catalog as repo
from app.schemas.catalog import CategoryOut, DishOut

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/categories")
def list_categories(session: SessionDep) -> list[CategoryOut]:
    return [CategoryOut.of(c) for c in repo.active_categories(session)]


@router.get("/dishes")
def list_dishes(
    session: SessionDep,
    category_id: uuid.UUID | None = None,
    vegan: bool | None = None,
    vegetarian: bool | None = None,
    kashrut: KashrutClass | None = None,
) -> list[DishOut]:
    dishes = repo.available_dishes(
        session, category_id=category_id, vegan=vegan, vegetarian=vegetarian, kashrut=kashrut
    )
    names = repo.allergen_names(session)
    return [DishOut.of(d, names) for d in dishes]


@router.get("/dishes/{dish_id}")
def get_dish(dish_id: uuid.UUID, session: SessionDep) -> DishOut:
    dish = repo.available_dish(session, dish_id)
    if dish is None:
        raise HTTPException(status_code=404, detail="Dish not found")
    return DishOut.of(dish, repo.allergen_names(session))
