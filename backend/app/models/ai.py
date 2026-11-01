from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin
from app.models.enums import ProposalStatus, pg_enum


class AiConversation(TenantMixin, Base):
    __tablename__ = "ai_conversations"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id"))


class AiMessage(TenantMixin, Base):
    __tablename__ = "ai_messages"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("ai_conversations.id"))
    role: Mapped[str]
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class AiChangeProposal(TenantMixin, Base):
    __tablename__ = "ai_change_proposals"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id"))
    conversation_id: Mapped[UUID | None]
    base_order_version: Mapped[int]
    changes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    rationale: Mapped[str]
    price_before: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    price_after: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[ProposalStatus] = mapped_column(
        pg_enum(ProposalStatus, "proposal_status"), server_default=text("'pending'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AiUsage(TenantMixin, Base):
    __tablename__ = "ai_usage"

    caterer_id: Mapped[UUID] = mapped_column(ForeignKey("caterers.id"), primary_key=True)
    month: Mapped[date] = mapped_column(primary_key=True)
    message_count: Mapped[int] = mapped_column(server_default=text("0"))
