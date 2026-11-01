from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CategoryCreate(BaseModel):
    # extra="forbid": a body that tries to name a caterer is rejected, not ignored.
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = None
    is_active: bool | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    sort_order: int
    is_active: bool
