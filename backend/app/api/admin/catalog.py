"""Owner catalog management (screens A2 dishes & categories, A3 pricing)."""

import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
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


@router.get("/allergens", response_model=list[s.AllergenOut])
def list_allergens(db: Session = Depends(get_db)):
    return svc.list_allergens(db)


@router.post("/allergens", response_model=s.AllergenOut, status_code=201)
def create_allergen(data: s.AllergenCreate, db: Session = Depends(get_db)):
    return svc.create_allergen(db, data)
