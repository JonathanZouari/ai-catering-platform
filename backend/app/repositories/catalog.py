import sqlite3

DISH_COLUMNS = (
    "id, category_id, name, description, image_path, pricing_unit, unit_price_minor, "
    "unit_label, currency, min_quantity, kashrut_class, is_vegetarian, is_vegan"
)


def list_categories(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, name, sort_order FROM dish_categories "
        "WHERE is_active = 1 ORDER BY sort_order, id"
    ).fetchall()


def list_dishes(
    conn: sqlite3.Connection,
    *,
    category_id: int | None = None,
    vegetarian: bool | None = None,
    vegan: bool | None = None,
    kashrut: str | None = None,
) -> list[sqlite3.Row]:
    """Available dishes. A dietary filter matches only known values, so unknown never passes."""
    where = ["is_available = 1"]
    params: list[object] = []
    for column, value in (
        ("category_id", category_id),
        ("is_vegetarian", vegetarian),
        ("is_vegan", vegan),
        ("kashrut_class", kashrut),
    ):
        if value is not None:
            where.append(f"{column} = ?")
            params.append(value)
    # Only fixed column names are formatted in; every value is a bound parameter.
    sql = f"SELECT {DISH_COLUMNS} FROM dishes WHERE {' AND '.join(where)} ORDER BY category_id, id"  # noqa: S608
    return conn.execute(sql, params).fetchall()


def get_dish(conn: sqlite3.Connection, dish_id: int) -> sqlite3.Row | None:
    return conn.execute(
        f"SELECT {DISH_COLUMNS} FROM dishes WHERE id = ? AND is_available = 1",  # noqa: S608
        (dish_id,),
    ).fetchone()


def list_dish_allergens(conn: sqlite3.Connection, dish_id: int) -> list[sqlite3.Row]:
    """Every allergen with its status for the dish; a missing row comes back as unknown."""
    return conn.execute(
        "SELECT a.name, COALESCE(da.status, 'unknown') AS status FROM allergens a "
        "LEFT JOIN dish_allergens da ON da.allergen_id = a.id AND da.dish_id = ? "
        "ORDER BY a.id",
        (dish_id,),
    ).fetchall()
