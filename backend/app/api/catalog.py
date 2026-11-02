import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.db import get_db
from app.core.errors import ApiError
from app.repositories import catalog
from app.schemas.catalog import (
    Category,
    Dish,
    DishDetail,
    KashrutClass,
    format_agorot,
)

router = APIRouter(prefix="/api/catalog", tags=["catalog"])
Db = Annotated[sqlite3.Connection, Depends(get_db)]


def _with_price(row: dict) -> dict:
    return {**row, "unit_price": format_agorot(row["unit_price"])}


@router.get("/categories")
def list_categories(conn: Db) -> list[Category]:
    return [Category(**row) for row in catalog.list_categories(conn)]


@router.get("/dishes")
def list_dishes(
    conn: Db,
    category_id: str | None = None,
    vegan: bool | None = None,
    vegetarian: bool | None = None,
    kashrut: KashrutClass | None = None,
) -> list[Dish]:
    rows = catalog.list_dishes(
        conn, category_id=category_id, kashrut=kashrut, vegan=vegan, vegetarian=vegetarian
    )
    return [Dish(**_with_price(row)) for row in rows]


@router.get("/dishes/{dish_id}")
def get_dish(conn: Db, dish_id: str) -> DishDetail:
    row = catalog.get_dish(conn, dish_id)
    if row is None:
        raise ApiError(404, "dish_not_found", "Dish not found")
    return DishDetail(**_with_price(row))
