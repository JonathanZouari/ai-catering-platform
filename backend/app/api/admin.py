import uuid
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.api.catalog import SessionDep
from app.core import storage
from app.core.auth import CurrentUser, OwnerDep
from app.models import Dish
from app.repositories import catalog as repo
from app.schemas.catalog import DishOut

router = APIRouter(prefix="/api/admin", tags=["admin"])

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # same limit as the dish-images bucket
IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def looks_like(content_type: str, data: bytes) -> bool:
    """Checks the file's first bytes: the content type the browser sends can be spoofed."""
    if content_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    return data[:4] == b"RIFF" and data[8:12] == b"WEBP"


@router.get("/me")
def me(user: OwnerDep) -> CurrentUser:
    return user


@router.get("/dishes")
def list_all_dishes(session: SessionDep, _owner: OwnerDep) -> list[DishOut]:
    """Every dish, including unavailable ones."""
    names = repo.allergen_names(session)
    return [DishOut.of(d, names) for d in repo.all_dishes(session)]


@router.post("/dishes/{dish_id}/image")
def upload_dish_image(
    dish_id: uuid.UUID,
    session: SessionDep,
    _owner: OwnerDep,
    file: Annotated[UploadFile, File()],
) -> DishOut:
    dish = session.get(Dish, dish_id)
    if dish is None:
        raise HTTPException(status_code=404, detail="Dish not found")
    content_type = file.content_type or ""
    if content_type not in IMAGE_TYPES:
        raise HTTPException(status_code=422, detail="Upload a JPEG, PNG or WebP image")
    data = file.file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image is larger than 5 MB")
    if not looks_like(content_type, data):
        raise HTTPException(status_code=422, detail="The file is not a valid image")

    path = f"{dish.id}/{uuid.uuid4()}.{IMAGE_TYPES[content_type]}"
    storage.upload(storage.DISH_IMAGES, path, data, content_type)
    old_path, dish.image_path = dish.image_path, path
    session.commit()
    if old_path:
        storage.remove(storage.DISH_IMAGES, [old_path])
    return DishOut.of(dish, repo.allergen_names(session))
