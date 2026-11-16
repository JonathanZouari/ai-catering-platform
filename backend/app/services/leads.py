from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import not_found
from app.core.tenancy import CatererScope
from app.models import Lead, LeadEvent, LeadOutcome, Order
from app.models.enums import LeadStage, ProposalStatus
from app.repositories.leads import LeadEventRepository, LeadOutcomeRepository, LeadRepository
from app.repositories.orders import OrderRepository
from app.schemas.leads import LeadEventOut, LeadNoteCreate, LeadOut, LeadStageUpdate, LeadSummary
from app.services import lead_scoring
from app.services.lead_scoring import Features

DECIDED = (LeadStage.WON, LeadStage.LOST)


def build_features(repo: LeadRepository, order: Order) -> Features:
    event = order.event
    submitted = order.submitted_at.date() if order.submitted_at else None
    categories = {item.dish.category.category_type for item in order.items}
    return Features(
        days_to_event=(event.event_date - submitted).days if submitted else None,
        guests=event.adults + event.children,
        total=float(order.total) if order.total is not None else None,
        categories=len(categories) if order.items else None,
        chat_messages=repo.count_customer_messages(order.id),
        proposals_accepted=repo.count_proposals(order.id, ProposalStatus.APPROVED),
        proposals_rejected=repo.count_proposals(order.id, ProposalStatus.REJECTED),
        has_email=True if order.customer.email else None,
        delivery_resolved=True if order.delivery_zone_id else None,
        kashrut_acknowledged=order.kashrut_warning_acknowledged,
    )


def record_submission(session: Session, scope: CatererScope, order_id: UUID) -> Lead:
    """Creates the lead for a submitted order, or rescores it. Runs after the order's own
    transaction has committed, so scoring never holds an order lock."""
    order = OrderRepository(session, scope).get(order_id)
    if order is None:
        raise not_found()
    repo = LeadRepository(session, scope)
    features = build_features(repo, order)
    result = lead_scoring.score(features)

    lead = repo.get_by_order(order.id)
    if lead is None:
        lead = repo.add(Lead(order_id=order.id, score=0, score_version=""))
    lead.score = result.probability
    lead.score_version = lead_scoring.SCORE_VERSION
    lead.reasons = result.reasons
    lead.features = features.as_dict()
    session.commit()
    return lead


def _summary(lead: Lead, order: Order) -> dict:
    return {
        "id": lead.id,
        "order_id": order.id,
        "stage": lead.stage,
        "score": lead.score,
        "band": lead_scoring.band(float(lead.score)),
        "customer_name": order.customer.full_name,
        "event_date": order.event.event_date,
        "guests": order.event.adults + order.event.children,
        "total": order.total,
        "submitted_at": order.submitted_at,
    }


def list_leads(session: Session, scope: CatererScope, stage: LeadStage | None) -> list[LeadSummary]:
    rows = LeadRepository(session, scope).list_ranked(stage)
    return [LeadSummary(**_summary(lead, order)) for lead, order in rows]


def _require(session: Session, scope: CatererScope, lead_id: UUID) -> Lead:
    lead = LeadRepository(session, scope).get(lead_id)
    if lead is None:
        raise not_found()
    return lead


def get_lead(session: Session, scope: CatererScope, lead_id: UUID) -> LeadOut:
    lead = _require(session, scope, lead_id)
    order = OrderRepository(session, scope).get(lead.order_id)
    if order is None:
        raise not_found()
    # Rebuilt from the stored features, so "unknown" always matches the score on screen.
    unknown = lead_scoring.score(Features(**lead.features)).unknown
    events = LeadEventRepository(session, scope).for_lead(lead.id)
    return LeadOut(
        **_summary(lead, order),
        phone=order.customer.phone,
        reasons=lead.reasons,
        unknown=unknown,
        events=[LeadEventOut.model_validate(event) for event in events],
    )


def change_stage(
    session: Session, scope: CatererScope, lead_id: UUID, data: LeadStageUpdate
) -> LeadOut:
    repo = LeadRepository(session, scope)
    lead = repo.lock(lead_id)
    if lead is None:
        raise not_found()
    if lead.stage != data.stage:
        lead.stage = data.stage
        LeadEventRepository(session, scope).add(
            LeadEvent(lead_id=lead.id, kind="stage_change", stage=data.stage)
        )
        outcomes = LeadOutcomeRepository(session, scope)
        if data.stage in DECIDED and outcomes.for_lead(lead.id) is None:
            # Written once: the score and features as they were when the caterer decided.
            outcomes.add(
                LeadOutcome(
                    lead_id=lead.id,
                    outcome=data.stage,
                    score_at_decision=lead.score,
                    score_version=lead.score_version,
                    features=lead.features,
                )
            )
    session.commit()
    return get_lead(session, scope, lead_id)


def add_note(session: Session, scope: CatererScope, lead_id: UUID, data: LeadNoteCreate) -> LeadOut:
    lead = _require(session, scope, lead_id)
    LeadEventRepository(session, scope).add(
        LeadEvent(lead_id=lead.id, kind="note", note=data.note.strip())
    )
    session.commit()
    return get_lead(session, scope, lead_id)
