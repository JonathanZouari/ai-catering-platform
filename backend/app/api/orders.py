"""Signed-in customer's orders (screen C1). Items, pricing and submit come in later slices."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.customer_auth import CustomerIdentity, require_customer
from app.core.db import get_db
from app.schemas import customer_orders as s
from app.services import customer_orders as svc

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
