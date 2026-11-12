import sqlite3
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends

from app.db import connect

router = APIRouter(prefix="/api")


def get_db() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


@router.get("/dishes")
def list_dishes(db: Annotated[sqlite3.Connection, Depends(get_db)]) -> list[dict]:
    """Available dishes. unit_price is in agorot. null dietary/allergen info means unknown."""
    rows = db.execute(
        "SELECT d.id, d.name, d.description, d.image_path, d.pricing_unit, d.unit_price,"
        " d.unit_label, d.min_quantity, c.id AS category_id, c.name AS category,"
        " dd.kashrut_class, dd.is_vegetarian, dd.is_vegan"
        " FROM dishes d JOIN dish_categories c ON c.id = d.category_id"
        " LEFT JOIN dish_dietary dd ON dd.dish_id = d.id"
        " WHERE d.is_available = 1 AND c.is_active = 1 ORDER BY c.sort_order, d.name"
    ).fetchall()
    allergens: dict[str, list[dict]] = {}
    for r in db.execute(
        "SELECT da.dish_id, a.name, da.status FROM dish_allergens da"
        " JOIN allergens a ON a.id = da.allergen_id"
    ):
        allergens.setdefault(r["dish_id"], []).append({"name": r["name"], "status": r["status"]})
    return [
        {
            **dict(r),
            "is_vegetarian": None if r["is_vegetarian"] is None else bool(r["is_vegetarian"]),
            "is_vegan": None if r["is_vegan"] is None else bool(r["is_vegan"]),
            "allergens": allergens.get(r["id"], []),
        }
        for r in rows
    ]
