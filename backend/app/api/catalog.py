import json
import sqlite3

from fastapi import APIRouter, Depends

from app.core.db import get_db
from app.repositories import catalog

router = APIRouter(prefix="/api/catalog")


def _flag(value: int | None) -> bool | None:
    return None if value is None else bool(value)


@router.get("/categories")
def categories(conn: sqlite3.Connection = Depends(get_db)) -> list[dict]:  # noqa: B008
    return [dict(row) for row in catalog.list_categories(conn)]


@router.get("/dishes")
def dishes(conn: sqlite3.Connection = Depends(get_db)) -> list[dict]:  # noqa: B008
    return [
        {
            "id": d["id"],
            "categoryId": d["category_id"],
            "name": d["name"],
            "description": d["description"],
            "price": d["price_agorot"] / 100,
            "unit": d["unit"],
            "perGuest": d["per_guest"],
            "step": d["step"],
            "kashrut": d["kashrut"],
            "vegetarian": _flag(d["is_vegetarian"]),
            "vegan": _flag(d["is_vegan"]),
            "allergens": None if d["allergens"] is None else json.loads(d["allergens"]),
        }
        for d in catalog.list_available_dishes(conn)
    ]


@router.get("/zones")
def zones(conn: sqlite3.Connection = Depends(get_db)) -> list[dict]:  # noqa: B008
    return [{"city": z["city"], "fee": z["fee_agorot"] / 100} for z in catalog.list_zones(conn)]
