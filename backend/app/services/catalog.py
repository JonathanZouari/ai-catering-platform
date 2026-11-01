from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.core.errors import conflict, not_found
from app.models import DishCategory
from app.repositories.catalog import CategoryRepository
from app.schemas.catalog import CategoryCreate, CategoryUpdate


def list_categories(repo: CategoryRepository) -> Sequence[DishCategory]:
    return repo.list_all()


def get_category(repo: CategoryRepository, category_id: UUID) -> DishCategory:
    category = repo.get(category_id)
    if category is None:
        raise not_found()
    return category


def create_category(repo: CategoryRepository, data: CategoryCreate) -> DishCategory:
    try:
        category = repo.add(DishCategory(**data.model_dump()))
        repo.session.commit()
    except IntegrityError as exc:
        repo.session.rollback()
        raise conflict("כבר קיימת קטגוריה בשם הזה") from exc
    return category


def update_category(
    repo: CategoryRepository, category_id: UUID, data: CategoryUpdate
) -> DishCategory:
    category = get_category(repo, category_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    try:
        repo.session.commit()
    except IntegrityError as exc:
        repo.session.rollback()
        raise conflict("כבר קיימת קטגוריה בשם הזה") from exc
    return category
