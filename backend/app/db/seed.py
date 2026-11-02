# ruff: noqa: E501
"""Sample catalog for local development. Idempotent: safe to run repeatedly.

Run: uv run python -m app.db.seed
"""

from app.db import init_db

CATEGORIES = ["ראשונות", "סלטים", "עיקריות", "תוספות", "קינוחים"]
ALLERGENS = ["גלוטן", "אגוזים", "בוטנים", "שומשום", "ביצים", "חלב", "דגים", "סויה"]

# (category, name, description, unit, price in agorot, unit_label, kashrut, vegetarian, vegan, allergens)
DISHES = [
    (
        "ראשונות",
        "חומוס ביתי",
        "חומוס עם טחינה ושמן זית",
        "per_tray",
        12000,
        "מגש 2 ק״ג",
        "pareve",
        1,
        1,
        ["שומשום"],
    ),
    (
        "ראשונות",
        "קובה סלק",
        "קובה סלק במילוי בשר",
        "per_item",
        1800,
        "יחידה",
        "meat",
        0,
        0,
        ["גלוטן"],
    ),
    (
        "סלטים",
        "סלט ירקות קצוץ",
        "עגבנייה, מלפפון ובצל",
        "per_tray",
        9000,
        "מגש 3 ק״ג",
        "pareve",
        1,
        1,
        [],
    ),
    (
        "סלטים",
        "סלט קינואה",
        "קינואה, ירקות ואגוזי מלך",
        "per_tray",
        14000,
        "מגש 2 ק״ג",
        "pareve",
        1,
        1,
        ["אגוזים"],
    ),
    (
        "עיקריות",
        "חזה עוף בתנור",
        "עוף צלוי בתיבול עשבים",
        "per_weight",
        6500,
        "ק״ג",
        "meat",
        0,
        0,
        [],
    ),
    (
        "עיקריות",
        "סלמון בגריל",
        "פילה סלמון ברוטב לימון",
        "per_guest",
        4500,
        "למנה",
        "pareve",
        0,
        0,
        ["דגים"],
    ),
    (
        "עיקריות",
        "לזניה גבינות",
        "לזניה עם ממרח עגבניות",
        "per_tray",
        26000,
        "מגש 12 מנות",
        "dairy",
        1,
        0,
        ["גלוטן", "חלב", "ביצים"],
    ),
    (
        "תוספות",
        "אורז בסמטי",
        "אורז עם שקדים קלויים",
        "per_tray",
        8000,
        "מגש 3 ק״ג",
        "pareve",
        1,
        1,
        ["אגוזים"],
    ),
    (
        "תוספות",
        "תפוחי אדמה בתנור",
        "תפוחי אדמה עם רוזמרין",
        "per_tray",
        7500,
        "מגש 3 ק״ג",
        "pareve",
        1,
        1,
        [],
    ),
    (
        "קינוחים",
        "עוגת שוקולד",
        "עוגת שוקולד מריר",
        "per_item",
        5500,
        "עוגה",
        "dairy",
        1,
        0,
        ["גלוטן", "ביצים", "חלב"],
    ),
    ("קינוחים", "סלט פירות", "פירות העונה", "per_guest", 1500, "למנה", "pareve", 1, 1, []),
]


def seed(path: str = "catering.db") -> None:
    conn = init_db(path)
    with conn:
        for i, name in enumerate(CATEGORIES):
            conn.execute(
                "INSERT OR IGNORE INTO dish_categories (id, name, sort_order) VALUES (?, ?, ?)",
                (f"cat-{i + 1}", name, i),
            )
        for i, name in enumerate(ALLERGENS):
            conn.execute("INSERT OR IGNORE INTO allergens (id, name) VALUES (?, ?)", (i + 1, name))
        for i, (cat, name, desc, unit, price, label, kashrut, veg, vegan, allergens) in enumerate(
            DISHES
        ):
            dish_id = f"dish-{i + 1}"
            conn.execute(
                "INSERT OR IGNORE INTO dishes (id, category_id, name, description, pricing_unit,"
                " unit_price, unit_label) VALUES (?, (SELECT id FROM dish_categories WHERE name = ?),"
                " ?, ?, ?, ?, ?)",
                (dish_id, cat, name, desc, unit, price, label),
            )
            conn.execute(
                "INSERT OR IGNORE INTO dish_dietary (dish_id, kashrut_class, is_vegetarian, is_vegan)"
                " VALUES (?, ?, ?, ?)",
                (dish_id, kashrut, veg, vegan),
            )
            # Only allergens listed here are recorded as 'contains'; the rest stay unknown (no row).
            for a in allergens:
                conn.execute(
                    "INSERT OR IGNORE INTO dish_allergens (dish_id, allergen_id, status)"
                    " VALUES (?, (SELECT id FROM allergens WHERE name = ?), 'contains')",
                    (dish_id, a),
                )


if __name__ == "__main__":
    seed()
