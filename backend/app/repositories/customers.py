import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orders import Customer, Event, Order


def by_auth_user(db: Session, auth_user_id: uuid.UUID) -> Customer | None:
    return db.scalar(select(Customer).where(Customer.auth_user_id == auth_user_id))


def orders_for(db: Session, customer_id: uuid.UUID) -> list[Order]:
    q = (
        select(Order)
        .join(Order.event)
        .where(Order.customer_id == customer_id)
        .order_by(Event.event_date.desc())
    )
    return list(db.scalars(q).unique())
