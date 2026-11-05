import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, UploadFile
from fastapi.security import HTTPAuthorizationCredentials

from app.api.catalog import Lang
from app.core.db import Db
from app.core.errors import AppError
from app.core.ratelimit import limit
from app.core.security import bearer, optional_customer
from app.core.storage import Storage, get_storage, read_upload
from app.models.orders import EVENT_TYPES
from app.schemas.account import OrderFileOut
from app.schemas.orders import (
    ItemIn,
    OrderCreate,
    OrderCreated,
    OrderOut,
    OrderPatch,
    PricingOut,
    RatingIn,
    RecommendationOut,
    SubmitIn,
)
from app.services import files as file_service
from app.services import orders as service
from app.services.geo import Geocoder, get_geocoder

router = APIRouter(prefix="/api")
# Private link token issued once by POST /api/orders; wrong token and unknown id both give 404.
Token = Annotated[str | None, Header(alias="X-Order-Token")]
Geo = Annotated[Geocoder, Depends(get_geocoder)]
Files = Annotated[Storage, Depends(get_storage)]


def _viewer(claims: Annotated[dict | None, Depends(optional_customer)]) -> uuid.UUID | None:
    return uuid.UUID(claims["sub"]) if claims else None


def _viewer_or_guest(creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    """Bearer lets an account owner open its order; a bad bearer must not break the link token."""
    try:
        return _viewer(optional_customer(creds))
    except AppError:
        return None


Viewer = Annotated[uuid.UUID | None, Depends(_viewer_or_guest)]


@router.get("/catalog/event-types")
def event_types() -> list[str]:
    # shortcut: constant list; move to the admin if the owner wants to edit it.
    return list(EVENT_TYPES)


@router.post("/orders", status_code=201, dependencies=[Depends(limit("orders", 10, 3600))])
def create_order(
    body: OrderCreate, db: Db, geocode: Geo,
    claims: Annotated[dict | None, Depends(optional_customer)], lang: Lang = "he",
) -> OrderCreated:  # fmt: skip
    return service.create_order(db, body, lang, geocode, claims)


@router.get("/orders/{order_id}")
def get_order(
    order_id: uuid.UUID, db: Db, viewer: Viewer, token: Token = None, lang: Lang = "he"
) -> OrderOut:
    return service.get_order(db, order_id, token, lang, viewer)


@router.patch("/orders/{order_id}")
def patch_order(
    order_id: uuid.UUID, body: OrderPatch, db: Db, geocode: Geo, token: Token = None,
    lang: Lang = "he",
) -> OrderOut:  # fmt: skip
    return service.patch_order(db, order_id, token, body, lang, geocode)


@router.put("/orders/{order_id}/items/{dish_id}")
def put_item(
    order_id: uuid.UUID, dish_id: uuid.UUID, body: ItemIn, db: Db, token: Token = None,
    lang: Lang = "he",
) -> OrderOut:  # fmt: skip
    return service.set_item(db, order_id, token, dish_id, body.quantity, body.version, lang)


@router.delete("/orders/{order_id}/items/{dish_id}")
def delete_item(
    order_id: uuid.UUID, dish_id: uuid.UUID, version: int, db: Db, token: Token = None,
    lang: Lang = "he",
) -> OrderOut:  # fmt: skip
    return service.remove_item(db, order_id, token, dish_id, version, lang)


@router.get("/orders/{order_id}/pricing")
def get_pricing(
    order_id: uuid.UUID, db: Db, viewer: Viewer, token: Token = None, lang: Lang = "he"
) -> PricingOut:
    return service.get_pricing(db, order_id, token, lang, viewer)


@router.get("/orders/{order_id}/recommendations")
def get_recommendations(
    order_id: uuid.UUID, db: Db, token: Token = None
) -> list[RecommendationOut]:
    return service.recommendations(db, order_id, token)


@router.post("/orders/{order_id}/submit")
def submit_order(
    order_id: uuid.UUID, body: SubmitIn, db: Db, token: Token = None, lang: Lang = "he"
) -> OrderOut:
    return service.submit(db, order_id, token, body.version, lang, body.sms_opt_in)


@router.post("/orders/{order_id}/reopen")
def reopen_order(
    order_id: uuid.UUID, body: SubmitIn, db: Db, token: Token = None, lang: Lang = "he"
) -> OrderOut:
    return service.reopen(db, order_id, token, body.version, lang)


@router.post("/orders/{order_id}/rating")
def rate_order(
    order_id: uuid.UUID, body: RatingIn, db: Db, token: Token = None, lang: Lang = "he"
) -> OrderOut:
    return service.rate(db, order_id, token, body, lang)


@router.get("/orders/{order_id}/files")
def list_files(
    order_id: uuid.UUID, db: Db, storage: Files, viewer: Viewer, token: Token = None
) -> list[OrderFileOut]:
    order = service.customer_order(db, order_id, token, viewer=viewer)
    return file_service.list_files(db, order, storage)


@router.post("/orders/{order_id}/files", status_code=201)
# Sync on purpose: the storage upload uses blocking httpx, so FastAPI runs it in the threadpool.
def upload_file(
    order_id: uuid.UUID, file: UploadFile, db: Db, storage: Files, viewer: Viewer,
    token: Token = None,
) -> OrderFileOut:  # fmt: skip
    order = service.customer_order(db, order_id, token, lock=True, viewer=viewer)
    data, kind = read_upload(file, pdf=True)
    return file_service.add_file(db, order, data, kind, file.filename, "customer", storage)


@router.delete("/orders/{order_id}/files/{file_id}", status_code=204)
def delete_file(
    order_id: uuid.UUID, file_id: uuid.UUID, db: Db, storage: Files, viewer: Viewer,
    token: Token = None,
) -> None:  # fmt: skip
    order = service.customer_order(db, order_id, token, lock=True, viewer=viewer)
    file_service.delete_file(db, order, file_id, storage)
