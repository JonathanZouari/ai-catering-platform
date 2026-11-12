import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from app.core.database import normalize_url
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
from app.seed import seed_catalog


def count(session: Session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_seed_fills_catalog(engine):
    with Session(engine) as session:
        assert count(session, DishCategory) == 6
        assert count(session, Dish) == 17
        hummus = session.scalars(select(Dish).where(Dish.name == "חומוס ביתי")).one()
        assert hummus.category.name == "סלטים ומטבלים"
        assert hummus.pricing_unit is PricingUnit.PER_TRAY
        assert hummus.unit_price_agorot == 8500


def test_seed_is_idempotent(engine):
    assert seed_catalog(engine) == (0, 0)


def test_negative_price_rejected(engine):
    with Session(engine) as session:
        category = session.scalars(select(DishCategory)).first()
        session.add(
            Dish(
                category=category,
                name="x",
                pricing_unit=PricingUnit.PER_ITEM,
                unit_price_agorot=-1,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_unknown_category_rejected(engine):
    with Session(engine) as session:
        session.add(
            Dish(
                category_id=uuid.uuid4(),
                name="x",
                pricing_unit=PricingUnit.PER_ITEM,
                unit_price_agorot=100,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_invalid_pricing_unit_rejected(engine):
    with Session(engine) as session:
        category = session.scalars(select(DishCategory)).first()
        session.add(
            Dish(category=category, name="x", pricing_unit="per_box", unit_price_agorot=100)
        )
        with pytest.raises((StatementError, IntegrityError)):
            session.commit()


def test_seed_fills_dietary_and_allergens(engine):
    with Session(engine) as session:
        assert count(session, Allergen) == 6
        assert count(session, DishDietary) == 17
        cheese = session.scalars(select(Dish).where(Dish.name == "סלט סלק וגבינת עיזים")).one()
        assert cheese.dietary.kashrut_class is KashrutClass.DAIRY
        assert cheese.dietary.is_vegan is False
        contains = {
            a.allergen.name for a in cheese.allergens if a.status is AllergenStatus.CONTAINS
        }
        assert contains == {"חלב", "אגוזים"}
        assert len(cheese.allergens) == 6  # verified list: every other allergen is free


def test_unknown_allergens_have_no_rows(engine):
    with Session(engine) as session:
        stew = session.scalars(select(Dish).where(Dish.name == "תבשיל קדרה צמחי")).one()
        assert stew.allergens == []


def test_seed_backfills_dietary_for_older_databases(engine):
    with Session(engine) as session, session.begin():
        session.query(DishAllergen).delete()
        session.query(DishDietary).delete()
    assert seed_catalog(engine) == (0, 0)
    with Session(engine) as session:
        assert count(session, DishDietary) == 17
        assert count(session, DishAllergen) == 16 * 6


def test_invalid_allergen_status_rejected(engine):
    with Session(engine) as session:
        dish = session.scalars(select(Dish)).first()
        allergen = session.scalars(select(Allergen)).first()
        session.execute(DishAllergen.__table__.delete())
        session.add(DishAllergen(dish=dish, allergen=allergen, status="maybe"))
        with pytest.raises((StatementError, IntegrityError)):
            session.commit()


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("postgresql://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
        ("postgres://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("sqlite:///./catering.db", "sqlite:///./catering.db"),
    ],
)
def test_normalize_url(url, expected):
    assert normalize_url(url) == expected
