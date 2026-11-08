# ruff: noqa: E501  (one dish per row reads better than wrapped tuples)
"""Create the catalog tables and fill them with the demo menu.

Run from backend/:  uv run python -m app.seed
Safe to run again: rows that already exist (by name) are skipped, and dishes that have no dietary
data yet get it, so an older catering.db is brought up to date.
The menu mirrors frontend/js/customer/mock-backend.js. Prices are PLACEHOLDER demo values.
"""

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.database import Base, get_engine
from app.models import (
    Allergen,
    AllergenStatus,
    Dish,
    DishAllergen,
    DishCategory,
    DishDietary,
    KashrutClass,
    PricingUnit,
)

CATEGORIES = ["סלטים ומטבלים", "עיקריות", "דגים", "תוספות ולחמים", "קינוחים", "שתייה"]

U = PricingUnit
# (category, name, description, price in ₪, pricing unit, per_guest, qty_step)
DISHES = [
    ("סלטים ומטבלים", "חומוס ביתי", "חומוס חם עם טחינה גולמית, שמן זית ופפריקה.", 85, U.PER_TRAY, None, None),
    ("סלטים ומטבלים", "סלט חצילים קלויים", "חצילים שרופים על האש עם טחינה, לימון ופטרוזיליה.", 90, U.PER_TRAY, None, None),
    ("סלטים ומטבלים", "סלט סלק וגבינת עיזים", "סלק אפוי, גבינת עיזים, אגוזי מלך וויניגרט הדרים.", 110, U.PER_TRAY, None, None),
    ("סלטים ומטבלים", "טבולה פטרוזיליה", "פטרוזיליה קצוצה, בורגול, עגבניות ולימון.", 80, U.PER_TRAY, None, None),
    ("עיקריות", "עוף בתנור בעשבי תיבול", "ירכי עוף אפויות עם שום, רוזמרין ולימון.", 74, U.PER_WEIGHT, None, None),
    ("עיקריות", "קציצות בקר ברוטב עגבניות", "קציצות בקר רכות ברוטב עגבניות וכוסברה.", 240, U.PER_TRAY, None, None),
    ("עיקריות", "פשטידת ברוקולי וגבינות", "פשטידה אפויה עם ברוקולי ושלוש גבינות.", 190, U.PER_TRAY, None, None),
    ("עיקריות", "תבשיל קדרה צמחי", "ירקות עונה, חומוס ותבלינים בבישול איטי.", 170, U.PER_TRAY, None, None),
    ("דגים", "פילה סלמון בלימון", "פילה סלמון אפוי עם לימון, שמיר ושמן זית.", 98, U.PER_ITEM, 0.6, 1),
    ("דגים", "דג מושט בצ׳רמולה", "דג מושט שלם בתנור עם צ׳רמולה ביתית.", 145, U.PER_WEIGHT, None, None),
    ("תוספות ולחמים", "אורז בסמטי ושקדים", "אורז בסמטי עם שקדים קלויים ובצל מקורמל.", 120, U.PER_TRAY, None, None),
    ("תוספות ולחמים", "ירקות שורש קלויים", "גזר, בטטה וסלק קלויים עם דבש או סילאן.", 105, U.PER_TRAY, None, None),
    ("תוספות ולחמים", "פוקאצ׳ה ביתית", "פוקאצ׳ה אפויה עם רוזמרין ומלח גס.", 18, U.PER_ITEM, 1.5, 4),
    ("קינוחים", "עוגת שוקולד ללא קמח", "עוגת שוקולד מריר לחה, 12 פרוסות.", 160, U.PER_ITEM, 0.1, 1),
    ("קינוחים", "פלטת פירות העונה", "פירות טריים חתוכים, לכ-10 סועדים.", 140, U.PER_ITEM, 0.1, 1),
    ("קינוחים", "מיני טארטלטים", "טארטלטים עם קרם וניל ופירות יער.", 9, U.PER_ITEM, 2, 6),
    ("שתייה", "שתייה קלה ומים", "מבחר שתייה קלה ומים מינרליים לכל אורח.", 14, U.PER_GUEST, None, None),
]  # fmt: skip

ALLERGENS = ["גלוטן", "אגוזים", "חלב", "ביצים", "שומשום", "דגים"]

K = KashrutClass
# name: (kashrut, vegetarian, vegan, allergens it contains). A list is a verified list, so every
# other allergen is recorded as free; None means the business has not provided allergen info.
DIETARY = {
    "חומוס ביתי": (K.PAREVE, True, True, ["שומשום"]),
    "סלט חצילים קלויים": (K.PAREVE, True, True, []),
    "סלט סלק וגבינת עיזים": (K.DAIRY, True, False, ["חלב", "אגוזים"]),
    "טבולה פטרוזיליה": (K.PAREVE, True, True, ["גלוטן"]),
    "עוף בתנור בעשבי תיבול": (K.MEAT, False, False, []),
    "קציצות בקר ברוטב עגבניות": (K.MEAT, False, False, ["גלוטן", "ביצים"]),
    "פשטידת ברוקולי וגבינות": (K.DAIRY, True, False, ["חלב", "גלוטן", "ביצים"]),
    "תבשיל קדרה צמחי": (K.PAREVE, True, True, None),
    "פילה סלמון בלימון": (K.PAREVE, False, False, ["דגים"]),
    "דג מושט בצ׳רמולה": (K.PAREVE, False, False, ["דגים"]),
    "אורז בסמטי ושקדים": (K.PAREVE, True, True, ["אגוזים"]),
    "ירקות שורש קלויים": (K.PAREVE, True, True, []),
    "פוקאצ׳ה ביתית": (K.PAREVE, True, True, ["גלוטן"]),
    "עוגת שוקולד ללא קמח": (K.PAREVE, True, False, ["ביצים", "אגוזים"]),
    "פלטת פירות העונה": (K.PAREVE, True, True, []),
    "מיני טארטלטים": (K.DAIRY, True, False, ["חלב", "גלוטן", "ביצים"]),
    "שתייה קלה ומים": (K.PAREVE, True, True, []),
}

UNIT_LABELS = {U.PER_TRAY: "מגש", U.PER_WEIGHT: "ק״ג", U.PER_ITEM: "יחידה", U.PER_GUEST: "לאורח"}


def seed_catalog(engine: Engine) -> tuple[int, int]:
    """Create the tables and insert missing rows. Returns (categories added, dishes added)."""
    Base.metadata.create_all(engine)
    added_categories = added_dishes = 0
    with Session(engine) as session, session.begin():
        categories = {c.name: c for c in session.scalars(select(DishCategory))}
        for order, name in enumerate(CATEGORIES):
            if name not in categories:
                categories[name] = DishCategory(name=name, sort_order=order)
                session.add(categories[name])
                added_categories += 1

        existing = set(session.scalars(select(Dish.name)))
        for category, name, description, price, unit, per_guest, step in DISHES:
            if name in existing:
                continue
            session.add(
                Dish(
                    category=categories[category],
                    name=name,
                    description=description,
                    pricing_unit=unit,
                    unit_price_agorot=price * 100,
                    unit_label=UNIT_LABELS[unit],
                    per_guest=per_guest,
                    qty_step=step,
                )
            )
            added_dishes += 1

        session.flush()
        allergens = {a.name: a for a in session.scalars(select(Allergen))}
        for name in ALLERGENS:
            if name not in allergens:
                allergens[name] = Allergen(name=name)
                session.add(allergens[name])
        session.flush()

        for dish in session.scalars(select(Dish).where(Dish.name.in_(DIETARY))):
            if dish.dietary is not None:
                continue
            kashrut, vegetarian, vegan, contains = DIETARY[dish.name]
            dish.dietary = DishDietary(
                kashrut_class=kashrut, is_vegetarian=vegetarian, is_vegan=vegan
            )
            if contains is not None and not dish.allergens:
                for name, allergen in allergens.items():
                    status = AllergenStatus.CONTAINS if name in contains else AllergenStatus.FREE
                    dish.allergens.append(DishAllergen(allergen=allergen, status=status))
    return added_categories, added_dishes


if __name__ == "__main__":
    engine = get_engine()
    categories, dishes = seed_catalog(engine)
    print(f"{engine.url}: added {categories} categories, {dishes} dishes")
