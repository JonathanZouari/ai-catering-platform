from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

LeadStatus = Literal["new", "contacted", "quoted", "won", "lost"]
LeadSource = Literal["referral", "google", "instagram", "website"]


class Lead(BaseModel):
    id: UUID
    full_name: str
    phone: str | None
    email: str | None
    event_type: str
    event_date: date
    guests: int
    budget_per_guest: Decimal
    source: LeadSource
    is_returning: bool
    status: LeadStatus
    created_at: datetime
    # Between 0 and 1. Meaningful for open leads; a closed lead's outcome is already known.
    purchase_probability: float
