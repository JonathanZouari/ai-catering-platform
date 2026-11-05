from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Connection

from app.core.db import get_db
from app.repositories import catalog
from app.schemas.catalog import AllergenStatus, Category, Dish, DishDetail, KashrutClass

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

Db = Annotated[Connection, Depends(get_db)]


@router.get("/categories")
def list_categories(db: Db) -> list[Category]:
    return [Category(**row) for row in catalog.list_categories(db)]


@router.get("/dishes")
def list_dishes(
    db: Db,
    category_id: UUID | None = None,
    vegetarian: bool | None = None,
    vegan: bool | None = None,
    kashrut: KashrutClass | None = None,
) -> list[Dish]:
    rows = catalog.list_dishes(
        db, category_id=category_id, vegetarian=vegetarian, vegan=vegan, kashrut=kashrut
    )
    return [Dish(**row) for row in rows]


@router.get("/dishes/{dish_id}")
def get_dish(db: Db, dish_id: UUID) -> DishDetail:
    row = catalog.get_dish(db, dish_id)
    if row is None:
        raise HTTPException(status_code=404, detail="not_found")
    allergens = [AllergenStatus(**a) for a in catalog.list_dish_allergens(db, dish_id)]
    return DishDetail(**row, allergens=allergens)
