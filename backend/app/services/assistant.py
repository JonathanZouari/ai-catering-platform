"""AI assistant conversations: storage, the daily limit and the chat view (Phase 4).

The model loop itself lives in app/agents/assistant.py and reaches the database only through
this module and the other services. One conversation per order, chat only on the customer's own
draft. Messages are appended, never edited (the model needs its earlier blocks back unchanged).
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.customer_auth import CustomerIdentity
from app.core.errors import AppError
from app.models.assistant import AiConversation, AiMessage
from app.models.orders import Order
from app.schemas import assistant as s
from app.services import customer_orders, proposals
from app.services import settings as settings_svc


def _draft(db: Session, who: CustomerIdentity, order_id: uuid.UUID) -> Order:
    order = customer_orders._owned(db, who, order_id)  # 404 for other customers' orders
    if order.status != "draft":
        raise AppError(409, "invalid_transition", "The assistant helps while the order is a draft")
    return order


def _conversation(db: Session, order_id: uuid.UUID) -> AiConversation | None:
    return db.scalar(select(AiConversation).where(AiConversation.order_id == order_id))


def _messages(db: Session, conversation: AiConversation | None) -> list[AiMessage]:
    if conversation is None:
        return []
    q = select(AiMessage).where(AiMessage.conversation_id == conversation.id)
    return list(db.scalars(q.order_by(AiMessage.position)))


def _sent_today(db: Session, order: Order) -> int:
    """The customer's messages in the last 24 hours, across all their orders."""
    start = datetime.now(UTC) - timedelta(days=1)
    q = (
        select(func.count(AiMessage.id))
        .join(AiConversation, AiConversation.id == AiMessage.conversation_id)
        .join(Order, Order.id == AiConversation.order_id)
        .where(
            Order.customer_id == order.customer_id,
            AiMessage.customer_text.is_not(None),
            AiMessage.created_at >= start,
        )
    )
    return db.scalar(q) or 0


def start_turn(
    db: Session, who: CustomerIdentity, order_id: uuid.UUID, text: str
) -> tuple[uuid.UUID, list[dict]]:
    """Check the order and the limit, store the customer's message; returns the conversation id
    and the full message history to send to the model."""
    order = _draft(db, who, order_id)
    limit = settings_svc.get(db).assistant_daily_limit
    if _sent_today(db, order) >= limit:
        raise AppError(429, "assistant_limit", "Daily message limit reached", {"limit": limit})
    conversation = _conversation(db, order.id)
    if conversation is None:
        conversation = AiConversation(order_id=order.id)
        db.add(conversation)
        db.flush()
    db.add(
        AiMessage(
            conversation_id=conversation.id,
            position=_next_position(db, conversation.id),
            role="user",
            content=[{"type": "text", "text": text}],
            customer_text=text,
        )
    )
    db.commit()
    history = [{"role": m.role, "content": m.content} for m in _messages(db, conversation)]
    return conversation.id, history


def append(db: Session, conversation_id: uuid.UUID, messages: list[dict]) -> None:
    """Store a finished turn's messages together, so a failed turn never leaves a tool call
    without its result in the history."""
    start = _next_position(db, conversation_id)
    for i, m in enumerate(messages):
        db.add(
            AiMessage(
                conversation_id=conversation_id,
                position=start + i,
                role=m["role"],
                content=m["content"],
            )
        )
    db.commit()


def _next_position(db: Session, conversation_id: uuid.UUID) -> int:
    # A concurrent turn on the same conversation hits the unique (conversation_id, position)
    # and fails instead of interleaving the history.
    q = select(func.coalesce(func.max(AiMessage.position), 0))
    return db.scalar(q.where(AiMessage.conversation_id == conversation_id)) + 1


def _reply_text(content: list[dict]) -> str:
    return "\n\n".join(b["text"] for b in content if b.get("type") == "text" and b["text"].strip())


def chat_view(db: Session, who: CustomerIdentity, order_id: uuid.UUID) -> s.ChatOut:
    """What the customer sees: their messages, the assistant's replies, the open proposal."""
    order = customer_orders._owned(db, who, order_id)
    shown = []
    for m in _messages(db, _conversation(db, order.id)):
        if m.customer_text is not None:
            shown.append(s.ChatMessageOut(role="user", text=m.customer_text))
        elif m.role == "assistant" and (text := _reply_text(m.content)):
            shown.append(s.ChatMessageOut(role="assistant", text=text))
    pending = [
        p
        for p in proposals.list_for_order(db, order.id)
        if p.proposed_by == "assistant" and p.status == "pending"
    ]
    limit = settings_svc.get(db).assistant_daily_limit
    return s.ChatOut(
        available=bool(get_settings().anthropic_api_key) and limit > 0,
        messages=shown,
        proposal=pending[0] if pending else None,
        remaining_today=max(limit - _sent_today(db, order), 0),
    )
