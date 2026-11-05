from collections.abc import Iterator
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends

from app.db import connect

router = APIRouter(prefix="/api")


def get_db() -> Iterator[psycopg.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


@router.get("/dishes")
def list_dishes(db: Annotated[psycopg.Connection, Depends(get_db)]) -> list[dict]:
    """Available dishes. unit_price is in agorot. null dietary/allergen info means unknown."""
    rows = db.execute(
        "SELECT d.id, d.name, d.description, d.image_path, d.pricing_unit, d.unit_price,"
        " d.unit_label, d.min_quantity, c.id AS category_id, c.name AS category,"
        " dd.kashrut_class, dd.is_vegetarian, dd.is_vegan"
        " FROM dishes d JOIN dish_categories c ON c.id = d.category_id"
        " LEFT JOIN dish_dietary dd ON dd.dish_id = d.id"
        " WHERE d.is_available AND c.is_active ORDER BY c.sort_order, d.name"
    ).fetchall()
    allergens: dict[str, list[dict]] = {}
    for r in db.execute(
        "SELECT da.dish_id, a.name, da.status FROM dish_allergens da"
        " JOIN allergens a ON a.id = da.allergen_id"
    ):
        allergens.setdefault(r["dish_id"], []).append({"name": r["name"], "status": r["status"]})
    return [
        {
            **r,
            "min_quantity": None if r["min_quantity"] is None else float(r["min_quantity"]),
            "allergens": allergens.get(r["id"], []),
        }
        for r in rows
    ]
