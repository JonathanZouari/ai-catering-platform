from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Numeric, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin
from app.models.enums import LeadStage, pg_enum


class Lead(TenantMixin, Base):
    __tablename__ = "leads"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    order_id: Mapped[UUID] = mapped_column(unique=True)
    stage: Mapped[LeadStage] = mapped_column(
        pg_enum(LeadStage, "lead_stage"), server_default=text("'new'")
    )
    score: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    score_version: Mapped[str]
    reasons: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'"))
    features: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'"))
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class LeadEvent(TenantMixin, Base):
    __tablename__ = "lead_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    lead_id: Mapped[UUID]
    kind: Mapped[str]
    stage: Mapped[LeadStage | None] = mapped_column(pg_enum(LeadStage, "lead_stage"))
    note: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class LeadOutcome(TenantMixin, Base):
    __tablename__ = "lead_outcomes"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    lead_id: Mapped[UUID] = mapped_column(unique=True)
    outcome: Mapped[LeadStage] = mapped_column(pg_enum(LeadStage, "lead_stage"))
    score_at_decision: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    score_version: Mapped[str]
    features: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'"))
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
