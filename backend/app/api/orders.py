from uuid import UUID

from fastapi import APIRouter

from app.api.deps import OrderScopeDep, SessionDep
from app.schemas.orders import ItemSet, OrderOut, OrderUpdate, SubmitRequest
from app.services import orders

router = APIRouter(prefix="/api/orders")


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: UUID, session: SessionDep, scope: OrderScopeDep):
    return orders.view(session, scope, orders.get_order(session, scope, order_id))


@router.patch("/{order_id}", response_model=OrderOut)
def update_order(order_id: UUID, data: OrderUpdate, session: SessionDep, scope: OrderScopeDep):
    return orders.view(session, scope, orders.update_order(session, scope, order_id, data))


@router.put("/{order_id}/items/{dish_id}", response_model=OrderOut)
def set_item(
    order_id: UUID, dish_id: UUID, data: ItemSet, session: SessionDep, scope: OrderScopeDep
):
    return orders.view(session, scope, orders.set_item(session, scope, order_id, dish_id, data))


@router.delete("/{order_id}/items/{dish_id}", response_model=OrderOut)
def remove_item(
    order_id: UUID, dish_id: UUID, version: int, session: SessionDep, scope: OrderScopeDep
):
    order = orders.remove_item(session, scope, order_id, dish_id, version)
    return orders.view(session, scope, order)


@router.post("/{order_id}/submit", response_model=OrderOut)
def submit_order(order_id: UUID, data: SubmitRequest, session: SessionDep, scope: OrderScopeDep):
    return orders.view(session, scope, orders.submit_order(session, scope, order_id, data))
