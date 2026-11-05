"""Private files on an order. Never imported by agents/: the assistant must not see them."""

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.storage import Storage, clean_name, content_type, quiet_delete
from app.models.orders import Order, OrderFile
from app.repositories import orders as repo
from app.schemas.account import OrderFileOut

MAX_FILES = 10


def out(f: OrderFile, storage: Storage) -> OrderFileOut:
    url = storage.sign(get_settings().order_files_bucket, f.path)
    return OrderFileOut(
        id=f.id, original_name=f.original_name, content_type=f.content_type,
        size_bytes=f.size_bytes, uploaded_by=f.uploaded_by, created_at=f.created_at, url=url,
    )  # fmt: skip


def list_files(db: Session, order: Order, storage: Storage) -> list[OrderFileOut]:
    return [out(f, storage) for f in repo.order_files(db, order.id)]


def add_file(
    db: Session, order: Order, data: bytes, kind: str, name: str | None, by: str, storage: Storage
) -> OrderFileOut:
    """`order` must be loaded with lock=True: the row lock serialises the 10-file count."""
    if repo.count_order_files(db, order.id) >= MAX_FILES:
        raise AppError(409, f"An order can have at most {MAX_FILES} files", code="file_limit")
    bucket = get_settings().order_files_bucket
    path = storage.upload(data, kind, bucket=bucket, prefix=f"{order.id}/")
    row = OrderFile(
        order_id=order.id, path=path, original_name=clean_name(name),
        content_type=content_type(kind), size_bytes=len(data), uploaded_by=by,
    )  # fmt: skip
    try:
        db.add(row)
        db.commit()
    except Exception:
        db.rollback()
        quiet_delete(storage, bucket, path)
        raise
    return out(row, storage)


def delete_file(db: Session, order: Order, file_id, storage: Storage) -> None:
    row = repo.get_order_file(db, order.id, file_id)
    if row is None:
        raise AppError(404, "File not found")
    storage.delete(get_settings().order_files_bucket, row.path)  # 502 keeps the row
    db.delete(row)
    db.commit()
