"""Catalog rules: categories, dishes, pricing fields, dietary and allergen data."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import storage
from app.core.errors import AppError
from app.models.catalog import Allergen, Dish, DishAllergen, DishCategory, DishDietary
from app.repositories import catalog as repo
from app.repositories import orders as orders_repo
from app.schemas import catalog as s


def _commit(db: Session, conflict_message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "conflict", conflict_message) from exc


def _get[T](db: Session, model: type[T], id_, what: str) -> T:
    obj = db.get(model, id_)
    if obj is None:
        raise AppError(404, "not_found", f"{what} not found")
    return obj


def _reject_nulls(changes: dict, required: set[str]) -> None:
    for key in required & changes.keys():
        if changes[key] is None:
            raise AppError(422, "validation_error", f"{key} cannot be null", {"field": key})


# categories


def list_categories(db: Session, active_only: bool = False) -> list[DishCategory]:
    return repo.list_categories(db, active_only)


def create_category(db: Session, data: s.CategoryCreate) -> DishCategory:
    category = DishCategory(**data.model_dump())
    db.add(category)
    _commit(db, "A category with this name already exists")
    return category


def update_category(db: Session, category_id: uuid.UUID, data: s.CategoryUpdate) -> DishCategory:
    category = _get(db, DishCategory, category_id, "Category")
    changes = data.model_dump(exclude_unset=True)
    _reject_nulls(changes, {"name", "sort_order", "is_active"})
    for key, value in changes.items():
        setattr(category, key, value)
    _commit(db, "A category with this name already exists")
    return category


def delete_category(db: Session, category_id: uuid.UUID) -> None:
    category = _get(db, DishCategory, category_id, "Category")
    if repo.has_dishes(db, category_id):
        raise AppError(409, "category_not_empty", "Move or delete the dishes in it first")
    db.delete(category)
    db.commit()


# dishes


def list_dishes(db: Session, **filters) -> list[Dish]:
    return repo.list_dishes(db, **filters)


def get_dish(db: Session, dish_id: uuid.UUID, public: bool = False) -> Dish:
    dish = _get(db, Dish, dish_id, "Dish")
    if public and not (dish.is_available and dish.category.is_active):
        raise AppError(404, "not_found", "Dish not found")
    return dish


def _check_category(db: Session, category_id: uuid.UUID) -> None:
    if db.get(DishCategory, category_id) is None:
        raise AppError(422, "validation_error", "Unknown category", {"field": "category_id"})


def create_dish(db: Session, data: s.DishCreate) -> Dish:
    _check_category(db, data.category_id)
    dish = Dish(**data.model_dump(), dietary=DishDietary())  # pareve until the owner says meat
    db.add(dish)
    db.commit()
    db.refresh(dish)
    return dish


def update_dish(db: Session, dish_id: uuid.UUID, data: s.DishUpdate) -> Dish:
    dish = _get(db, Dish, dish_id, "Dish")
    changes = data.model_dump(exclude_unset=True)
    required = {"category_id", "name", "pricing_unit", "unit_price", "is_available"}
    _reject_nulls(changes, required | {"contains_alcohol"})
    if "category_id" in changes:
        _check_category(db, changes["category_id"])
    for key, value in changes.items():
        setattr(dish, key, value)
    db.commit()
    db.refresh(dish)
    return dish


def delete_dish(db: Session, dish_id: uuid.UUID) -> None:
    dish = _get(db, Dish, dish_id, "Dish")
    if orders_repo.dish_in_orders(db, dish_id):
        raise AppError(409, "dish_in_orders", "Dish appears in orders; mark it unavailable instead")
    db.delete(dish)
    db.commit()


def set_dietary(db: Session, dish_id: uuid.UUID, data: s.DietaryUpdate) -> Dish:
    dish = _get(db, Dish, dish_id, "Dish")
    known = {a.id for a in repo.list_allergens(db)}
    ids = [a.allergen_id for a in data.allergens]
    if set(ids) - known or len(ids) != len(set(ids)):
        raise AppError(
            422, "validation_error", "Unknown or duplicate allergen", {"field": "allergens"}
        )
    if dish.dietary is None:
        dish.dietary = DishDietary()
    dish.dietary.kashrut_class = data.kashrut_class
    dish.dietary.is_vegetarian = data.is_vegetarian
    dish.dietary.is_vegan = data.is_vegan
    dish.dietary.verified_at = datetime.now(UTC)
    dish.allergens.clear()
    db.flush()
    dish.allergens.extend(
        DishAllergen(allergen_id=a.allergen_id, status=a.status)
        for a in data.allergens
        if a.status != "unknown"  # a missing row is how "unknown" is stored
    )
    db.commit()
    db.refresh(dish)
    return dish


# dish photos (Supabase Storage). image_path is either a static "/assets/..." file or a path in
# the bucket: "dishes/..." = the owner's own photo, "placeholder/..." = stand-in (OPEN #20).

MAX_IMAGE_BYTES = 5 * 1024 * 1024
IMAGE_TYPES = {  # content type -> (extension, check of the file's own first bytes)
    "image/jpeg": ("jpg", lambda b: b[:3] == b"\xff\xd8\xff"),
    "image/png": ("png", lambda b: b[:8] == b"\x89PNG\r\n\x1a\n"),
    "image/webp": ("webp", lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP"),
}


def _image_url(path: str | None) -> str | None:
    if not path:
        return None
    return path if path.startswith("/assets/") else storage.public_url(path)


def set_image(
    db: Session, dish_id: uuid.UUID, data: bytes, content_type: str, placeholder: bool = False
) -> Dish:
    dish = _get(db, Dish, dish_id, "Dish")
    kind = IMAGE_TYPES.get(content_type.split(";")[0].strip().lower())
    if kind is None or not kind[1](data):
        raise AppError(422, "invalid_image", "Upload a JPG, PNG or WebP image")
    if len(data) > MAX_IMAGE_BYTES:
        raise AppError(413, "image_too_large", "Images are limited to 5 MB")
    # Our own name (never the uploader's filename); a new name per upload busts caches.
    path = f"{'placeholder' if placeholder else 'dishes'}/{dish.id}/{uuid.uuid4().hex}.{kind[0]}"
    storage.upload(path, data, content_type)
    old, dish.image_path = dish.image_path, path
    db.commit()
    db.refresh(dish)
    if old and not old.startswith("/"):
        storage.delete(old)
    return dish


def remove_image(db: Session, dish_id: uuid.UUID) -> Dish:
    dish = _get(db, Dish, dish_id, "Dish")
    old, dish.image_path = dish.image_path, None
    db.commit()
    db.refresh(dish)
    if old and not old.startswith("/"):
        storage.delete(old)
    return dish


def to_out(dish: Dish) -> s.DishOut:
    computed = ("dietary", "allergens", "image_url", "image_is_placeholder")
    plain = {k: getattr(dish, k) for k in s.DishOut.model_fields if k not in computed}
    return s.DishOut(
        **plain,
        image_url=_image_url(dish.image_path),
        image_is_placeholder=bool(dish.image_path) and not dish.image_path.startswith("dishes/"),
        dietary=s.DietaryOut.model_validate(dish.dietary) if dish.dietary else s.DietaryOut(),
        allergens=[
            s.DishAllergenOut(allergen_id=a.allergen_id, name=a.allergen.name, status=a.status)
            for a in sorted(dish.allergens, key=lambda a: a.allergen.name)
        ],
    )


# allergens


def list_allergens(db: Session) -> list[Allergen]:
    return repo.list_allergens(db)


def create_allergen(db: Session, data: s.AllergenCreate) -> Allergen:
    allergen = Allergen(name=data.name)
    db.add(allergen)
    _commit(db, "An allergen with this name already exists")
    return allergen
