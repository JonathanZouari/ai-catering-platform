"""Private files on an order. Never imported by agents/: the assistant must not see them."""

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.storage import Storage, clean_name, content_type, quiet_delete, safe_sign
from app.models.orders import Order, OrderFile, OrderStatus
from app.repositories import orders as repo
from app.schemas.account import OrderFileOut

MAX_FILES = 10


CLOSED = (OrderStatus.delivered, OrderStatus.cancelled, OrderStatus.rejected)


def out(f: OrderFile, storage: Storage) -> OrderFileOut:
    url = safe_sign(storage, get_settings().order_files_bucket, f.path)
    return OrderFileOut(
        id=f.id, original_name=f.original_name, content_type=f.content_type,
        size_bytes=f.size_bytes, uploaded_by=f.uploaded_by, created_at=f.created_at, url=url,
    )  # fmt: skip


def list_files(db: Session, order: Order, storage: Storage) -> list[OrderFileOut]:
    return [out(f, storage) for f in repo.order_files(db, order.id)]  # read-only: no row lock


def _check_open(order: Order, by: str) -> None:
    if by == "customer" and order.status in CLOSED:
        raise AppError(409, "This order is closed; its files can no longer be changed",
                       code="order_closed")  # fmt: skip


def _check_room(db: Session, order: Order) -> None:
    if repo.count_order_files(db, order.id) >= MAX_FILES:
        raise AppError(409, f"An order can have at most {MAX_FILES} files", code="file_limit")


def add_file(
    db: Session, order: Order, data: bytes, kind: str, name: str | None, by: str, storage: Storage
) -> OrderFileOut:
    _check_open(order, by)
    _check_room(db, order)  # cheap early exit; the locked re-check below is the real one
    bucket = get_settings().order_files_bucket
    # Upload first, so the row lock is never held across a Storage HTTP call.
    path = storage.upload(data, kind, bucket=bucket, prefix=f"{order.id}/")
    try:
        order = repo.get_order(db, order.id, lock=True)  # serialises the 10-file count
        _check_open(order, by)
        _check_room(db, order)
        row = OrderFile(
            order_id=order.id, path=path, original_name=clean_name(name),
            content_type=content_type(kind), size_bytes=len(data), uploaded_by=by,
        )  # fmt: skip
        db.add(row)
        db.commit()
    except Exception:
        db.rollback()
        quiet_delete(storage, bucket, path)  # limit hit or DB failure: no orphan object
        raise
    return out(row, storage)  # saved already: a signing failure only blanks the url


def delete_file(db: Session, order: Order, file_id, storage: Storage, by: str) -> None:
    _check_open(order, by)
    row = repo.get_order_file(db, order.id, file_id)
    if row is None:
        raise AppError(404, "File not found")
    if by == "customer" and row.uploaded_by != "customer":
        raise AppError(403, "Only the owner can remove this file", code="file_owner")
    storage.delete(get_settings().order_files_bucket, row.path)  # 502 keeps the row
    db.delete(row)
    db.commit()
