import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.schemas.orders import OrderStatus, UtcDatetime

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
# Lenient on format (local or +972...), strict on characters: digits, +, -, spaces, parentheses.
Phone = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^\+?[0-9][0-9\-\s()]{6,19}$")
]


class ProfileIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: Name
    phone: Phone


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    full_name: str
    phone: str | None


class MeOut(BaseModel):
    email: str
    profile: ProfileOut | None  # null until the customer completes it once


class MyOrderOut(BaseModel):
    id: uuid.UUID
    status: OrderStatus
    event_type: str
    event_date: date
    guests: int
    total: Decimal | None
    submitted_at: UtcDatetime | None
    decision_note: str | None
    has_pending_proposal: bool = False  # the owner proposed a change awaiting the customer


class AuthConfigOut(BaseModel):
    """Public values the browser needs for supabase-js (the anon key is public by design)."""

    supabase_url: str
    supabase_anon_key: str
