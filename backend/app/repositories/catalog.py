from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Allergen, Dish, DishCategory
from app.repositories.base import ScopedRepository


class CategoryRepository(ScopedRepository[DishCategory]):
    model = DishCategory
    default_order = (DishCategory.sort_order, DishCategory.name)


class DishRepository(ScopedRepository[Dish]):
    model = Dish
    default_order = (Dish.name,)

    def list_by_category(self, category_id: UUID) -> Sequence[Dish]:
        query = self._select().where(Dish.category_id == category_id).order_by(Dish.name)
        return self.session.scalars(query).all()


def list_allergens(session: Session) -> Sequence[Allergen]:
    """Platform-wide list, so it isn't tenant scoped."""
    return session.scalars(select(Allergen).order_by(Allergen.id)).all()
