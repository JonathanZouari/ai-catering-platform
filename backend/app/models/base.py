from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class Base(DeclarativeBase):
    pass


class TenantMixin:
    """Marks a model as owned by one caterer. Required by ScopedRepository."""

    @declared_attr
    def caterer_id(cls) -> Mapped[UUID]:  # noqa: N805
        return mapped_column(ForeignKey("caterers.id"), nullable=False)
