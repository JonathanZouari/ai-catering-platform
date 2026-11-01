from collections.abc import Sequence

from app.models import DishCategory
from app.repositories.base import ScopedRepository


class CategoryRepository(ScopedRepository[DishCategory]):
    model = DishCategory

    def list_all(self) -> Sequence[DishCategory]:
        query = self._select().order_by(DishCategory.sort_order, DishCategory.name)
        return self.session.scalars(query).all()
