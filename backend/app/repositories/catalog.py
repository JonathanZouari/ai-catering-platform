import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Allergen, Dish, DishAllergen, DishCategory, DishDietary, KashrutClass


def active_categories(session: Session) -> list[DishCategory]:
    query = (
        select(DishCategory)
        .where(DishCategory.is_active)
        .order_by(DishCategory.sort_order, DishCategory.name)
    )
    return list(session.scalars(query))


def allergen_names(session: Session) -> list[str]:
    return list(session.scalars(select(Allergen.name).order_by(Allergen.id)))


def _dish_query():
    return (
        select(Dish)
        .join(Dish.category)
        .where(Dish.is_available, DishCategory.is_active)
        .options(
            selectinload(Dish.dietary),
            selectinload(Dish.allergens).selectinload(DishAllergen.allergen),
        )
    )


def available_dishes(
    session: Session,
    *,
    category_id: uuid.UUID | None = None,
    vegan: bool | None = None,
    vegetarian: bool | None = None,
    kashrut: KashrutClass | None = None,
) -> list[Dish]:
    query = _dish_query()
    if category_id is not None:
        query = query.where(Dish.category_id == category_id)
    if vegan is not None or vegetarian is not None or kashrut is not None:
        # Inner join: a dish with no dietary row is unknown, so it never matches a dietary filter.
        query = query.join(Dish.dietary)
        if vegan is not None:
            query = query.where(DishDietary.is_vegan.is_(vegan))
        if vegetarian is not None:
            query = query.where(DishDietary.is_vegetarian.is_(vegetarian))
        if kashrut is not None:
            query = query.where(DishDietary.kashrut_class == kashrut)
    query = query.order_by(DishCategory.sort_order, Dish.created_at, Dish.name)
    return list(session.scalars(query))


def all_dishes(session: Session) -> list[Dish]:
    """Owner view: unavailable dishes and inactive categories included."""
    query = (
        select(Dish)
        .join(Dish.category)
        .options(
            selectinload(Dish.dietary),
            selectinload(Dish.allergens).selectinload(DishAllergen.allergen),
        )
        .order_by(DishCategory.sort_order, Dish.created_at, Dish.name)
    )
    return list(session.scalars(query))


def available_dish(session: Session, dish_id: uuid.UUID) -> Dish | None:
    return session.scalars(_dish_query().where(Dish.id == dish_id)).one_or_none()
