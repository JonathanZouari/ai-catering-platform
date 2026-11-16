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
    # Serialized as a string ("180.00") so clients never round a float amount.
    budget_per_guest: Decimal
    source: LeadSource
    is_returning: bool
    status: LeadStatus
    created_at: datetime
    # Between 0 and 1. None for a closed lead (won or lost): its outcome is known.
    purchase_probability: float | None


class LeadStatusUpdate(BaseModel):
    status: LeadStatus
