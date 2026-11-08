"""Owner catalog management (screens A2 dishes & categories, A3 pricing)."""

import uuid

from fastapi import APIRouter, Depends, Request, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.core.security import require_admin
from app.schemas import catalog as s
from app.services import catalog as svc

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/categories", response_model=list[s.CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return svc.list_categories(db)


@router.post("/categories", response_model=s.CategoryOut, status_code=201)
def create_category(data: s.CategoryCreate, db: Session = Depends(get_db)):
    return svc.create_category(db, data)


@router.patch("/categories/{category_id}", response_model=s.CategoryOut)
def update_category(category_id: uuid.UUID, data: s.CategoryUpdate, db: Session = Depends(get_db)):
    return svc.update_category(db, category_id, data)


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: uuid.UUID, db: Session = Depends(get_db)):
    svc.delete_category(db, category_id)
    return Response(status_code=204)


@router.get("/dishes", response_model=list[s.DishOut])
def list_dishes(db: Session = Depends(get_db)):
    return [svc.to_out(d) for d in svc.list_dishes(db)]


@router.post("/dishes", response_model=s.DishOut, status_code=201)
def create_dish(data: s.DishCreate, db: Session = Depends(get_db)):
    return svc.to_out(svc.create_dish(db, data))


@router.get("/dishes/{dish_id}", response_model=s.DishOut)
def get_dish(dish_id: uuid.UUID, db: Session = Depends(get_db)):
    return svc.to_out(svc.get_dish(db, dish_id))


@router.patch("/dishes/{dish_id}", response_model=s.DishOut)
def update_dish(dish_id: uuid.UUID, data: s.DishUpdate, db: Session = Depends(get_db)):
    return svc.to_out(svc.update_dish(db, dish_id, data))


@router.delete("/dishes/{dish_id}", status_code=204)
def delete_dish(dish_id: uuid.UUID, db: Session = Depends(get_db)):
    svc.delete_dish(db, dish_id)
    return Response(status_code=204)


@router.put("/dishes/{dish_id}/dietary", response_model=s.DishOut)
def set_dietary(dish_id: uuid.UUID, data: s.DietaryUpdate, db: Session = Depends(get_db)):
    return svc.to_out(svc.set_dietary(db, dish_id, data))


@router.put("/dishes/{dish_id}/image", response_model=s.DishOut)
async def set_image(
    dish_id: uuid.UUID, request: Request, placeholder: bool = False, db: Session = Depends(get_db)
):
    """Body = the image file itself (Content-Type image/jpeg|png|webp), no multipart."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > svc.MAX_IMAGE_BYTES:
        raise AppError(413, "image_too_large", "Images are limited to 5 MB")
    data = bytearray()
    async for chunk in request.stream():  # stop reading past the limit, whatever the header said
        data += chunk
        if len(data) > svc.MAX_IMAGE_BYTES:
            raise AppError(413, "image_too_large", "Images are limited to 5 MB")
    content_type = request.headers.get("content-type", "")
    dish = await run_in_threadpool(
        svc.set_image, db, dish_id, bytes(data), content_type, placeholder
    )
    return svc.to_out(dish)


@router.delete("/dishes/{dish_id}/image", response_model=s.DishOut)
def remove_image(dish_id: uuid.UUID, db: Session = Depends(get_db)):
    return svc.to_out(svc.remove_image(db, dish_id))


@router.get("/allergens", response_model=list[s.AllergenOut])
def list_allergens(db: Session = Depends(get_db)):
    return svc.list_allergens(db)


@router.post("/allergens", response_model=s.AllergenOut, status_code=201)
def create_allergen(data: s.AllergenCreate, db: Session = Depends(get_db)):
    return svc.create_allergen(db, data)
