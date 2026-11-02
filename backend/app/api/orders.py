"""Signed-in customer's orders: event (C1), items (C2), pricing and recommendations (C3)."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core import mailer
from app.core.customer_auth import CustomerIdentity, require_customer
from app.core.db import get_db
from app.schemas import customer_orders as s
from app.services import customer_orders as svc
from app.services import notifications

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.post("", response_model=s.CustomerOrderOut, status_code=201)
def create_draft(
    data: s.DraftIn,
    who: CustomerIdentity = Depends(require_customer),
    db: Session = Depends(get_db),
):
    return svc.create_draft(db, who, data)


@router.get("/{order_id}", response_model=s.CustomerOrderOut)
def get_order(
    order_id: uuid.UUID,
    who: CustomerIdentity = Depends(require_customer),
    db: Session = Depends(get_db),
):
    return svc.get_order(db, who, order_id)


@router.patch("/{order_id}", response_model=s.CustomerOrderOut)
def update_draft(
    order_id: uuid.UUID,
    data: s.DraftUpdate,
    who: CustomerIdentity = Depends(require_customer),
    db: Session = Depends(get_db),
):
    return svc.update_draft(db, who, order_id, data)


@router.put("/{order_id}/items/{dish_id}", response_model=s.CustomerOrderOut)
def set_item(
    order_id: uuid.UUID,
    dish_id: uuid.UUID,
    data: s.ItemIn,
    who: CustomerIdentity = Depends(require_customer),
    db: Session = Depends(get_db),
):
    return svc.set_item(db, who, order_id, dish_id, data)


@router.delete("/{order_id}/items/{dish_id}", response_model=s.CustomerOrderOut)
def remove_item(
    order_id: uuid.UUID,
    dish_id: uuid.UUID,
    version: int,
    who: CustomerIdentity = Depends(require_customer),
    db: Session = Depends(get_db),
):
    return svc.remove_item(db, who, order_id, dish_id, version)


@router.get("/{order_id}/pricing", response_model=s.PricingOut)
def pricing(
    order_id: uuid.UUID,
    who: CustomerIdentity = Depends(require_customer),
    db: Session = Depends(get_db),
):
    return svc.get_pricing(db, who, order_id)


@router.get("/{order_id}/recommendations", response_model=list[s.RecommendationOut])
def recommendations(
    order_id: uuid.UUID,
    who: CustomerIdentity = Depends(require_customer),
    db: Session = Depends(get_db),
):
    return svc.get_recommendations(db, who, order_id)


@router.post("/{order_id}/submit", response_model=s.CustomerOrderOut)
def submit(
    order_id: uuid.UUID,
    data: s.VersionIn,
    background: BackgroundTasks,
    who: CustomerIdentity = Depends(require_customer),
    db: Session = Depends(get_db),
):
    order = svc.submit(db, who, order_id, data.version)
    if email := notifications.order_submitted(db, order_id):
        background.add_task(mailer.send, email)  # after the response; never blocks the order
    return order


@router.post("/{order_id}/withdraw", response_model=s.CustomerOrderOut)
def withdraw(
    order_id: uuid.UUID,
    data: s.VersionIn,
    who: CustomerIdentity = Depends(require_customer),
    db: Session = Depends(get_db),
):
    return svc.withdraw(db, who, order_id, data.version)
