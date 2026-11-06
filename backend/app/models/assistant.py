"""AI assistant conversations, mirroring migrations 0010 and 0015 (docs/AI_AGENT_DESIGN.md).

One conversation per order. Messages are stored exactly as sent to and received from the model
(Claude Messages API content blocks, thinking included) and only ever appended: the model needs
its own earlier blocks back unchanged.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AiConversation(Base):
    __tablename__ = "ai_conversations"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AiMessage(Base):
    __tablename__ = "ai_messages"
    __table_args__ = (
        CheckConstraint("role in ('user', 'assistant')", name="ai_messages_role"),
        UniqueConstraint("conversation_id", "position", name="ai_messages_conversation_position"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE"), index=True
    )
    # 1, 2, 3... within the conversation; the history order (created_at ties within a turn).
    position: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(Text)
    # Message content blocks as the API takes them: text, thinking, tool_use, tool_result.
    content: Mapped[list] = mapped_column(JSON)
    # The customer's own words (user messages that aren't tool results); null otherwise.
    # Counted for the daily limit and shown in the chat history.
    customer_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
