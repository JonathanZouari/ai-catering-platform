"""Public catalog read API: only active categories and available dishes."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.schemas import catalog as s
from app.schemas.settings import AccessibilityContact, BusinessOut
from app.services import catalog as svc
from app.services import settings as settings_svc

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@router.get("/business", response_model=BusinessOut)
def business(db: Session = Depends(get_db)):
    """Public facts: the kashrut certificate (OPEN_DECISIONS #9), accessibility contact."""
    env = get_settings()
    return BusinessOut(
        kashrut_certificate=settings_svc.get(db).kashrut_certificate,
        accessibility_contact=AccessibilityContact(
            name=env.accessibility_contact_name,
            phone=env.accessibility_contact_phone,
            email=env.accessibility_contact_email or env.owner_email,
        ),
    )


@router.get("/categories", response_model=list[s.CategoryOut])
def categories(db: Session = Depends(get_db)):
    return svc.list_categories(db, active_only=True)


@router.get("/dishes", response_model=list[s.DishOut])
def dishes(
    category_id: uuid.UUID | None = None,
    vegan: bool | None = None,
    vegetarian: bool | None = None,
    kashrut: Literal["meat", "pareve"] | None = None,
    db: Session = Depends(get_db),
):
    found = svc.list_dishes(
        db,
        public=True,
        category_id=category_id,
        vegan=vegan,
        vegetarian=vegetarian,
        kashrut=kashrut,
    )
    return [svc.to_out(d) for d in found]


@router.get("/dishes/{dish_id}", response_model=s.DishOut)
def dish(dish_id: uuid.UUID, db: Session = Depends(get_db)):
    return svc.to_out(svc.get_dish(db, dish_id, public=True))
