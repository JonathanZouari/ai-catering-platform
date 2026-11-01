from uuid import UUID

from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import KashrutMixingRule, pg_enum


class Caterer(Base):
    __tablename__ = "caterers"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    slug: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    logo_path: Mapped[str | None]
    brand_color: Mapped[str | None]
    contact_phone: Mapped[str | None]
    kashrut_status: Mapped[str | None]
    kashrut_certificate_path: Mapped[str | None]
    kashrut_mixing_rule: Mapped[KashrutMixingRule] = mapped_column(
        pg_enum(KashrutMixingRule, "kashrut_mixing_rule"), server_default=text("'warn'")
    )
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))


class CatererUser(Base):
    __tablename__ = "caterer_users"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    caterer_id: Mapped[UUID] = mapped_column(ForeignKey("caterers.id"))
    auth_user_id: Mapped[UUID] = mapped_column(unique=True)
