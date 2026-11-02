"""Change proposals on an order, mirroring migration 0009.

One mechanism for both proposers (ADR 0003): the owner proposes changes to an order awaiting
approval (OPEN_DECISIONS #6, this slice); the AI assistant will propose changes to drafts in
Phase 4 (docs/AI_AGENT_DESIGN.md). Nothing changes until the customer accepts, and accepting only
works while the order is still at `base_order_version`.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

PROPOSAL_STATUSES = ("pending", "accepted", "declined", "cancelled", "expired")


class OrderProposal(Base):
    __tablename__ = "order_proposals"
    __table_args__ = (
        CheckConstraint("proposed_by in ('owner', 'assistant')", name="order_proposals_by"),
        CheckConstraint(
            "status in ('pending', 'accepted', 'declined', 'cancelled', 'expired')",
            name="order_proposals_status",
        ),
        # At most one open proposal per order.
        Index(
            "order_proposals_one_pending",
            "order_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    proposed_by: Mapped[str] = mapped_column(Text)
    base_order_version: Mapped[int] = mapped_column(Integer)
    # [{"op": "add_item"|"set_quantity"|"remove_item", "dish_id", "name",
    #   "from_quantity", "to_quantity"}]
    changes: Mapped[list] = mapped_column(JSON)
    # The full proposed item list with frozen prices:
    # [{"dish_id", "name", "pricing_unit", "quantity", "unit_price", "line_total"}]
    lines: Mapped[list] = mapped_column(JSON)
    price_before: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    price_after: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    note: Mapped[str | None] = mapped_column(Text)  # from the proposer, shown to the customer
    status: Mapped[str] = mapped_column(Text, default="pending")
    customer_note: Mapped[str | None] = mapped_column(Text)  # reason when declining
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
