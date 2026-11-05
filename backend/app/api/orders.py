from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends

from app.api.dishes import get_db
from app.schemas.orders import OrderCreate
from app.services import orders

router = APIRouter(prefix="/api")
Db = Annotated[psycopg.Connection, Depends(get_db)]


@router.get("/availability")
def get_availability(db: Db) -> dict:
    """Closed dates, delivery zones (fees in agorot) and time-slot labels."""
    return orders.availability(db)


@router.post("/orders", status_code=201)
def create_order(payload: OrderCreate, db: Db) -> dict:
    """Validates, prices server-side and stores the order as pending_approval."""
    return orders.create_order(db, payload)


@router.get("/orders/{order_id}")
def get_order(order_id: str, db: Db) -> dict:
    return orders.get_order(db, order_id)
