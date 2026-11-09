from uuid import UUID

from fastapi import APIRouter

from app.api.deps import ScopeDep, SessionDep
from app.models.enums import OrderStatus
from app.schemas.orders import AdminOrderOut, ApproveRequest, OrderSummary, RejectRequest
from app.services import orders

router = APIRouter(prefix="/orders")


@router.get("", response_model=list[OrderSummary])
def list_orders(session: SessionDep, scope: ScopeDep, status: OrderStatus | None = None):
    return orders.list_orders(session, scope, status)


@router.get("/{order_id}", response_model=AdminOrderOut)
def get_order(order_id: UUID, session: SessionDep, scope: ScopeDep):
    return orders.admin_view(session, scope, orders.get_submitted(session, scope, order_id))


@router.post("/{order_id}/approve", response_model=AdminOrderOut)
def approve_order(order_id: UUID, data: ApproveRequest, session: SessionDep, scope: ScopeDep):
    return orders.admin_view(session, scope, orders.approve_order(session, scope, order_id, data))


@router.post("/{order_id}/reject", response_model=AdminOrderOut)
def reject_order(order_id: UUID, data: RejectRequest, session: SessionDep, scope: ScopeDep):
    return orders.admin_view(session, scope, orders.reject_order(session, scope, order_id, data))
