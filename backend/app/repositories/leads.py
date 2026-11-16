from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select

from app.models import (
    AiChangeProposal,
    AiConversation,
    AiMessage,
    Event,
    Lead,
    LeadEvent,
    LeadOutcome,
    Order,
)
from app.models.enums import LeadStage, ProposalStatus
from app.repositories.base import ScopedRepository


class LeadRepository(ScopedRepository[Lead]):
    model = Lead

    def get_by_order(self, order_id: UUID) -> Lead | None:
        return self.session.scalar(self._select().where(Lead.order_id == order_id))

    def list_ranked(self, stage: LeadStage | None) -> Sequence[tuple[Lead, Order]]:
        query = (
            select(Lead, Order)
            .join(Order, (Order.caterer_id == Lead.caterer_id) & (Order.id == Lead.order_id))
            .join(Event, Event.id == Order.event_id)
            .where(Lead.caterer_id == self.scope.caterer_id)
            .order_by(Lead.score.desc(), Event.event_date)
        )
        if stage is not None:
            query = query.where(Lead.stage == stage)
        return [(lead, order) for lead, order in self.session.execute(query).all()]

    def lock(self, lead_id: UUID) -> Lead | None:
        query = (
            self._select()
            .where(Lead.id == lead_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return self.session.scalar(query)

    def count_customer_messages(self, order_id: UUID) -> int:
        query = (
            select(func.count())
            .select_from(AiMessage)
            .join(AiConversation, AiConversation.id == AiMessage.conversation_id)
            .where(
                AiMessage.caterer_id == self.scope.caterer_id,
                AiConversation.order_id == order_id,
                AiMessage.role == "user",
            )
        )
        return self.session.scalar(query) or 0

    def count_proposals(self, order_id: UUID, status: ProposalStatus) -> int:
        query = (
            select(func.count())
            .select_from(AiChangeProposal)
            .where(
                AiChangeProposal.caterer_id == self.scope.caterer_id,
                AiChangeProposal.order_id == order_id,
                AiChangeProposal.status == status,
            )
        )
        return self.session.scalar(query) or 0


class LeadEventRepository(ScopedRepository[LeadEvent]):
    model = LeadEvent

    def for_lead(self, lead_id: UUID) -> Sequence[LeadEvent]:
        query = self._select().where(LeadEvent.lead_id == lead_id)
        return self.session.scalars(query.order_by(LeadEvent.created_at.desc())).all()


class LeadOutcomeRepository(ScopedRepository[LeadOutcome]):
    model = LeadOutcome

    def for_lead(self, lead_id: UUID) -> LeadOutcome | None:
        return self.session.scalar(self._select().where(LeadOutcome.lead_id == lead_id))
