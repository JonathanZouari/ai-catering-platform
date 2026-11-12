from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps


# Columns follow docs/DATABASE_SCHEMA.md "customers"; auth_user_id waits on OPEN #1.
class Customer(Timestamps, Base):
    __tablename__ = "customers"

    # shortcut: int PKs instead of Postgres uuid in all models; switch when moving to Supabase.
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str]
    email: Mapped[str | None]
    phone: Mapped[str | None]
