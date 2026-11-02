"""Owner order management (screen A1)."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core import mailer
from app.core.db import get_db
from app.core.security import require_admin
from app.schemas import orders as s
from app.schemas import proposals as ps
from app.services import notifications, proposals
from app.services import orders as svc

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/orders", response_model=list[s.OrderSummaryOut])
def list_orders(status: s.OwnerStatus | None = None, db: Session = Depends(get_db)):
    return svc.list_orders(db, status)


@router.get("/orders/{order_id}", response_model=s.OrderDetailOut)
def get_order(order_id: uuid.UUID, db: Session = Depends(get_db)):
    return svc.get_order(db, order_id)


def _decide(db: Session, order_id: uuid.UUID, approve: bool, data, background: BackgroundTasks):
    order = svc.decide(db, order_id, approve, data)
    if email := notifications.order_decided(db, order_id):
        background.add_task(mailer.send, email)  # after the response; never blocks the decision
    return order


@router.post("/orders/{order_id}/approve", response_model=s.OrderDetailOut)
def approve(
    order_id: uuid.UUID,
    background: BackgroundTasks,
    data: s.DecisionIn | None = None,
    db: Session = Depends(get_db),
):
    return _decide(db, order_id, True, data or s.DecisionIn(), background)


@router.post("/orders/{order_id}/reject", response_model=s.OrderDetailOut)
def reject(
    order_id: uuid.UUID,
    data: s.DecisionIn,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return _decide(db, order_id, False, data, background)


@router.get("/orders/{order_id}/proposals", response_model=list[ps.ProposalOut])
def list_proposals(order_id: uuid.UUID, db: Session = Depends(get_db)):
    svc.get_order(db, order_id)  # 404 for drafts and unknown orders
    return proposals.list_for_order(db, order_id)


@router.post("/orders/{order_id}/proposals", response_model=ps.ProposalOut, status_code=201)
def propose(
    order_id: uuid.UUID,
    data: ps.ProposalCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    proposal = proposals.create(db, order_id, data)
    if email := notifications.proposal_created(db, proposal.id):
        background.add_task(mailer.send, email)
    return proposal


@router.post("/orders/{order_id}/proposals/{proposal_id}/cancel", response_model=ps.ProposalOut)
def cancel_proposal(order_id: uuid.UUID, proposal_id: uuid.UUID, db: Session = Depends(get_db)):
    return proposals.cancel(db, order_id, proposal_id)
