from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.models.enums import LeadStage
from app.schemas.base import InputModel, OutputModel

Band = Literal["low", "medium", "high"]


class LeadReason(OutputModel):
    label: str
    points: float


class LeadSummary(OutputModel):
    id: UUID
    order_id: UUID
    stage: LeadStage
    score: Decimal
    band: Band
    customer_name: str
    event_date: date
    guests: int
    total: Decimal | None
    submitted_at: datetime | None


class LeadEventOut(OutputModel):
    id: UUID
    kind: str
    stage: LeadStage | None
    note: str | None
    created_at: datetime


class LeadOut(LeadSummary):
    phone: str
    reasons: list[LeadReason]
    unknown: list[str]
    events: list[LeadEventOut]


class LeadStageUpdate(InputModel):
    stage: LeadStage


class LeadNoteCreate(InputModel):
    note: str = Field(min_length=1, max_length=1000)
