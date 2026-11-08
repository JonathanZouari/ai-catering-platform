"""Fill the catalog with a starter menu: `uv run python -m app.core.seed_menu [--dev] [--dry-run]`.

Without `--dev`: the local starter menu (creates its categories). With `--dev`: additions that
fit the Dev catalog's existing categories (DEV_MENU).

Idempotent and additive: categories and dishes are matched by name, existing ones are never
changed or deleted (only a missing photo is filled in). Kosher meat kitchen: meat or pareve,
never dairy (OPEN_DECISIONS #9). Allergens: only obvious "contains" are recorded and
verified_at stays empty, so the owner still checks each dish in the admin screen.
"""

# ruff: noqa: E501  (the MENU table reads best one dish per line)
import sys
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import get_engine
from app.models.catalog import Allergen, Dish, DishAllergen, DishCategory, DishDietary

IMG = "/assets/img/"
# category: (sort_order, [(name, description, unit, price, min, serves, kashrut, diet, allergens,
#            image, alcohol)]); diet: "vegan" / "veg" / None (unknown)
MENU: dict[str, tuple[int, list[tuple]]] = {
    "סלטים ומטבלים": (0, [
        ("חומוס ביתי", None, "per_tray", 120, None, 15, "pareve", "vegan", ["שומשום"], "chickpea.jpg", False),
        ("סלט ירוק עם קינואה", None, "per_tray", 140, None, 12, "pareve", "vegan", [], "quinoa.jpg", False),
        ("טחינה ירוקה", "טחינה גולמית עם פטרוזיליה, לימון ושום", "per_tray", 70, None, 25, "pareve", "vegan", ["שומשום"], None, False),
        ("מטבוחה", "עגבניות ופלפלים בבישול ארוך, פיקנטי עדין", "per_tray", 80, None, 20, "pareve", "vegan", [], None, False),
        ("סלט כרוב סגול אסייתי", "כרוב, גזר ובצל ירוק ברוטב סויה ושומשום", "per_tray", 95, None, 15, "pareve", "vegan", ["שומשום", "סויה"], None, False),
        ("סלט פטוש", "ירקות קצוצים, סומק ופיתה קלויה", "per_tray", 110, None, 12, "pareve", "vegan", ["גלוטן"], "green-salad.jpg", False),
        ("סלט גזר מרוקאי", "גזר מבושל בכמון, שום ופטרוזיליה", "per_tray", 75, None, 20, "pareve", "vegan", [], None, False),
        ("סלט עדשים שחורות ובטטה", "עדשים, בטטה צלויה, בצל סגול ועשבי תיבול", "per_tray", 120, None, 12, "pareve", "vegan", [], "greens.jpg", False),
    ]),
    "מנות עיקריות": (1, [
        ("שיפודי עוף בגריל", None, "per_item", 18, None, Decimal("0.5"), "meat", None, [], "skewers.jpg", False),
        ("בריסקט בבישול ארוך", None, "per_weight", 220, None, 4, "meat", None, [], "brisket.jpg", False),
        ("פילה סלמון בתנור", None, "per_guest", 65, None, 1, "pareve", None, ["דגים"], "salmon.jpg", False),
        ("טופו מוקפץ עם ירקות", None, "per_guest", 48, None, 1, "pareve", "vegan", ["סויה"], "tofu.jpg", False),
        ("שניצל עוף פריך", "חזה עוף בפירורי לחם, מטוגן בשמן עמוק", "per_item", 16, 20, Decimal("0.5"), "meat", None, ["גלוטן", "ביצים"], None, False),
        ("קציצות בקר ברוטב עגבניות", "קציצות ביתיות בבישול איטי", "per_weight", 180, 2, 5, "meat", None, ["ביצים"], None, False),
        ("פרגיות בגריל", "פרגיות במרינדת שום ופפריקה", "per_weight", 160, 2, 5, "meat", None, [], None, False),
        ("עוף שלם בתנור עם הדרים", "עוף צלוי עם תפוזים, לימון ורוזמרין", "per_item", 95, None, 4, "meat", None, [], None, False),
        ("אסאדו בבישול ארוך", "צלעות בקר ביין אדום ושורשים, 8 שעות בתנור", "per_weight", 260, 2, 4, "meat", None, [], None, False),
        ("מקלובה צמחונית", "אורז, חצילים, כרובית ותפוחי אדמה, הפוכה מהסיר", "per_tray", 210, None, 10, "pareve", "vegan", [], None, False),
    ]),
    "תוספות": (2, [
        ("אורז עם שקדים", None, "per_tray", 90, None, 12, "pareve", "vegan", ["אגוזים"], None, False),
        ("תפוחי אדמה צלויים", None, "per_tray", 85, None, 12, "pareve", "vegan", [], None, False),
        ("אורז עם אטריות", "אורז לבן עם אטריות קלויות", "per_tray", 80, None, 12, "pareve", "vegan", ["גלוטן"], None, False),
        ("מג'דרה", "אורז ועדשים עם בצל מטוגן", "per_tray", 85, None, 12, "pareve", "vegan", [], None, False),
        ("שעועית ירוקה מוקפצת", "בשום, סויה ושומשום קלוי", "per_tray", 95, None, 12, "pareve", "vegan", ["שומשום", "סויה"], None, False),
        ("ירקות שורש צלויים", "בטטה, גזר, סלק ובצל בשמן זית וטימין", "per_tray", 100, None, 12, "pareve", "vegan", [], None, False),
        ("קוסקוס עם ירקות", "קוסקוס ביתי עם מרק ירקות", "per_tray", 95, None, 12, "pareve", "vegan", ["גלוטן"], None, False),
        ("פירה בשמן זית", "פירה תפוחי אדמה בלי חלב, עם שמן זית ועירית", "per_tray", 85, None, 12, "pareve", "vegan", [], None, False),
    ]),
    "קינוחים": (3, [
        ("עוגת שוקולד", None, "per_item", 160, None, 12, "pareve", None, [], "cake.jpg", False),
        ("סלט פירות", None, "per_tray", 130, None, 20, "pareve", "vegan", [], None, False),
        ("עוגת תפוזים", "עוגה בחושה עם סירופ תפוזים", "per_item", 120, None, 12, "pareve", "veg", ["גלוטן", "ביצים"], None, False),
        ("מוס שוקולד בכוסות", "מוס פרווה על בסיס שוקולד מריר", "per_item", 12, 12, 1, "pareve", "veg", ["ביצים"], None, False),
        ("מגש פטיפורים", "מבחר עוגיות ומאפים קטנים", "per_tray", 180, None, 20, "pareve", "veg", ["גלוטן", "ביצים", "אגוזים"], None, False),
        ("סורבה לימון", "סורבה פירות, בלי חלב", "per_guest", 14, 10, 1, "pareve", "vegan", [], None, False),
        ("רוגלך שוקולד", "בצק פרווה מתוק במילוי שוקולד", "per_tray", 110, None, 15, "pareve", "veg", ["גלוטן"], None, False),
        ("מלבי חלב קוקוס", "עם סירופ ורדים ובוטנים", "per_item", 14, 12, 1, "pareve", "vegan", ["אגוזים"], None, False),
    ]),
    "פינגר פוד": (4, [
        ("מיני בורקס תפוחי אדמה", "בצק עלים פרווה עם שומשום", "per_tray", 140, None, 15, "pareve", "veg", ["גלוטן", "ביצים", "שומשום"], None, False),
        ("סיגרים במילוי בשר", "בצק פילו פריך במילוי בקר מתובל", "per_tray", 180, None, 15, "meat", None, ["גלוטן"], None, False),
        ("קובה מטוגן", "קליפת בורגול במילוי בשר וצנוברים", "per_item", 7, 30, Decimal("0.33"), "meat", None, ["גלוטן", "אגוזים"], None, False),
        ("פלאפל עם טחינה", "כדורי פלאפל ירוקים עם טחינה לטבילה", "per_tray", 120, None, 20, "pareve", "vegan", ["שומשום"], None, False),
        ("מיני שיפודי קבב", "קבב בקר וטלה על שיפוד קטן", "per_item", 9, 30, Decimal("0.33"), "meat", None, [], None, False),
        ("רולים וייטנאמיים", "דפי אורז במילוי ירקות ואטריות, עם רוטב צ'ילי", "per_tray", 160, None, 15, "pareve", "vegan", ["סויה"], None, False),
        ("מיני סביח בפיתה", "חציל, ביצה, עמבה וטחינה", "per_item", 12, 20, Decimal("0.5"), "pareve", "veg", ["גלוטן", "ביצים", "שומשום"], None, False),
        ("ממולאים", "פלפלים, בצלים ועלי גפן במילוי אורז ועשבים", "per_tray", 190, None, 12, "pareve", "vegan", [], None, False),
    ]),
    "לחמים ומאפים": (5, [
        ("חלה קלועה", "חלה מתוקה עם שומשום", "per_item", 22, None, 8, "pareve", "veg", ["גלוטן", "ביצים", "שומשום"], None, False),
        ("פוקאצ'ה עשבי תיבול", "שמן זית, רוזמרין ומלח גס", "per_item", 35, None, 8, "pareve", "vegan", ["גלוטן"], None, False),
        ("לחם מחמצת", "כיכר כפרית", "per_item", 30, None, 10, "pareve", "vegan", ["גלוטן"], None, False),
        ("לחמניות אישיות", "לחמניות רכות עם שומשום", "per_item", 4, 20, 1, "pareve", "vegan", ["גלוטן", "שומשום"], None, False),
        ("פיתות טריות", None, "per_item", 3, 20, 1, "pareve", "vegan", ["גלוטן"], None, False),
        ("בייגלה ירושלמי", "עם זעתר", "per_item", 6, 20, 1, "pareve", "vegan", ["גלוטן", "שומשום"], None, False),
    ]),
    "שתייה": (6, [
        ("לימונדה עם נענע", "בקנקנים, סחוטה במקום", "per_guest", 8, 10, 1, "pareve", "vegan", [], None, False),
        ("מיץ תפוזים סחוט", None, "per_guest", 10, 10, 1, "pareve", "vegan", [], None, False),
        ("מים מינרליים", "בקבוק 1.5 ליטר", "per_item", 5, 6, 3, "pareve", "vegan", [], None, False),
        ("שתייה קלה", "פחיות, מבחר טעמים", "per_item", 5, 12, 1, "pareve", "vegan", [], None, False),
        ("עמדת קפה ותה", "קפה, תה ועוגיות פרווה", "per_guest", 9, 20, 1, "pareve", None, ["גלוטן"], None, False),
        ("יין אדום כשר", "בקבוק 750 מ\"ל", "per_item", 85, None, 5, "pareve", None, [], None, True),
        ("יין לבן כשר", "בקבוק 750 מ\"ל", "per_item", 75, None, 5, "pareve", None, [], None, True),
        ("בירה", "בקבוק 330 מ\"ל", "per_item", 14, 12, 1, "pareve", "vegan", ["גלוטן"], None, True),
    ]),
}  # fmt: skip

# Additions for the Dev catalog (entered 2026-11-08: 36 dishes in 10 categories, other names).
# Only dishes Dev has nothing close to, filed under Dev's own categories (`--dev` never creates
# a category). Reuses MENU rows by name; DEV_EXTRA holds the dishes MENU doesn't have.
_ROWS = {row[0]: row for _, rows in MENU.values() for row in rows}
DEV_EXTRA = {
    "מוסקה בשרית": ("מוסקה בשרית", "חצילים, בקר טחון ורוטב עגבניות, בלי גבינה", "per_tray", 230, None, 10, "meat", None, [], None, False),
    "כרעי עוף בסילאן": ("כרעי עוף בסילאן", "כרעיים צלויות בסילאן, שום ושומשום", "per_item", 22, 10, 1, "meat", None, ["שומשום"], None, False),
    "מוסר ים בתנור": ("מוסר ים בתנור", "פילה עם עשבי תיבול, לימון ושמן זית", "per_guest", 72, 10, 1, "pareve", None, ["דגים"], None, False),
    "מגש ירקות ומטבלים": ("מגש ירקות ומטבלים", "ירקות חתוכים עם טחינה ומטבל חצילים", "per_tray", 150, None, 15, "pareve", "vegan", ["שומשום"], None, False),
    "מגש סושי צמחוני": ("מגש סושי צמחוני", "רולים במילוי ירקות ואבוקדו, עם סויה", "per_tray", 220, None, 12, "pareve", "vegan", ["סויה", "שומשום"], None, False),
}  # fmt: skip
_ROWS |= DEV_EXTRA
DEV_MENU: dict[str, tuple[int, list[tuple]]] = {
    cat: (0, [_ROWS[n] for n in names])
    for cat, names in {
        "סלטים ומטבלים": ["מטבוחה", "סלט גזר מרוקאי", "סלט פטוש", "סלט עדשים שחורות ובטטה"],
        "מאפים ופתיחים": [
            "קובה מטוגן",
            "פלאפל עם טחינה",
            "מיני סביח בפיתה",
            "רולים וייטנאמיים",
            "ממולאים",
            "חלה קלועה",
            "פוקאצ'ה עשבי תיבול",
            "לחמניות אישיות",
        ],
        "עיקריות בשר": ["קציצות בקר ברוטב עגבניות", "אסאדו בבישול ארוך", "מוסקה בשרית"],
        "עיקריות עוף": ["עוף שלם בתנור עם הדרים", "כרעי עוף בסילאן"],
        "דגים": ["מוסר ים בתנור"],
        "תוספות": [
            "מג'דרה",
            "שעועית ירוקה מוקפצת",
            "קוסקוס עם ירקות",
            "פירה בשמן זית",
            "אורז עם אטריות",
        ],
        "מגשי אירוח": ["מגש ירקות ומטבלים", "מגש סושי צמחוני", "מקלובה צמחונית"],
        "קינוחים": ["עוגת תפוזים", "מגש פטיפורים", "סורבה לימון", "מלבי חלב קוקוס"],
        "שתייה": ["לימונדה עם נענע", "מיץ תפוזים סחוט", "עמדת קפה ותה", "יין לבן כשר", "בירה"],
    }.items()
}


def seed(db: Session, menu=MENU, new_categories: bool = True) -> tuple[int, int, int]:
    """Returns (categories added, dishes added, photos filled in). The caller commits."""
    allergens = {a.name: a.id for a in db.scalars(select(Allergen))}
    categories = {c.name: c for c in db.scalars(select(DishCategory))}
    dishes = {d.name: d for d in db.scalars(select(Dish))}
    added_cats = added = photos = 0
    for cat_name, (sort_order, rows) in menu.items():
        cat = categories.get(cat_name)
        if cat is None:
            if not new_categories:
                raise ValueError(f"category {cat_name!r} not found; nothing was written")
            cat = DishCategory(name=cat_name, sort_order=sort_order)
            db.add(cat)
            db.flush()
            added_cats += 1
        for name, desc, unit, price, min_q, serves, kashrut, diet, contains, image, alcohol in rows:
            if name in dishes:
                if image and not dishes[name].image_path:
                    dishes[name].image_path = IMG + image
                    photos += 1
                continue
            missing = set(contains) - allergens.keys()
            if missing:
                raise ValueError(f"unknown allergens {missing} on {name}")
            db.add(
                Dish(
                    category_id=cat.id,
                    name=name,
                    description=desc,
                    image_path=IMG + image if image else None,
                    pricing_unit=unit,
                    unit_price=Decimal(price),
                    min_quantity=Decimal(min_q) if min_q else None,
                    serves_adults=Decimal(serves),
                    contains_alcohol=alcohol,
                    dietary=DishDietary(
                        kashrut_class=kashrut,
                        is_vegetarian=True if diet in ("veg", "vegan") else None,
                        is_vegan=True if diet == "vegan" else None,
                    ),
                    allergens=[
                        DishAllergen(allergen_id=allergens[a], status="contains") for a in contains
                    ],
                )
            )
            added += 1
    db.flush()
    return added_cats, added, photos


def main(argv: list[str]) -> None:
    engine = get_engine()
    if engine is None:
        sys.exit("DATABASE_URL is not set")
    with sessionmaker(engine)() as db:
        dev = "--dev" in argv
        result = seed(db, DEV_MENU if dev else MENU, new_categories=not dev)
        if "--dry-run" in argv:
            db.rollback()
        else:
            db.commit()
        cats, dishes, photos = result
        dry = " (dry run)" if "--dry-run" in argv else ""
        print(f"categories +{cats}, dishes +{dishes}, photos +{photos}{dry}")


if __name__ == "__main__":
    main(sys.argv[1:])
