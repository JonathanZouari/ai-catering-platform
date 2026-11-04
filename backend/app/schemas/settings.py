from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    child_portion: Decimal = Field(gt=0, le=1, max_digits=3, decimal_places=2)
    lead_days: int = Field(ge=0, le=60)
    assistant_daily_limit: int = Field(ge=0, le=1000)


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    child_portion: Decimal
    lead_days: int
    assistant_daily_limit: int
