import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.catalog import Dish
from app.models.orders import Customer, Order, OrderFile, OrderItem, OrderStatus, QuantityRule


def _orders():
    return select(Order).options(
        selectinload(Order.items).selectinload(OrderItem.dish).selectinload(Dish.dietary),
        selectinload(Order.customer),
        selectinload(Order.event),
        selectinload(Order.zone),
    )


def get_order(db: Session, order_id: uuid.UUID, *, lock: bool = False):
    q = _orders().where(Order.id == order_id)
    if lock:  # serialises concurrent mutations of one order
        q = q.with_for_update(of=Order).execution_options(populate_existing=True)
    return db.scalar(q)


def list_orders(db: Session, status: OrderStatus | None):
    q = _orders().order_by(Order.created_at.desc())
    return list(db.scalars(q.where(Order.status == status) if status else q))


def get_item(order: Order, dish_id: uuid.UUID) -> OrderItem | None:
    return next((i for i in order.items if i.dish_id == dish_id), None)


def rules_by_category(db: Session) -> dict[uuid.UUID, QuantityRule]:
    return {r.category_id: r for r in db.scalars(select(QuantityRule))}


def get_rule(db: Session, category_id: uuid.UUID):
    return db.scalar(select(QuantityRule).where(QuantityRule.category_id == category_id))


def customer_by_auth(db: Session, auth_user_id: uuid.UUID) -> Customer | None:
    return db.scalar(select(Customer).where(Customer.auth_user_id == auth_user_id))


def orders_of_customer(db: Session, customer_id: uuid.UUID):
    q = _orders().where(Order.customer_id == customer_id).order_by(Order.created_at.desc())
    return list(db.scalars(q))


def order_files(db: Session, order_id: uuid.UUID) -> list[OrderFile]:
    q = select(OrderFile).where(OrderFile.order_id == order_id).order_by(OrderFile.created_at)
    return list(db.scalars(q))


def get_order_file(db: Session, order_id: uuid.UUID, file_id: uuid.UUID) -> OrderFile | None:
    q = select(OrderFile).where(OrderFile.order_id == order_id, OrderFile.id == file_id)
    return db.scalar(q)


def count_order_files(db: Session, order_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count()).select_from(OrderFile).where(OrderFile.order_id == order_id)
    )
