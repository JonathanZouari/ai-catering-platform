from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Certificate = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


class SettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    child_portion: Decimal = Field(gt=0, le=1, max_digits=3, decimal_places=2)
    lead_days: int = Field(ge=0, le=60)
    assistant_daily_limit: int = Field(ge=0, le=1000)
    kashrut_certificate: Certificate | None  # required (full replacement); null or "" = none
    # Fee for any locality outside the zones; required, null = deliver to zone cities only.
    default_delivery_fee: Decimal | None = Field(ge=0, le=10_000, max_digits=7, decimal_places=2)


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    child_portion: Decimal
    lead_days: int
    assistant_daily_limit: int
    kashrut_certificate: str | None
    default_delivery_fee: Decimal | None


class BusinessOut(BaseModel):
    """Public facts about the business."""

    model_config = ConfigDict(from_attributes=True)
    kashrut_certificate: str | None
