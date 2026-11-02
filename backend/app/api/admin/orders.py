"""Owner order management (screen A1)."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_admin
from app.schemas import orders as s
from app.services import orders as svc

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/orders", response_model=list[s.OrderSummaryOut])
def list_orders(status: s.OwnerStatus | None = None, db: Session = Depends(get_db)):
    return svc.list_orders(db, status)


@router.get("/orders/{order_id}", response_model=s.OrderDetailOut)
def get_order(order_id: uuid.UUID, db: Session = Depends(get_db)):
    return svc.get_order(db, order_id)


@router.post("/orders/{order_id}/approve", response_model=s.OrderDetailOut)
def approve(order_id: uuid.UUID, data: s.DecisionIn | None = None, db: Session = Depends(get_db)):
    return svc.decide(db, order_id, True, data or s.DecisionIn())


@router.post("/orders/{order_id}/reject", response_model=s.OrderDetailOut)
def reject(order_id: uuid.UUID, data: s.DecisionIn, db: Session = Depends(get_db)):
    return svc.decide(db, order_id, False, data)
