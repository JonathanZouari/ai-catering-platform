from datetime import date

from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


# docs/DATABASE_SCHEMA.md "events". Guest-count subset semantics wait on OPEN #4.
class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("adults >= 0 AND children >= 0", name="guests_non_negative"),
        CheckConstraint("adults + children > 0", name="has_guests"),
        CheckConstraint(
            "vegetarian_guests >= 0 AND vegan_guests >= 0 AND restricted_guests >= 0",
            name="diet_counts_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    event_type: Mapped[str]
    event_date: Mapped[date]
    adults: Mapped[int]
    children: Mapped[int]
    vegetarian_guests: Mapped[int] = mapped_column(default=0)
    vegan_guests: Mapped[int] = mapped_column(default=0)
    restricted_guests: Mapped[int] = mapped_column(default=0)
    dietary_notes: Mapped[str | None]
