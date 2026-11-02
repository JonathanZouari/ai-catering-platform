import sqlite3
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.core.db import get_db
from app.repositories import catalog
from app.schemas.catalog import AllergenStatus, Category, Dish, DishDetail, KashrutClass

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

Db = Annotated[sqlite3.Connection, Depends(get_db)]


def _optional_bool(value: int | None) -> bool | None:
    return None if value is None else bool(value)


def _dish_fields(row: sqlite3.Row) -> dict:
    fields = dict(row)
    fields["unit_price"] = Decimal(fields.pop("unit_price_minor")).scaleb(-2)
    fields["is_vegetarian"] = _optional_bool(fields["is_vegetarian"])
    fields["is_vegan"] = _optional_bool(fields["is_vegan"])
    return fields


@router.get("/categories")
def list_categories(db: Db) -> list[Category]:
    return [Category(**dict(row)) for row in catalog.list_categories(db)]


@router.get("/dishes")
def list_dishes(
    db: Db,
    category_id: int | None = None,
    vegetarian: bool | None = None,
    vegan: bool | None = None,
    kashrut: KashrutClass | None = None,
) -> list[Dish]:
    rows = catalog.list_dishes(
        db, category_id=category_id, vegetarian=vegetarian, vegan=vegan, kashrut=kashrut
    )
    return [Dish(**_dish_fields(row)) for row in rows]


@router.get("/dishes/{dish_id}")
def get_dish(db: Db, dish_id: int) -> DishDetail:
    row = catalog.get_dish(db, dish_id)
    if row is None:
        raise HTTPException(status_code=404, detail="not_found")
    allergens = [AllergenStatus(**dict(a)) for a in catalog.list_dish_allergens(db, dish_id)]
    return DishDetail(**_dish_fields(row), allergens=allergens)
