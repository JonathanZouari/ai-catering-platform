from collections.abc import Sequence
from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.models import AiChangeProposal, AiConversation, AiMessage, AiUsage
from app.models.enums import ProposalStatus
from app.repositories.base import ScopedRepository


class ConversationRepository(ScopedRepository[AiConversation]):
    model = AiConversation

    def for_order(self, order_id: UUID) -> AiConversation | None:
        return self.session.scalar(self._select().where(AiConversation.order_id == order_id))


class MessageRepository(ScopedRepository[AiMessage]):
    model = AiMessage

    def latest(self, conversation_id: UUID, limit: int) -> Sequence[AiMessage]:
        """The most recent messages, oldest first. A question and its answer share a timestamp,
        so role breaks the tie: reversed below, the question comes first."""
        query = (
            self._select()
            .where(AiMessage.conversation_id == conversation_id)
            .order_by(AiMessage.created_at.desc(), AiMessage.role)
            .limit(limit)
        )
        return list(reversed(self.session.scalars(query).all()))

    def count_from_customer(self, conversation_id: UUID) -> int:
        query = (
            select(func.count())
            .select_from(AiMessage)
            .where(
                AiMessage.caterer_id == self.scope.caterer_id,
                AiMessage.conversation_id == conversation_id,
                AiMessage.role == "user",
            )
        )
        return self.session.scalar(query) or 0


class ProposalRepository(ScopedRepository[AiChangeProposal]):
    model = AiChangeProposal

    def for_order(
        self, order_id: UUID, status: ProposalStatus | None = None
    ) -> Sequence[AiChangeProposal]:
        query = self._select().where(AiChangeProposal.order_id == order_id)
        if status is not None:
            query = query.where(AiChangeProposal.status == status)
        return self.session.scalars(query.order_by(AiChangeProposal.created_at)).all()

    def lock(self, order_id: UUID, proposal_id: UUID) -> AiChangeProposal | None:
        query = (
            self._select()
            .where(AiChangeProposal.id == proposal_id, AiChangeProposal.order_id == order_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return self.session.scalar(query)


def consume_message(session, caterer_id: UUID, month: date, limit: int) -> bool:
    """Counts one message, atomically. False means the caterer is at the limit."""
    statement = insert(AiUsage).values(caterer_id=caterer_id, month=month, message_count=1)
    statement = statement.on_conflict_do_update(
        index_elements=[AiUsage.caterer_id, AiUsage.month],
        set_={"message_count": AiUsage.message_count + 1},
        where=AiUsage.message_count < limit,
    ).returning(AiUsage.message_count)
    return limit > 0 and session.execute(statement).first() is not None
