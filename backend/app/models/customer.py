from datetime import UTC, datetime

from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


# Columns follow docs/DATABASE_SCHEMA.md "customers"; auth_user_id waits on OPEN #1.
class Customer(Base):
    __tablename__ = "customers"

    # shortcut: int PK instead of Postgres uuid; switch to uuid when moving to Supabase.
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str]
    email: Mapped[str | None]
    phone: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)
