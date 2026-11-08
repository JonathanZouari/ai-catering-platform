"""Owner-editable business settings: a single row (id = 1), see migration 0006."""

from decimal import Decimal

from sqlalchemy import CheckConstraint, Integer, Numeric, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BusinessSettings(Base):
    __tablename__ = "business_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="business_settings_single_row"),
        CheckConstraint("child_portion > 0 and child_portion <= 1", name="business_settings_child"),
        CheckConstraint("lead_days between 0 and 60", name="business_settings_lead_days"),
        CheckConstraint(
            "assistant_daily_limit between 0 and 1000", name="business_settings_assistant_limit"
        ),
        CheckConstraint(
            "default_delivery_fee is null or default_delivery_fee between 0 and 10000",
            name="business_settings_default_delivery_fee",
        ),
    )
    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    # A child's portion as a share of an adult's (OPEN_DECISIONS #3: 0.75).
    child_portion: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0.75"))
    # Earliest event date = today + lead_days (OPEN_DECISIONS #5: 3).
    lead_days: Mapped[int] = mapped_column(Integer, default=3)
    # Messages a customer may send the AI assistant in any 24 hours; 0 = assistant off.
    assistant_daily_limit: Mapped[int] = mapped_column(Integer, default=30)
    # Who certifies the kitchen, shown to customers (OPEN_DECISIONS #9); null = not shown.
    kashrut_certificate: Mapped[str | None] = mapped_column(Text)
    # Delivery fee for a locality outside every zone (migration 0016); null = zones only.
    default_delivery_fee: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
