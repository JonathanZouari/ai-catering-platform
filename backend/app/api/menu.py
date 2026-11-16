"""Read the menu from the SQLite database."""

from contextlib import closing

from fastapi import APIRouter, HTTPException

from app import db

router = APIRouter(prefix="/api", tags=["menu"])


@router.get("/menu")
def get_menu() -> dict:
    """Categories with their available dishes, each dish with its known allergens."""
    if not db.DB_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="Database not created yet. Run: cd backend && uv run python -m app.db",
        )

    with closing(db.get_connection()) as conn:
        categories = conn.execute(
            "SELECT id, name FROM dish_categories ORDER BY sort_order, id"
        ).fetchall()

        # INNER JOIN: every dish row paired with its category row.
        dishes = conn.execute(
            """
            SELECT dishes.id, dishes.category_id, dishes.name, dishes.description,
                   dishes.pricing_unit, dishes.unit_price, dishes.kashrut,
                   dishes.is_vegetarian, dishes.is_vegan,
                   dish_categories.name AS category_name
            FROM dishes
            INNER JOIN dish_categories ON dishes.category_id = dish_categories.id
            WHERE dishes.is_available = 1
            ORDER BY dish_categories.sort_order, dishes.id
            """
        ).fetchall()

        allergen_rows = conn.execute(
            """
            SELECT dish_allergens.dish_id, allergens.name, dish_allergens.status
            FROM dish_allergens
            INNER JOIN allergens ON dish_allergens.allergen_id = allergens.id
            ORDER BY allergens.id
            """
        ).fetchall()

    allergens_by_dish: dict[int, list[dict]] = {}
    for row in allergen_rows:
        allergens_by_dish.setdefault(row["dish_id"], []).append(
            {"name": row["name"], "status": row["status"]}
        )

    def as_bool_or_unknown(value: int | None) -> bool | None:
        # NULL in the database means "unknown", never "no".
        return None if value is None else bool(value)

    dishes_by_category: dict[int, list[dict]] = {}
    for row in dishes:
        dishes_by_category.setdefault(row["category_id"], []).append(
            {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "pricing_unit": row["pricing_unit"],
                "unit_price": row["unit_price"],
                "kashrut": row["kashrut"],
                "is_vegetarian": as_bool_or_unknown(row["is_vegetarian"]),
                "is_vegan": as_bool_or_unknown(row["is_vegan"]),
                "allergens": allergens_by_dish.get(row["id"], []),
            }
        )

    return {
        "categories": [
            {
                "id": category["id"],
                "name": category["name"],
                "dishes": dishes_by_category.get(category["id"], []),
            }
            for category in categories
        ]
    }
