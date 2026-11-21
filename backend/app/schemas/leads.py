"""Lead form input and the owner's view of a lead."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

EventType = Literal[
    "יום הולדת", "אירוע משפחתי", "בר או בת מצווה", "ארוחת שבת", "יום נישואין", "חגיגה פרטית", "אחר"
]
Source = Literal["google", "instagram", "facebook", "referral", "direct", "other"]


class LeadIn(BaseModel):
    """What the lead form sends. Behaviour signals are reported by the browser, so they are
    bounded here but can be faked; they only affect a score the owner sees."""

    full_name: str = Field(min_length=2, max_length=80)
    phone: str = Field(pattern=r"^0\d{1,2}-?\d{7}$")
    event_type: EventType
    guests: int = Field(ge=1, le=2000)
    event_date: date
    budget_per_guest: int = Field(ge=0, le=2000)
    consent: Literal[True]
    dishes_viewed: int = Field(default=0, ge=0, le=500)
    minutes_on_site: float = Field(default=0, ge=0, le=1440)
    visits: int = Field(default=1, ge=1, le=1000)
    source: Source = "direct"
    used_chat: bool = False

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v) < 2:
            raise ValueError("name too short")
        return v

    @field_validator("event_date")
    @classmethod
    def future_date(cls, v: date) -> date:
        days = (v - date.today()).days
        if not 0 <= days <= 730:
            raise ValueError("event date must be between today and two years ahead")
        return v


class LeadOut(BaseModel):
    lead_id: str
    full_name: str
    phone: str
    event_type: str
    guests: int
    days_until_event: int
    budget_per_guest: int
    dishes_viewed: int
    visits: int
    source: str
    used_chat: bool
    probability: float
    is_hot: bool | None
    is_demo: bool
