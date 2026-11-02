import json
import sqlite3
from contextlib import closing
from pathlib import Path

from fastapi import APIRouter, HTTPException

# shortcut: reads the course SQLite file directly; swap for a repository layer when Supabase lands.
DB_PATH = Path(__file__).resolve().parents[3] / "database" / "sqlite" / "catering.db"

# Unit codes the customer UI already uses.
UNITS = {"per_tray": "tray", "per_weight": "kg", "per_item": "item", "per_guest": "guest"}

router = APIRouter(prefix="/api/catalog")


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise HTTPException(503, "Database missing. Run: python3 database/sqlite/build_db.py")
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def _flag(value: int | None) -> bool | None:
    return None if value is None else bool(value)


@router.get("/categories")
def categories() -> list[dict]:
    with closing(_connect()) as con:
        rows = con.execute(
            "SELECT id, name FROM dish_categories WHERE is_active = 1 ORDER BY sort_order"
        )
        return [dict(r) for r in rows]


@router.get("/dishes")
def dishes() -> list[dict]:
    with closing(_connect()) as con:
        rows = con.execute(
            """
            SELECT d.id, d.category_id, d.name, d.description, d.pricing_unit, d.unit_price,
                   dd.kashrut_class, dd.is_vegetarian, dd.is_vegan,
                   (SELECT count(*) FROM dish_allergens WHERE dish_id = d.id) AS allergen_rows,
                   (SELECT json_group_array(a.name) FROM dish_allergens da
                      JOIN allergens a ON a.id = da.allergen_id
                     WHERE da.dish_id = d.id AND da.status = 'contains') AS contains
            FROM dishes d
            JOIN dish_categories c ON c.id = d.category_id
            LEFT JOIN dish_dietary dd ON dd.dish_id = d.id
            WHERE d.is_available = 1
            ORDER BY c.sort_order, d.rowid
            """
        )
        return [
            {
                "id": r["id"],
                "categoryId": r["category_id"],
                "name": r["name"],
                "description": r["description"],
                "price": float(r["unit_price"]),
                "unit": UNITS[r["pricing_unit"]],
                "kashrut": r["kashrut_class"],
                "vegetarian": _flag(r["is_vegetarian"]),
                "vegan": _flag(r["is_vegan"]),
                # No allergen rows at all = unknown (null), never "allergen free".
                "allergens": json.loads(r["contains"]) if r["allergen_rows"] else None,
            }
            for r in rows
        ]
