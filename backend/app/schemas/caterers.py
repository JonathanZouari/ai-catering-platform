from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CatererCreate(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=60)
    name: str = Field(min_length=1, max_length=120)
    auth_user_id: UUID


class CatererPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    logo_path: str | None
    brand_color: str | None
    kashrut_status: str | None
