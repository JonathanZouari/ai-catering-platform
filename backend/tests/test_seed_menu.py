from sqlalchemy import func, select

from app.core.seed_menu import MENU, seed
from app.models.catalog import Allergen, Dish, DishCategory

ALLERGENS = ["גלוטן", "ביצים", "חלב", "אגוזים", "שומשום", "סויה", "דגים"]


def test_seed_is_additive_idempotent_and_never_dairy(make_session):
    with make_session() as db:
        db.add_all(Allergen(name=n) for n in ALLERGENS)
        existing = DishCategory(name="תוספות", sort_order=9)
        db.add(existing)
        db.flush()
        mine = Dish(category_id=existing.id, name="מג'דרה", pricing_unit="per_tray", unit_price=1)
        db.add(mine)
        db.commit()

        total = sum(len(rows) for _, rows in MENU.values())
        assert seed(db) == (len(MENU) - 1, total - 1, 0)
        db.commit()
        assert seed(db) == (0, 0, 0)  # second run adds nothing

        assert db.scalar(select(func.count()).select_from(Dish)) == total
        db.refresh(mine)
        assert mine.unit_price == 1 and existing.sort_order == 9  # owner's data untouched
        dishes = db.scalars(select(Dish)).all()
        assert {d.dietary.kashrut_class for d in dishes if d.dietary} <= {"meat", "pareve"}
        assert all(d.dietary.verified_at is None for d in dishes if d.dietary)
        assert not any(a.allergen.name == "חלב" for d in dishes for a in d.allergens)


def test_dev_menu_only_fills_existing_categories(make_session):
    from app.core.seed_menu import DEV_MENU

    with make_session() as db:
        db.add_all(Allergen(name=n) for n in ALLERGENS)
        db.add_all(DishCategory(name=n) for n in list(DEV_MENU)[:-1])  # one category missing
        db.commit()
        try:
            seed(db, DEV_MENU, new_categories=False)
            raise AssertionError("expected a missing-category error")
        except ValueError as e:
            assert list(DEV_MENU)[-1] in str(e)
        db.rollback()
        assert db.scalar(select(func.count()).select_from(Dish)) == 0

        db.add(DishCategory(name=list(DEV_MENU)[-1]))
        db.commit()
        total = sum(len(rows) for _, rows in DEV_MENU.values())
        assert seed(db, DEV_MENU, new_categories=False) == (0, total, 0)
