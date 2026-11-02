import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import Allergen, Dish, DishCategory, DishDietary


def list_categories(db: Session, active_only: bool = False) -> list[DishCategory]:
    q = select(DishCategory).order_by(DishCategory.sort_order, DishCategory.name)
    if active_only:
        q = q.where(DishCategory.is_active)
    return list(db.scalars(q))


def list_dishes(
    db: Session,
    *,
    public: bool = False,
    category_id: uuid.UUID | None = None,
    vegan: bool | None = None,
    vegetarian: bool | None = None,
    kashrut: str | None = None,
) -> list[Dish]:
    q = select(Dish).join(Dish.category).order_by(DishCategory.sort_order, Dish.name)
    if public:
        q = q.where(Dish.is_available, DishCategory.is_active)
    if category_id:
        q = q.where(Dish.category_id == category_id)
    if vegan is not None or vegetarian is not None or kashrut:
        q = q.outerjoin(DishDietary, DishDietary.dish_id == Dish.id)
        if vegan is not None:
            q = q.where(DishDietary.is_vegan.is_(vegan))
        if vegetarian is not None:
            q = q.where(DishDietary.is_vegetarian.is_(vegetarian))
        if kashrut:
            q = q.where(DishDietary.kashrut_class == kashrut)
    return list(db.scalars(q).unique())


def has_dishes(db: Session, category_id: uuid.UUID) -> bool:
    return db.scalar(select(Dish.id).where(Dish.category_id == category_id).limit(1)) is not None


def list_allergens(db: Session) -> list[Allergen]:
    return list(db.scalars(select(Allergen).order_by(Allergen.name)))
