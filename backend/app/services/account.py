import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.storage import Storage, quiet_delete, safe_sign
from app.models.orders import Customer
from app.repositories import orders as repo
from app.schemas.account import CustomerOut, CustomerPatch


def ensure_customer(db: Session, claims: dict, details: dict | None = None) -> Customer:
    """The signed-in user's customer row, created on first use. Flushes; the caller commits.

    details: name/email/phone from an order form; used instead of the token's own claims.
    """
    uid = uuid.UUID(claims["sub"])
    customer = repo.customer_by_auth(db, uid)
    if customer:
        return customer
    if details is None:
        email = claims.get("email")
        if not email:
            raise AppError(403, "This account has no email address")
        name = (claims.get("user_metadata") or {}).get("full_name") or email.split("@")[0]
        details = {"full_name": str(name)[:200], "email": email[:254]}
    try:
        with db.begin_nested():  # a concurrent first request may win the unique auth_user_id
            customer = Customer(auth_user_id=uid, **details)
            db.add(customer)
            db.flush()
    except IntegrityError:
        customer = repo.customer_by_auth(db, uid)
    return customer


def me_out(customer: Customer, storage: Storage) -> CustomerOut:
    return CustomerOut(
        id=customer.id, full_name=customer.full_name, email=customer.email, phone=customer.phone,
        avatar_url=safe_sign(storage, get_settings().avatar_bucket, customer.avatar_path),
    )  # fmt: skip


def update_me(db: Session, customer: Customer, body: CustomerPatch) -> Customer:
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is not None:  # full_name is required; phone has no "clear" yet
            setattr(customer, field, value)
    db.commit()
    return customer


def set_avatar(db: Session, customer: Customer, data: bytes, kind: str, storage: Storage):
    bucket = get_settings().avatar_bucket
    new = storage.upload(data, kind, bucket=bucket, prefix=f"{customer.id}/")
    old, customer.avatar_path = customer.avatar_path, new
    try:
        db.commit()
    except Exception:
        db.rollback()
        quiet_delete(storage, bucket, new)  # no orphan, and the row never pointed at it
        raise
    if old:
        quiet_delete(storage, bucket, old)
    return customer


def remove_avatar(db: Session, customer: Customer, storage: Storage):
    if customer.avatar_path:
        # Object first: if storage fails we answer 502 and the row still points at a real file.
        storage.delete(get_settings().avatar_bucket, customer.avatar_path)
        customer.avatar_path = None
        db.commit()
    return customer
