from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import KashrutMixingRule
from app.schemas.base import OutputModel, PatchModel

BrandColor = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]
EmailAddress = Annotated[str, Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)]


class CatererCreate(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=60)
    name: str = Field(min_length=1, max_length=120)
    auth_user_id: UUID


class CatererPublic(OutputModel):
    slug: str
    name: str
    logo_path: str | None
    brand_color: str | None
    kashrut_status: str | None
    contact_phone: str | None


class ProfileOut(CatererPublic):
    notification_email: str | None
    kashrut_certificate_path: str | None
    kashrut_mixing_rule: KashrutMixingRule


class ProfileUpdate(PatchModel):
    required_fields = {"name", "kashrut_mixing_rule"}

    name: str | None = Field(default=None, min_length=1, max_length=120)
    brand_color: BrandColor | None = None
    contact_phone: str | None = Field(default=None, max_length=30)
    notification_email: EmailAddress | None = None
    kashrut_status: str | None = Field(default=None, max_length=200)
    kashrut_mixing_rule: KashrutMixingRule | None = None


class ClientConfig(BaseModel):
    supabase_url: str | None
    supabase_anon_key: str | None
    storage_public_url: str | None
