from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin


class DishCategory(TenantMixin, Base):
    __tablename__ = "dish_categories"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str]
    sort_order: Mapped[int] = mapped_column(server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
