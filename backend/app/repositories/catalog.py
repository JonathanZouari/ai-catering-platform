from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Connection, RowMapping, text

DISH_COLUMNS = (
    "id, category_id, name, description, image_path, pricing_unit, unit_price, "
    "unit_label, currency, min_quantity, kashrut_class, is_vegetarian, is_vegan"
)


def list_categories(conn: Connection) -> Sequence[RowMapping]:
    sql = "SELECT id, name, sort_order FROM dish_categories WHERE is_active ORDER BY sort_order, id"
    return conn.execute(text(sql)).mappings().all()


def list_dishes(
    conn: Connection,
    *,
    category_id: UUID | None = None,
    vegetarian: bool | None = None,
    vegan: bool | None = None,
    kashrut: str | None = None,
) -> Sequence[RowMapping]:
    """Available dishes. A dietary filter matches only known values, so unknown never passes."""
    where = ["is_available"]
    params: dict[str, object] = {}
    for column, value in (
        ("category_id", category_id),
        ("is_vegetarian", vegetarian),
        ("is_vegan", vegan),
        ("kashrut_class", kashrut),
    ):
        if value is not None:
            where.append(f"{column} = :{column}")
            params[column] = value
    # Only fixed column names are formatted in; every value is a bound parameter.
    sql = f"SELECT {DISH_COLUMNS} FROM dishes WHERE {' AND '.join(where)} ORDER BY category_id, id"  # noqa: S608
    return conn.execute(text(sql), params).mappings().all()


def get_dish(conn: Connection, dish_id: UUID) -> RowMapping | None:
    sql = f"SELECT {DISH_COLUMNS} FROM dishes WHERE id = :id AND is_available"  # noqa: S608
    return conn.execute(text(sql), {"id": dish_id}).mappings().first()


def list_dish_allergens(conn: Connection, dish_id: UUID) -> Sequence[RowMapping]:
    """Every allergen with its status for the dish; a missing row comes back as unknown."""
    sql = (
        "SELECT a.name, COALESCE(da.status, 'unknown') AS status FROM allergens a "
        "LEFT JOIN dish_allergens da ON da.allergen_id = a.id AND da.dish_id = :id "
        "ORDER BY a.id"
    )
    return conn.execute(text(sql), {"id": dish_id}).mappings().all()
