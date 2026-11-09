from collections.abc import Sequence
from uuid import UUID

from app.core.errors import AppError, not_found
from app.models import Dish, DishAllergen, DishCategory, DishDietary
from app.models.enums import AllergenStatus, PricingUnit
from app.repositories.catalog import CategoryRepository, DishRepository
from app.schemas.catalog import (
    CategoryCreate,
    CategoryUpdate,
    DietaryUpdate,
    DishCreate,
    DishUpdate,
)
from app.services.common import apply_patch, commit_or_conflict, get_or_404

DUPLICATE_CATEGORY = "כבר קיימת קטגוריה בשם הזה"


def create_category(repo: CategoryRepository, data: CategoryCreate) -> DishCategory:
    category = repo.add(DishCategory(**data.model_dump()))
    commit_or_conflict(repo.session, DUPLICATE_CATEGORY)
    return category


def update_category(
    repo: CategoryRepository, category_id: UUID, data: CategoryUpdate
) -> DishCategory:
    category = get_or_404(repo, category_id)
    apply_patch(category, data)
    commit_or_conflict(repo.session, DUPLICATE_CATEGORY)
    return category


def delete_category(repo: CategoryRepository, category_id: UUID) -> None:
    repo.delete(get_or_404(repo, category_id))
    commit_or_conflict(repo.session, "אי אפשר למחוק קטגוריה שיש בה מנות")


def _require_own_category(repo: DishRepository, category_id: UUID) -> None:
    # 404 like any other caterer's resource, so its existence isn't revealed.
    if CategoryRepository(repo.session, repo.scope).get(category_id) is None:
        raise not_found()


def list_dishes(repo: DishRepository, category_id: UUID | None) -> Sequence[Dish]:
    return repo.list_by_category(category_id) if category_id else repo.list_all()


def create_dish(repo: DishRepository, data: DishCreate) -> Dish:
    _require_own_category(repo, data.category_id)
    dish = repo.add(Dish(**data.model_dump()))
    commit_or_conflict(repo.session, "לא ניתן לשמור את המנה")
    return dish


def update_dish(repo: DishRepository, dish_id: UUID, data: DishUpdate) -> Dish:
    dish = get_or_404(repo, dish_id)
    if data.category_id is not None:
        _require_own_category(repo, data.category_id)
    apply_patch(dish, data)
    if dish.pricing_unit == PricingUnit.PER_WEIGHT and not dish.unit_label:
        repo.session.rollback()
        raise AppError(422, "validation_error", "במחיר לפי משקל יש לציין יחידת משקל")
    commit_or_conflict(repo.session, "לא ניתן לשמור את המנה")
    return dish


def delete_dish(repo: DishRepository, dish_id: UUID) -> None:
    repo.delete(get_or_404(repo, dish_id))
    commit_or_conflict(repo.session, "אי אפשר למחוק מנה שמופיעה בהזמנות. סמנו אותה כלא זמינה")


def set_dietary(repo: DishRepository, dish_id: UUID, data: DietaryUpdate) -> Dish:
    dish = get_or_404(repo, dish_id)
    fields = data.model_dump(exclude={"allergens"})
    if dish.dietary is None:
        dish.dietary = DishDietary(**fields)
    else:
        for field, value in fields.items():
            setattr(dish.dietary, field, value)

    # A missing row means unknown, so "unknown" entries aren't stored.
    known = {e.allergen_id: e.status for e in data.allergens if e.status != AllergenStatus.UNKNOWN}
    existing = {row.allergen_id: row for row in dish.allergens}
    for allergen_id, row in existing.items():
        if allergen_id not in known:
            dish.allergens.remove(row)
        else:
            row.status = known[allergen_id]
    dish.allergens.extend(
        DishAllergen(allergen_id=allergen_id, status=status)
        for allergen_id, status in known.items()
        if allergen_id not in existing
    )
    commit_or_conflict(repo.session, "אלרגן לא קיים")
    return dish
