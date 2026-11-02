import sqlite3

# One static query per read: optional filters are NULL-tolerant parameters, never string-built SQL.
_DISHES = """
SELECT d.id, d.category_id, d.name, d.description, d.image_path, d.pricing_unit, d.unit_price,
       d.unit_label, d.currency, d.min_quantity,
       dd.kashrut_class, dd.is_vegetarian, dd.is_vegan
FROM dishes d
JOIN dish_categories c ON c.id = d.category_id AND c.is_active = 1
LEFT JOIN dish_dietary dd ON dd.dish_id = d.id
WHERE d.is_available = 1
  AND (:category_id IS NULL OR d.category_id = :category_id)
  AND (:kashrut IS NULL OR dd.kashrut_class = :kashrut)
  AND (:vegan IS NULL OR dd.is_vegan = :vegan)
  AND (:vegetarian IS NULL OR dd.is_vegetarian = :vegetarian)
"""


def list_categories(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, name, sort_order FROM dish_categories WHERE is_active = 1"
        " ORDER BY sort_order, rowid"
    )
    return [dict(r) for r in rows]


def list_dishes(
    conn: sqlite3.Connection,
    *,
    category_id: str | None = None,
    kashrut: str | None = None,
    vegan: bool | None = None,
    vegetarian: bool | None = None,
) -> list[dict]:
    """A dietary filter matches only dishes where that flag is KNOWN to match.
    Unknown (NULL) never passes, because "not provided" must not read as vegan or vegetarian."""
    params = {
        "category_id": category_id,
        "kashrut": kashrut,
        "vegan": None if vegan is None else int(vegan),
        "vegetarian": None if vegetarian is None else int(vegetarian),
    }
    rows = conn.execute(_DISHES + " ORDER BY c.sort_order, d.rowid", params)
    return [dict(r) for r in rows]


def get_dish(conn: sqlite3.Connection, dish_id: str) -> dict | None:
    row = conn.execute(
        _DISHES + " AND d.id = :id",
        {
            "category_id": None,
            "kashrut": None,
            "vegan": None,
            "vegetarian": None,
            "id": dish_id,
        },
    ).fetchone()
    if row is None:
        return None
    allergens = conn.execute(
        "SELECT a.id, a.name, COALESCE(da.status, 'unknown') AS status"
        " FROM allergens a LEFT JOIN dish_allergens da"
        "   ON da.allergen_id = a.id AND da.dish_id = ?"
        " ORDER BY a.id",
        (dish_id,),
    )
    return {**dict(row), "allergens": [dict(a) for a in allergens]}
