from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, FetchedValue, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin
from app.models.enums import ProposalStatus, db_enum
from app.models.types import Hundredths, UtcDateTime


class AiConversation(TenantMixin, Base):
    __tablename__ = "ai_conversations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id"))


class AiMessage(TenantMixin, Base):
    __tablename__ = "ai_messages"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("ai_conversations.id"))
    role: Mapped[str]
    content: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=FetchedValue())


class AiChangeProposal(TenantMixin, Base):
    __tablename__ = "ai_change_proposals"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id"))
    conversation_id: Mapped[UUID | None]
    base_order_version: Mapped[int]
    changes: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    rationale: Mapped[str]
    price_before: Mapped[Decimal] = mapped_column(Hundredths)
    price_after: Mapped[Decimal] = mapped_column(Hundredths)
    status: Mapped[ProposalStatus] = mapped_column(
        db_enum(ProposalStatus), server_default=text("'pending'")
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=FetchedValue())
    decided_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    executed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)


class AiUsage(TenantMixin, Base):
    __tablename__ = "ai_usage"

    caterer_id: Mapped[UUID] = mapped_column(ForeignKey("caterers.id"), primary_key=True)
    month: Mapped[date] = mapped_column(primary_key=True)
    message_count: Mapped[int] = mapped_column(server_default=text("0"))
