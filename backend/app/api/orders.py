from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends

from app.agents.client import LLMClient, get_llm
from app.agents.loop import run_chat
from app.api.deps import OrderScopeDep, SessionDep
from app.core.email import Mailer, get_mailer
from app.core.rate_limit import limit_chat, limit_order_writes
from app.models.enums import ProposalStatus
from app.schemas.ai import ChatReply, ChatRequest, ChatState, ProposalDecision, ProposalOut
from app.schemas.orders import ItemSet, OrderOut, OrderUpdate, SubmitRequest
from app.services import assistant, notifications, orders, proposals

router = APIRouter(prefix="/api/orders", dependencies=[Depends(limit_order_writes)])

LLMDep = Annotated[LLMClient | None, Depends(get_llm)]
MailerDep = Annotated[Mailer | None, Depends(get_mailer)]


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
def submit_order(
    order_id: UUID,
    data: SubmitRequest,
    session: SessionDep,
    scope: OrderScopeDep,
    mailer: MailerDep,
    background: BackgroundTasks,
):
    order = orders.submit_order(session, scope, order_id, data)
    email = notifications.new_order_email(session, scope, order) if mailer else None
    if email:
        background.add_task(notifications.deliver, mailer, email, order.id)
    return orders.view(session, scope, order)


def _decision(session, scope, proposal, order) -> ProposalDecision:
    return ProposalDecision(
        proposal=ProposalOut.model_validate(proposal), order=orders.view(session, scope, order)
    )


@router.get("/{order_id}/chat", response_model=ChatState)
def get_chat(order_id: UUID, session: SessionDep, scope: OrderScopeDep, llm: LLMDep):
    pending = proposals.list_proposals(session, scope, order_id, ProposalStatus.PENDING)
    return ChatState(
        available=llm is not None,
        messages=assistant.history(session, scope, order_id),
        proposals=[ProposalOut.model_validate(item) for item in pending],
    )


@router.post("/{order_id}/chat", response_model=ChatReply, dependencies=[Depends(limit_chat)])
def chat(order_id: UUID, data: ChatRequest, session: SessionDep, scope: OrderScopeDep, llm: LLMDep):
    return run_chat(session, scope, order_id, data.message, llm)


@router.get("/{order_id}/proposals", response_model=list[ProposalOut])
def list_proposals(
    order_id: UUID,
    session: SessionDep,
    scope: OrderScopeDep,
    status: ProposalStatus | None = None,
):
    return proposals.list_proposals(session, scope, order_id, status)


@router.post("/{order_id}/proposals/{proposal_id}/approve", response_model=ProposalDecision)
def approve_proposal(order_id: UUID, proposal_id: UUID, session: SessionDep, scope: OrderScopeDep):
    proposal, order = proposals.approve_proposal(session, scope, order_id, proposal_id)
    return _decision(session, scope, proposal, order)


@router.post("/{order_id}/proposals/{proposal_id}/reject", response_model=ProposalDecision)
def reject_proposal(order_id: UUID, proposal_id: UUID, session: SessionDep, scope: OrderScopeDep):
    proposal, order = proposals.reject_proposal(session, scope, order_id, proposal_id)
    return _decision(session, scope, proposal, order)
