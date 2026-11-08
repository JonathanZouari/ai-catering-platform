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
