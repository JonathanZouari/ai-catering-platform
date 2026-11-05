from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile

from app.core.db import Db
from app.core.ratelimit import limit
from app.core.security import require_customer
from app.core.storage import Storage, get_storage, read_upload
from app.schemas.account import CustomerOut, CustomerPatch
from app.schemas.orders import OrderSummary
from app.services import account as service
from app.services import orders as order_service

router = APIRouter(prefix="/api/me")
Claims = Annotated[dict, Depends(require_customer)]
Files = Annotated[Storage, Depends(get_storage)]


def _me(db: Db, claims: dict):
    customer = service.ensure_customer(db, claims)
    db.commit()
    return customer


@router.get("")
def get_me(db: Db, claims: Claims, storage: Files) -> CustomerOut:
    return service.me_out(_me(db, claims), storage)


@router.patch("")
def patch_me(body: CustomerPatch, db: Db, claims: Claims, storage: Files) -> CustomerOut:
    return service.me_out(service.update_me(db, _me(db, claims), body), storage)


@router.get("/orders")
def my_orders(db: Db, claims: Claims) -> list[OrderSummary]:
    return order_service.my_orders(db, _me(db, claims))


@router.post("/avatar", dependencies=[Depends(limit("uploads", 30, 3600))])
# Sync on purpose: the storage upload uses blocking httpx, so FastAPI runs it in the threadpool.
def upload_avatar(file: UploadFile, db: Db, claims: Claims, storage: Files) -> CustomerOut:
    data, kind = read_upload(file)
    customer = service.set_avatar(db, _me(db, claims), data, kind, storage)
    return service.me_out(customer, storage)


@router.delete("/avatar")
def delete_avatar(db: Db, claims: Claims, storage: Files) -> CustomerOut:
    return service.me_out(service.remove_avatar(db, _me(db, claims), storage), storage)
